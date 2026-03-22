"""
m1_wise/collect.py
──────────────────
获取 Wise MYR→USD 报价，同时记录 Frankfurter mid-rate 作为对照锚点。

本脚本支持三种策略:
  --mode api     : Wise 官方 API（需 WISE_API_TOKEN 以解析 profile；若 profile 报价返回 401，
                   则自动改用无鉴权 POST /v3/quotes，source=wise_api_public）
  --mode scrape  : 从 wise.com 网页提取嵌入的汇率 JSON（无需 token）
                   费用按 wise.com pricing 页记录的结构估算
  --mode manual  : 交互式 CLI（TTY）；流水线中请用 api 或 scrape

注意: 使用 --loop 参数可在同一天多个时段采样，用于 spread 稳定性研究。

环境变量:
  WISE_API_TOKEN    Bearer token（api 模式必填）
  WISE_PROFILE_ID   数字 profile id；未设则 GET /v1/profiles 取首个 personal
  WISE_API_BASE     默认 https://api.wise.com

用法:
    python collect.py --mode api
    python collect.py --mode scrape
    python collect.py --loop 3 --wait 3600

输出:
    data/m1_wise/raw_quotes.jsonl
    data/m1_wise/mid_rates.jsonl
"""

import argparse
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).parent.parent))
from utils import append_jsonl, fetch_mid_rate, section, session_for

DATA_DIR = Path(__file__).parent.parent.parent / "data" / "m1_wise"
DATA_DIR.mkdir(parents=True, exist_ok=True)
RAW_QUOTES = DATA_DIR / "raw_quotes.jsonl"
MID_RATES = DATA_DIR / "mid_rates.jsonl"

WISE_RATE_PAGE = "https://wise.com/gb/currency-converter/myr-to-usd-rate"
WISE_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-GB,en;q=0.9",
}

# 费用参数（来自 wise.com/gb/pricing — 需定期核实）
# MYR→USD bank transfer: 固定费 + 变动费（0.57% × 金额）
WISE_FEE_FIXED_MYR = 4.14
WISE_FEE_VARIABLE_PCT = 0.0057

WISE_API_BASE = os.environ.get("WISE_API_BASE", "https://api.wise.com").rstrip("/")


def _wise_headers() -> dict:
    token = os.environ.get("WISE_API_TOKEN", "").strip()
    if not token:
        raise RuntimeError("WISE_API_TOKEN is not set (required for --mode api)")
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }


def wise_get_profile_id() -> int:
    """Resolve profile id from WISE_PROFILE_ID or first personal profile."""
    env_id = os.environ.get("WISE_PROFILE_ID", "").strip()
    if env_id:
        return int(env_id)
    url = f"{WISE_API_BASE}/v1/profiles"
    resp = requests.get(url, headers=_wise_headers(), timeout=30)
    resp.raise_for_status()
    profiles = resp.json()
    if not profiles:
        raise RuntimeError("No Wise profiles returned from GET /v1/profiles")
    for p in profiles:
        if (p.get("type") or "").upper() == "PERSONAL":
            return int(p["id"])
    return int(profiles[0]["id"])


def _pick_payment_option(quote: dict) -> dict | None:
    """Choose enabled BANK_TRANSFER payIn option; else first enabled."""
    options = quote.get("paymentOptions") or []
    preferred_pay_in = (quote.get("preferredPayIn") or "BANK_TRANSFER").upper()
    preferred_pay_out = (quote.get("payOut") or "BANK_TRANSFER").upper()
    candidates = []
    for opt in options:
        if opt.get("disabled"):
            continue
        candidates.append(opt)
    for opt in candidates:
        if (opt.get("payIn") or "").upper() == preferred_pay_in and (
            opt.get("payOut") or ""
        ).upper() == preferred_pay_out:
            return opt
    for opt in candidates:
        if (opt.get("payIn") or "").upper() == "BANK_TRANSFER":
            return opt
    return candidates[0] if candidates else None


def _fee_total_myr_from_option(opt: dict) -> float:
    fee = opt.get("fee") or {}
    total = fee.get("total")
    if total is not None:
        return float(total)
    price = opt.get("price") or {}
    pt = price.get("total") or {}
    val = pt.get("value") or {}
    amt = val.get("amount")
    if amt is not None:
        return float(amt)
    return 0.0


