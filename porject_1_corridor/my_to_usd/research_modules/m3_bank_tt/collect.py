"""
m3_bank_tt/collect.py
───────────────────────
收集银行零售 TT 汇率。
支持两种模式：
  --mode scrape : 尝试从银行官网抓取牌告汇率
  --mode manual : 交互式 CLI 手动输入（推荐，更准确）

支持的银行:
  maybank   : https://www.maybank2u.com.my/maybank2u/malaysia/en/personal/rates/foreign_exchange_rates.page
  cimb      : https://www.cimb.com.my/en/personal/rates-and-charges/foreign-exchange-rates.html

用法:
    python collect.py --mode manual --bank maybank
    python collect.py --mode manual --bank cimb
    python collect.py --mode scrape --bank maybank

输出:
    data/m3_bank_tt/raw_rates.jsonl
"""

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests
from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).parent.parent))
from utils import append_jsonl, fetch_mid_rate, section, session_for

DATA_DIR = Path(__file__).parent.parent.parent / "data" / "m3_bank_tt"
DATA_DIR.mkdir(parents=True, exist_ok=True)
RAW_RATES = DATA_DIR / "raw_rates.jsonl"

BANK_URLS = {
    "maybank": "https://www.maybank2u.com.my/maybank2u/malaysia/en/personal/rates/foreign_exchange_rates.page",
    "cimb": "https://www.cimb.com.my/en/personal/rates-and-charges/foreign-exchange-rates.html",
}

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    )
}


def scrape_bank_rate(bank: str) -> float | None:
    """
    尝试从银行官网抓取 MYR/USD TT Selling 汇率。
    银行网页频繁重构，失败时返回 None。
    """
    url = BANK_URLS.get(bank)
    if not url:
        return None
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        # 通用策略：找包含 "USD" 和数字的表格行
        for row in soup.find_all("tr"):
            cells = [td.get_text(strip=True) for td in row.find_all("td")]
            if any("USD" in c for c in cells):
                # TT Selling 通常是第3或第4列
                for c in cells:
                    try:
                        val = float(c.replace(",", ""))
                        if 0.20 < val < 0.30:   # MYR/USD TT selling 合理范围
                            return val
                    except ValueError:
                        pass
        return None
    except Exception as e:
        print(f"  Scrape failed for {bank}: {e}")
        return None


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
        "tt_selling_rate": tt_selling,  # 1 USD = X MYR (银行报价，>mid 表示贵)
        "wire_fee_myr": wire_fee,
        "cable_fee_myr": cable_fee,
        "total_fixed_fee_myr": wire_fee + cable_fee,
        "mid_rate_at_quote": None,
    }


def run(bank: str, amounts: list, mode: str = "manual") -> None:
    section("M3 Bank TT — collect.py")
    print(f"Bank: {bank.upper()} | Mode: {mode}")

    print("\nFetching mid-rate...")
    mid = fetch_mid_rate("MYR", "USD")
    print(f"  mid: 1 MYR = {mid['mid_rate']:.6f} USD  [{mid['timestamp']}]")

    # 如果是 scrape 模式，先尝试自动
    scraped_rate = None
    if mode == "scrape":
        print(f"\nScraping {bank.upper()} rate...")
        scraped_rate = scrape_bank_rate(bank)
        if scraped_rate:
            print(f"  Scraped TT Selling Rate (USD/MYR): {scraped_rate:.4f}")
        else:
            print("  Scrape failed. Falling back to manual.")

    for amount in amounts:
        if scraped_rate and mode == "scrape":
            ts = datetime.now(timezone.utc)
            # scrape 模式只拿到汇率，费用需要手动填
            wire_fee_str = input(f"  Wire fee for RM {amount:,.0f} (MYR): ").strip()
            wire_fee = float(wire_fee_str) if wire_fee_str else 0.0
            record = {
                "timestamp": ts.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "session": session_for(ts),
                "bank": bank,
                "source": "scrape",
                "source_amount": amount,
                "tt_selling_rate": scraped_rate,
                "wire_fee_myr": wire_fee,
                "cable_fee_myr": 0.0,
                "total_fixed_fee_myr": wire_fee,
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
