"""
m2_instarem/collect.py
───────────────────────
收集 Instarem MYR→USD 报价。

  --mode auto   : 优先调用官网公开端点 GET /api/v1/public/transaction/computed-value
                  （与网页计算器同源）；失败时再尝试 BeautifulSoup 旧选择器
  --mode manual : 交互式 CLI，手动输入报价

最佳实践：与 M1 在同一时刻运行（同一时段内），确保对比公平。

用法:
    python collect.py --mode manual
    python collect.py --mode auto --amount 10000 --amount 50000

输出:
    data/m2_instarem/raw_quotes.jsonl
"""

import argparse
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests
from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).parent.parent))
from utils import append_jsonl, fetch_mid_rate, section, session_for

DATA_DIR = Path(__file__).parent.parent.parent / "data" / "m2_instarem"
DATA_DIR.mkdir(parents=True, exist_ok=True)
RAW_QUOTES = DATA_DIR / "raw_quotes.jsonl"

# Instarem 公开计算器（结构随时可能变化）
INSTAREM_CALC_URL = "https://www.instarem.com/en-my/send-money/myr-to-usd/"
INSTAREM_API_BASE = os.environ.get("INSTAREM_API_BASE", "https://www.instarem.com/api").rstrip(
    "/"
)


def fetch_instarem_public_api(amount_myr: float) -> dict | None:
    """
    Instarem 公开计算器 API（无需登录；与页面 widget 同源）。
    GET .../v1/public/transaction/computed-value?...
    """
    params = {
        "source_currency": "MYR",
        "destination_currency": "USD",
        "instarem_bank_account_id": "",
        "country_code": "MY",
        "source_amount": int(amount_myr),
    }
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/122.0.0.0 Safari/537.36"
        ),
        "Accept": "application/json",
    }
    url = f"{INSTAREM_API_BASE}/v1/public/transaction/computed-value"
    try:
        resp = requests.get(url, params=params, headers=headers, timeout=15)
        resp.raise_for_status()
        payload = resp.json()
        if not payload.get("success") or not payload.get("data"):
            print(f"  [api] Unexpected success/data: {str(payload)[:200]}")
            return None
        data = payload["data"]
        rate = float(data.get("fx_rate") or data.get("instarem_fx_rate") or 0)
        if rate <= 0:
            print("  [api] Missing positive fx_rate in response.")
            return None
        fee = float(data.get("transaction_fee_amount") or 0)
        target = float(data.get("destination_amount") or 0)
        ts = datetime.now(timezone.utc)
        return {
            "timestamp": ts.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "source": "instarem_public_api",
            "source_amount": float(amount_myr),
            "instarem_rate": rate,
            "fee_total_myr": fee,
            "target_amount": round(target, 2) if target else round(
                (amount_myr - fee) * rate, 2
            ),
            "session": session_for(ts),
            "mid_rate_at_quote": None,
        }
    except Exception as e:
        print(f"  [api] Public API failed: {e}")
        return None


def fetch_instarem_auto(amount_myr: float) -> dict | None:
    """
    尝试从 Instarem 页面抓取报价。
    返回 None 表示抓取失败（退回 manual）。
    """
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/122.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "en-US,en;q=0.9",
    }
    try:
        api = fetch_instarem_public_api(amount_myr)
        if api is not None:
            return api

        resp = requests.get(INSTAREM_CALC_URL, headers=headers, timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        # 尝试找到汇率元素（选择器会随页面更新）
        rate_el = soup.select_one("[data-rate], .exchange-rate, .rate-value")
        fee_el = soup.select_one("[data-fee], .fee-value, .transfer-fee")

        if not rate_el:
            print("  [auto] Rate element not found — page structure may have changed.")
            return None

        rate = float(rate_el.get_text(strip=True).replace(",", ""))
        fee_text = fee_el.get_text(strip=True) if fee_el else "0"
        fee = float("".join(c for c in fee_text if c.isdigit() or c == ".") or "0")

        ts = datetime.now(timezone.utc)
        return {
            "timestamp": ts.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "source": "instarem_auto_scrape",
            "source_amount": amount_myr,
            "instarem_rate": rate,
            "fee_total_myr": fee,
            "target_amount": round((amount_myr - fee) * rate, 2),
            "session": session_for(ts),
            "mid_rate_at_quote": None,  # 由 collect() 补充
        }
    except Exception as e:
        print(f"  [auto] Scrape failed: {e}")
        return None


def fetch_instarem_manual(amount_myr: float) -> dict:
    """
    交互式手动输入 Instarem 报价。
    用户从 instarem.com 查到汇率后填入。
    """
    print(f"\n  Manual input for RM {amount_myr:,.0f}:")
    print("  -> 请打开 https://www.instarem.com/en-my/ 并输入金额，")
    print("     记录以下信息后按 Enter 确认。\n")

    rate_str = input(f"  Instarem exchange rate (1 MYR = ? USD): ").strip()
    fee_str = input(f"  Transfer fee (MYR, 如没有则填 0): ").strip()
    target_str = input(f"  Recipient gets (USD): ").strip()

    rate = float(rate_str)
    fee = float(fee_str) if fee_str else 0.0
    target = float(target_str) if target_str else round((amount_myr - fee) * rate, 2)

    ts = datetime.now(timezone.utc)
    return {
        "timestamp": ts.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source": "instarem_manual",
        "source_amount": amount_myr,
        "instarem_rate": rate,
        "fee_total_myr": fee,
        "target_amount": target,
        "session": session_for(ts),
        "mid_rate_at_quote": None,
    }


def run(amounts: list, mode: str = "manual") -> None:
    section("M2 Instarem — collect.py")
    print(f"Mode: {mode}")

    print("\nFetching mid-rate for timestamp anchor...")
    mid = fetch_mid_rate("MYR", "USD")
    print(f"  mid: 1 MYR = {mid['mid_rate']:.6f} USD  [{mid['timestamp']}]")

    strict = os.environ.get("STRICT_AUTO", "").lower() in ("1", "true", "yes")

    for amount in amounts:
        print(f"\nProcessing RM {amount:,.0f}...")
        if mode == "auto":
            record = fetch_instarem_auto(amount)
            if record is None:
                if strict:
                    print("  Auto failed and STRICT_AUTO=1 — exiting.")
                    sys.exit(1)
                print("  Auto failed. Falling back to manual input.")
                record = fetch_instarem_manual(amount)
        else:
            record = fetch_instarem_manual(amount)

        record["mid_rate_at_quote"] = mid["mid_rate"]
        append_jsonl(RAW_QUOTES, record)
        print(f"  Saved: rate={record['instarem_rate']}, fee={record['fee_total_myr']}, "
              f"target={record['target_amount']}")

    print(f"\nDone. Raw quotes -> {RAW_QUOTES}")


def main():
    parser = argparse.ArgumentParser(description="Collect Instarem MYR→USD quotes.")
    parser.add_argument("--mode", choices=["auto", "manual"], default="manual",
                        help="auto: scrape website; manual: CLI input (more reliable)")
    parser.add_argument("--amount", type=float, action="append",
                        help="Amount in MYR. Default: 10000 50000")
    args = parser.parse_args()
    amounts = args.amount if args.amount else [10000.0, 50000.0]
    run(amounts=amounts, mode=args.mode)


if __name__ == "__main__":
    main()