def _wise_quote_from_json(
    quote: dict,
    *,
    profile_id: int | None,
    source_label: str,
    fee_note: str,
) -> dict:
    opt = _pick_payment_option(quote)
    if not opt:
        raise RuntimeError("No enabled paymentOptions in Wise quote response")

    rate = float(quote.get("rate") or 0)
    if rate <= 0:
        raise RuntimeError("Wise quote missing positive rate")

    fee_total = _fee_total_myr_from_option(opt)
    target_amount = float(opt.get("targetAmount") or quote.get("targetAmount") or 0)
    source_amount = float(opt.get("sourceAmount") or quote.get("sourceAmount") or 0)

    ts = datetime.now(timezone.utc)
    return {
        "timestamp": ts.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "session": session_for(ts),
        "source": source_label,
        "source_currency": "MYR",
        "target_currency": "USD",
        "source_amount": source_amount,
        "target_amount": target_amount,
        "wise_rate": rate,
        "fee_total_myr": fee_total,
        "fee_variable_myr": None,
        "fee_fixed_myr": None,
        "fee_note": fee_note,
        "wise_quote_id": quote.get("id"),
        "wise_profile_id": profile_id,
        "wise_pay_in": opt.get("payIn"),
        "wise_pay_out": opt.get("payOut"),
        "mid_rate_at_quote": None,
    }


def fetch_wise_api(amount_myr: float, profile_id: int) -> dict:
    """
    POST /v3/profiles/{profileId}/quotes — fees and rate from API response.
    If the platform returns 401 (mustBeAuthenticated), fall back to
    POST /v3/quotes (unauthenticated illustrative quote; see Wise API docs).
    """
    body = {
        "sourceCurrency": "MYR",
        "targetCurrency": "USD",
        "sourceAmount": amount_myr,
        "preferredPayIn": "BANK_TRANSFER",
    }
    url = f"{WISE_API_BASE}/v3/profiles/{profile_id}/quotes"
    resp = requests.post(url, headers=_wise_headers(), json=body, timeout=45)

    if resp.status_code == 401:
        pub = requests.post(
            f"{WISE_API_BASE}/v3/quotes",
            headers={"Content-Type": "application/json"},
            json=body,
            timeout=45,
        )
        if not pub.ok:
            raise RuntimeError(
                f"Wise quote API 401; public /v3/quotes then {pub.status_code}: "
                f"{pub.text[:500]}"
            )
        quote = pub.json()
        return _wise_quote_from_json(
            quote,
            profile_id=None,
            source_label="wise_api_public",
            fee_note=(
                "unauthenticated POST /v3/quotes (fallback when profile quote returns 401)"
            ),
        )

    if not resp.ok:
        raise RuntimeError(f"Wise quote API {resp.status_code}: {resp.text[:500]}")
    quote = resp.json()
    return _wise_quote_from_json(
        quote,
        profile_id=profile_id,
        source_label="wise_api",
        fee_note="from Wise API paymentOptions fee total",
    )


def fetch_wise_scrape(amount_myr: float) -> dict:
    """从 wise.com 网页提取 MYR→USD 汇率（无需 API token）。"""
    url = f"{WISE_RATE_PAGE}?amount={amount_myr:.0f}"
    ts = datetime.now(timezone.utc)
    resp = requests.get(url, headers=WISE_HEADERS, timeout=15)
    resp.raise_for_status()

    match = re.search(r'"rate"\s*:\s*([\d.]+)', resp.text)
    if not match:
        raise ValueError("Rate JSON not found in wise.com page HTML")

    wise_rate = float(match.group(1))   # 1 MYR → USD（Wise 执行汇率）
    fee_variable = round(amount_myr * WISE_FEE_VARIABLE_PCT, 2)
    fee_total = round(WISE_FEE_FIXED_MYR + fee_variable, 2)
    target_amount = round((amount_myr - fee_total) * wise_rate, 2)

    return {
        "timestamp": ts.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "session": session_for(ts),
        "source": "wise_scrape",
        "source_currency": "MYR",
        "target_currency": "USD",
        "source_amount": amount_myr,
        "target_amount": target_amount,
        "wise_rate": wise_rate,
        "fee_total_myr": fee_total,
        "fee_variable_myr": fee_variable,
        "fee_fixed_myr": WISE_FEE_FIXED_MYR,
        "fee_note": "fee structure from wise.com/gb/pricing — verify before publish",
        "mid_rate_at_quote": None,
    }


