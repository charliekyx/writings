"""
m3_bank_tt/collect.py
───────────────────────
收集银行零售 TT 汇率（1 USD = X MYR）与 FTT 手续费，均来自**各银行官网**解析；
requests 失败时用 Playwright 加载同一官方 URL（不冒充他行、不用 BNM 汇总价替代单家银行）。

环境变量:
  STRICT_AUTO=1       : scrape 失败不回退 manual（非交互流水线应开启）
  STRICT_AUTO=0 且无 TTY（如 docker 默认）: 无法手填，会退出并提示用 SKIP_M3_MAYBANK 等
  M3_HTTP_TIMEOUT     : requests 单次超时秒数，默认 45
  M3_BANK_HTML_RETRIES: 银行官网 requests 重试次数，默认 1
  M3_USE_REQUESTS_ONLY=1: 禁用 Playwright（仅 CI/无浏览器环境）
  Maybank 默认先试 Mobile forexRates.do（轻量），再试桌面 forex_rates.page
  M3_PLAYWRIGHT_TIMEOUT_MS: Playwright 单次导航超时，默认 240000（4 分钟）；仍超时多为网络/站点问题
  docker_entry 中 SKIP_M3_MAYBANK=1 可跳过 Maybank 仅跑 CIMB（本地/不可达时）

输出:
    data/m3_bank_tt/raw_rates.jsonl
"""

import argparse
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests
from bs4 import BeautifulSoup
from requests.exceptions import ConnectionError, HTTPError, Timeout

sys.path.insert(0, str(Path(__file__).parent.parent))
from utils import append_jsonl, fetch_mid_rate, section, session_for

from fee_scrape import scrape_wire_fee_myr

DATA_DIR = Path(__file__).parent.parent.parent / "data" / "m3_bank_tt"


def _stdin_is_interactive() -> bool:
    try:
        return sys.stdin.isatty()
    except (ValueError, AttributeError):
        return False


def _exit_noninteractive_manual_hint() -> None:
    print(
        "  Non-interactive stdin (e.g. `docker run` without -it): cannot prompt for manual input.\n"
        "  Use: SKIP_M3_MAYBANK=1 to skip Maybank | STRICT_AUTO=1 to fail fast without prompts |\n"
        "       `docker run -it` for TTY | or run `collect.py --mode manual` on your laptop."
    )
    sys.exit(1)

DATA_DIR.mkdir(parents=True, exist_ok=True)
RAW_RATES = DATA_DIR / "raw_rates.jsonl"

# Maybank：先试官方 Mobile 轻量页（同柜台价，requests/Playwright 不易卡死），再回退桌面 forex 页。
BANK_URLS: dict[str, str | list[str]] = {
    "maybank": [
        "https://www.maybank2u.com.my/mbb/Mobile/forexRates.do",
        "https://www.maybank2u.com.my/maybank2u/malaysia/en/personal/rates/forex_rates.page",
    ],
    "cimb": (
        "https://www.cimb.com.my/en/business/help-and-support/rates-charges/"
        "forex-rates.htm.html"
    ),
}


def _urls_for_bank(bank: str) -> list[str]:
    u = BANK_URLS.get(bank)
    if u is None:
        return []
    return [u] if isinstance(u, str) else list(u)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    )
}


def _m3_http_timeout_sec() -> float:
    raw = os.environ.get("M3_HTTP_TIMEOUT", "45").strip()
    try:
        return float(raw)
    except ValueError:
        return 45.0


def _parse_usd_tt_selling_from_html(bank: str, html: str) -> float | None:
    """从已下载 HTML 解析 1 USD = X MYR（TT/OD Selling）。"""
    soup = BeautifulSoup(html, "html.parser")
    if bank == "cimb":
        for row in soup.find_all("tr"):
            tds = row.find_all("td")
            if len(tds) >= 3 and tds[1].get_text(strip=True) == "USD":
                try:
                    val = float(tds[2].get_text(strip=True).replace(",", ""))
                    if 3.0 < val < 6.0:
                        return val
                except ValueError:
                    continue
        return None

    # Maybank：桌面页含 "USD"；Mobile forexRates.do 行为 "1 US Dollar"
    def _row_is_usd_myr(cells: list[str]) -> bool:
        for c in cells:
            u = c.upper()
            if "USD" in u or "US DOLLAR" in u:
                return True
        return False

    for row in soup.find_all("tr"):
        cells = [td.get_text(strip=True) for td in row.find_all("td")]
        if not _row_is_usd_myr(cells):
            continue
        for c in cells:
            try:
                val = float(c.replace(",", ""))
                if 3.0 < val < 6.0:
                    return val
            except ValueError:
                pass
    return None


def _bank_html_max_attempts() -> int:
    raw = os.environ.get("M3_BANK_HTML_RETRIES", "1").strip()
    try:
        n = int(raw)
        return max(1, min(n, 5))
    except ValueError:
        return 1


