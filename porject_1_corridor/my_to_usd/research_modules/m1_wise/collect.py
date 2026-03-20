"""
m1_wise/collect.py
──────────────────
获取 Wise MYR→USD 报价，同时记录 Frankfurter mid-rate 作为对照锚点。

Wise 全部 API 端点需要 auth token，无匿名接口。
本脚本采用两种策略:
  --mode scrape  : 从 wise.com 网页提取嵌入的汇率 JSON（无需 token）
                   费用按 wise.com pricing 页记录的结构估算
  --mode manual  : 交互式 CLI，从 wise.com 手动查询后填入（最可靠）

注意: 使用 --loop 参数可在同一天多个时段采样，用于 spread 稳定性研究。

用法:
    python collect.py                          # scrape 模式，默认两个金额
    python collect.py --mode manual            # 手动模式
    python collect.py --loop 3 --wait 3600     # 每小时采样一次，共 3 次

输出:
    data/m1_wise/raw_quotes.jsonl
    data/m1_wise/mid_rates.jsonl
"""

import argparse
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
                else:
                    try:
                        quote = fetch_wise_scrape(amount)
                    except Exception as e:
                        print(f"  Scrape failed ({e}). Falling back to manual.")
                        quote = fetch_wise_manual(amount)

                quote["mid_rate_at_quote"] = mid["mid_rate"]
                append_jsonl(RAW_QUOTES, quote)
                print(f"  wise_rate  : {quote['wise_rate']:.6f} USD/MYR")
                print(f"  target_amt : USD {quote['target_amount']:,.2f}")
                print(f"  fee_total  : RM {quote['fee_total_myr']:.2f}")
            except Exception as e:
                print(f"  ERROR: {e}")

        if loop_i < loops - 1:
            print(f"\nWaiting {wait_sec}s before next sample...")
            time.sleep(wait_sec)

    print(f"\nDone. Raw quotes -> {RAW_QUOTES}")
    print(f"       Mid rates  -> {MID_RATES}")


def main():
    parser = argparse.ArgumentParser(description="Fetch Wise MYR→USD quotes.")
    parser.add_argument("--mode", choices=["scrape", "manual"], default="scrape",
                        help="scrape: extract from wise.com page; manual: CLI input")
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