def fetch_wise_manual(amount_myr: float) -> dict:
    """交互式 CLI：用户从 wise.com 查询后手动填入报价。"""
    ts = datetime.now(timezone.utc)
    print(f"\n  Manual input — Wise MYR→USD, amount: RM {amount_myr:,.0f}")
    print("  请打开 https://wise.com/send-money/ 输入金额后填入以下信息:\n")
    rate_str = input("  Exchange rate (1 MYR → USD, e.g. 0.2485): ").strip()
    fee_str = input("  Total fee (MYR, e.g. 61.5): ").strip()
    target_str = input("  Recipient receives (USD): ").strip()

    rate = float(rate_str)
    fee_total = float(fee_str) if fee_str else 0.0
    target = float(target_str) if target_str else round((amount_myr - fee_total) * rate, 2)

    return {
        "timestamp": ts.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "session": session_for(ts),
        "source": "wise_manual",
        "source_currency": "MYR",
        "target_currency": "USD",
        "source_amount": amount_myr,
        "target_amount": target,
        "wise_rate": rate,
        "fee_total_myr": fee_total,
        "fee_variable_myr": None,
        "fee_fixed_myr": None,
        "fee_note": "manually recorded from wise.com",
        "mid_rate_at_quote": None,
    }


def run(amounts: list, loops: int = 1, wait_sec: int = 0, mode: str = "scrape") -> None:
    section("M1 Wise — collect.py")
    strict = os.environ.get("STRICT_AUTO", "").lower() in ("1", "true", "yes")
    profile_id: int | None = None
    if mode == "api":
        profile_id = wise_get_profile_id()
        print(f"  Using Wise profile_id={profile_id} (api.wise.com)")

    for loop_i in range(loops):
        if loops > 1:
            print(f"\n── Loop {loop_i + 1}/{loops} ──")

        print("Fetching Frankfurter mid-rate...")
        mid = fetch_mid_rate("MYR", "USD")
        append_jsonl(MID_RATES, mid)
        print(f"  mid: 1 MYR = {mid['mid_rate']:.6f} USD  [{mid['timestamp']}]")

        for amount in amounts:
            print(f"\nFetching Wise quote for RM {amount:,.0f}  (mode={mode})...")
            try:
                if mode == "manual":
                    quote = fetch_wise_manual(amount)
                elif mode == "api":
                    assert profile_id is not None
                    quote = fetch_wise_api(amount, profile_id)
                else:
                    try:
                        quote = fetch_wise_scrape(amount)
                    except Exception as e:
                        if strict:
                            raise RuntimeError(
                                f"Wise scrape failed and STRICT_AUTO is set: {e}"
                            ) from e
                        print(f"  Scrape failed ({e}). Falling back to manual.")
                        quote = fetch_wise_manual(amount)

                quote["mid_rate_at_quote"] = mid["mid_rate"]
                append_jsonl(RAW_QUOTES, quote)
                print(f"  wise_rate  : {quote['wise_rate']:.6f} USD/MYR")
                print(f"  target_amt : USD {quote['target_amount']:,.2f}")
                print(f"  fee_total  : RM {quote['fee_total_myr']:.2f}")
            except Exception as e:
                print(f"  ERROR: {e}")
                if strict:
                    sys.exit(1)

        if loop_i < loops - 1:
            print(f"\nWaiting {wait_sec}s before next sample...")
            time.sleep(wait_sec)

    print(f"\nDone. Raw quotes -> {RAW_QUOTES}")
    print(f"       Mid rates  -> {MID_RATES}")


def main():
    parser = argparse.ArgumentParser(description="Fetch Wise MYR→USD quotes.")
    parser.add_argument(
        "--mode",
        choices=["api", "scrape", "manual"],
        default="scrape",
        help="api: Wise API (WISE_API_TOKEN); scrape: wise.com HTML; manual: CLI",
    )
    parser.add_argument("--amount", type=float, action="append",
                        help="Amount in MYR (repeatable). Default: 10000 50000")
    parser.add_argument("--loop", type=int, default=1,
                        help="Sampling loops (use for spread stability study).")
    parser.add_argument("--wait", type=int, default=3600,
                        help="Wait seconds between loops. Default: 3600 (1h)")
    args = parser.parse_args()
    amounts = args.amount if args.amount else [10000.0, 50000.0]
    run(amounts=amounts, loops=args.loop, wait_sec=args.wait, mode=args.mode)


if __name__ == "__main__":
    main()