def _http_get_with_retries(url: str) -> requests.Response:
    timeout = _m3_http_timeout_sec()
    max_attempts = _bank_html_max_attempts()
    last_exc: Exception | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            resp = requests.get(url, headers=HEADERS, timeout=timeout)
            resp.raise_for_status()
            return resp
        except Timeout as e:
            last_exc = e
            print(f"  HTTP attempt {attempt}/{max_attempts}: {e}")
            if attempt >= max_attempts:
                raise
            time.sleep(2 + attempt)
        except ConnectionError as e:
            last_exc = e
            print(f"  HTTP attempt {attempt}/{max_attempts}: {e}")
            if attempt >= max_attempts:
                raise
            time.sleep(2 + attempt)
        except HTTPError as e:
            code = e.response.status_code if e.response is not None else 0
            if 500 <= code < 600 and attempt < max_attempts:
                print(f"  HTTP attempt {attempt}/{max_attempts}: HTTP {code}")
                time.sleep(2 + attempt)
                continue
            raise
    raise RuntimeError(last_exc or "HTTP failed")


def scrape_bank_rate_from_html(bank: str) -> tuple[float, str] | None:
    urls = _urls_for_bank(bank)
    if not urls:
        return None
    last_err: Exception | None = None
    for url in urls:
        try:
            resp = _http_get_with_retries(url)
        except Exception as e:
            last_err = e
            print(f"  Bank page fetch failed for {bank} ({url}): {e}")
            continue
        try:
            rate = _parse_usd_tt_selling_from_html(bank, resp.text)
            if rate is None:
                print(f"  Could not parse USD TT selling from {bank} HTML ({url}) (layout changed?).")
            else:
                return (rate, url)
        except Exception as e:
            print(f"  Parse failed for {bank} ({url}): {e}")
    if last_err:
        print(f"  All HTTP URLs failed for {bank}; last error: {last_err}")
    return None


def _m3_playwright_timeout_ms() -> int:
    raw = os.environ.get("M3_PLAYWRIGHT_TIMEOUT_MS", "240000").strip()
    try:
        return max(30_000, int(raw))
    except ValueError:
        return 240_000


def scrape_bank_rate_playwright(bank: str) -> tuple[float, str] | None:
    try:
        from playwright_helper import fetch_page_html, playwright_available
    except ImportError:
        print("  Playwright not installed.")
        return None
    if not playwright_available():
        print("  Playwright not available (pip install playwright && playwright install chromium).")
        return None
    urls = _urls_for_bank(bank)
    if not urls:
        return None
    timeout_ms = _m3_playwright_timeout_ms()
    # Slow / flaky sites: try "commit" first (earlier than domcontentloaded), then full DOM.
    strategies: list[tuple[str, int]] = [
        ("commit", 10_000),
        ("domcontentloaded", 5_000),
    ]
    last_err: Exception | None = None
    for url in urls:
        html: str | None = None
        for wait_until, wait_after in strategies:
            try:
                print(f"  Playwright: {url} wait_until={wait_until!r} (timeout_ms={timeout_ms})...")
                html = fetch_page_html(
                    url,
                    timeout_ms=timeout_ms,
                    wait_after_ms=wait_after,
                    wait_until=wait_until,
                )
                break
            except Exception as e:
                last_err = e
                print(f"  Playwright ({wait_until}) failed: {e}")
        if html is None:
            print(f"  Playwright page load failed for {bank} ({url}): {last_err}")
            continue
        rate = _parse_usd_tt_selling_from_html(bank, html)
        if rate is not None:
            return (rate, url)
        print(f"  Playwright: could not parse USD TT selling from {bank} ({url}).")
    print(f"  Playwright: all URLs failed or unparsable for {bank}; last error: {last_err}")
    return None


def resolve_tt_selling_rate(bank: str) -> tuple[float, str, str] | None:
    """
    仅从本行官网解析 TT Selling。返回 (rate, source_key, page_url)。
    source_key: {bank}_html | {bank}_playwright
    """
    got = scrape_bank_rate_from_html(bank)
    if got is not None:
        rate, page_url = got
        return rate, f"{bank}_html", page_url

    requests_only = os.environ.get("M3_USE_REQUESTS_ONLY", "").strip().lower() in (
        "1",
        "true",
        "yes",
    )
    if requests_only:
        print("  M3_USE_REQUESTS_ONLY=1 — skipping Playwright for TT rate.")
        return None

    print(f"  Trying Playwright for {bank} official FX page...")
    got2 = scrape_bank_rate_playwright(bank)
    if got2 is None:
        return None
    rate, page_url = got2
    return rate, f"{bank}_playwright", page_url


def manual_input(bank: str, amount_myr: float) -> dict:
    """交互式输入银行 TT 汇率和费用。"""
    print(f"\n  Manual input — {bank.upper()} TT (MYR→USD)")
    print(f"  金额: RM {amount_myr:,.0f}")
    print(f"  请打开银行网站，找到 USD TT Selling Rate，填入以下信息：\n")

    rate_str = input(f"  TT Selling Rate (1 USD = ? MYR, e.g. 4.48): ").strip()
    wire_fee_str = input(f"  Wire fee (MYR, 如 RM 25): ").strip()
    cable_str = input(f"  Cable/admin fee (MYR, 如 0): ").strip()

    tt_selling = float(rate_str)
    wire_fee = float(wire_fee_str) if wire_fee_str else 0.0
    cable_fee = float(cable_str) if cable_str else 0.0

    ts = datetime.now(timezone.utc)
    return {
        "timestamp": ts.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "session": session_for(ts),
        "bank": bank,
        "source": "manual",
        "source_amount": amount_myr,
        "tt_selling_rate": tt_selling,
        "wire_fee_myr": wire_fee,
        "cable_fee_myr": cable_fee,
        "total_fixed_fee_myr": wire_fee + cable_fee,
        "mid_rate_at_quote": None,
        "source_tier": "manual",
    }


def run(bank: str, amounts: list, mode: str = "manual") -> None:
    section("M3 Bank TT — collect.py")
    strict = os.environ.get("STRICT_AUTO", "").lower() in ("1", "true", "yes")
    print(f"Bank: {bank.upper()} | Mode: {mode}")

    print("\nFetching mid-rate...")
    mid = fetch_mid_rate("MYR", "USD")
    print(f"  mid: 1 MYR = {mid['mid_rate']:.6f} USD  [{mid['timestamp']}]")

    scraped_rate = None
    tt_src_key: str | None = None
    tt_src_url: str | None = None
    if mode == "scrape":
        print(f"\nResolving {bank.upper()} TT selling rate (1 USD = ? MYR)...")
        resolved = resolve_tt_selling_rate(bank)
        if resolved is None:
            print("  Could not obtain TT selling rate from bank official pages.")
            if strict:
                print("  STRICT_AUTO: exiting (no manual fallback).")
                sys.exit(1)
            print("  Falling back to manual.")
            if not _stdin_is_interactive():
                _exit_noninteractive_manual_hint()
        else:
            scraped_rate, tt_src_key, tt_src_url = resolved
            print(f"  TT Selling (USD/MYR): {scraped_rate:.4f}  [source={tt_src_key}]")

    wire_fee_myr: float | None = None
    wire_fee_url: str | None = None
    if scraped_rate is not None and mode == "scrape":
        try:
            wire_fee_myr, wire_fee_url = scrape_wire_fee_myr(bank)
            print(f"  Scraped wire fee: RM {wire_fee_myr:.2f}  [{wire_fee_url}]")
        except Exception as e:
            if strict:
                print(f"  STRICT_AUTO: wire fee scrape failed: {e}")
                sys.exit(1)
            print(f"  Wire fee scrape failed ({e}); enter manually.")
            wire_fee_myr = None

    for amount in amounts:
        if scraped_rate is not None and mode == "scrape":
            ts = datetime.now(timezone.utc)
            wf = wire_fee_myr
            if wf is None:
                if not _stdin_is_interactive():
                    print("  Wire fee scrape failed; need manual fee but stdin is non-interactive.")
                    _exit_noninteractive_manual_hint()
                wire_fee_str = input(
                    f"  Wire fee for RM {amount:,.0f} (MYR): "
                ).strip()
                wf = float(wire_fee_str) if wire_fee_str else 0.0
            record = {
                "timestamp": ts.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "session": session_for(ts),
                "bank": bank,
                "source": "scrape",
                "source_tier": "authoritative",
                "source_amount": amount,
                "tt_selling_rate": scraped_rate,
                "tt_rate_source": tt_src_key,
                "tt_rate_source_url": tt_src_url,
                "wire_fee_myr": wf,
                "cable_fee_myr": 0.0,
                "total_fixed_fee_myr": wf,
                "wire_fee_source_url": wire_fee_url,
                "wire_fee_note": None,
                "mid_rate_at_quote": None,
            }
        else:
            record = manual_input(bank, amount)

        record["mid_rate_at_quote"] = mid["mid_rate"]
        append_jsonl(RAW_RATES, record)
        print(f"  Saved: {bank} rate={record['tt_selling_rate']}, wire={record['wire_fee_myr']}")

    print(f"\nDone. Raw rates -> {RAW_RATES}")


def main():
    parser = argparse.ArgumentParser(description="Collect bank TT rates for MYR→USD.")
    parser.add_argument("--bank", choices=["maybank", "cimb", "rhb", "other"],
                        default="maybank")
    parser.add_argument("--mode", choices=["scrape", "manual"], default="manual")
    parser.add_argument("--amount", type=float, action="append",
                        help="Amount in MYR. Default: 10000 50000")
    args = parser.parse_args()
    amounts = args.amount if args.amount else [10000.0, 50000.0]
    run(bank=args.bank, amounts=amounts, mode=args.mode)


if __name__ == "__main__":
    main()
