"""
m3_bank_tt/clean.py
────────────────────
将 raw_rates.jsonl 标准化，计算银行 TT 的 spread 和三种费控模式下的全成本。

用法:
    python clean.py

输出:
    data/m3_bank_tt/rates_clean.csv
"""

import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))
from utils import section

DATA_DIR = Path(__file__).parent.parent.parent / "data" / "m3_bank_tt"
RAW_RATES = DATA_DIR / "raw_rates.jsonl"
CLEAN_CSV = DATA_DIR / "rates_clean.csv"

# SWIFT 中间行费用假设范围（USD）
INTERMEDIARY_LOW = 0.0
INTERMEDIARY_MID = 25.0
INTERMEDIARY_HIGH = 35.0


def clean() -> pd.DataFrame:
    section("M3 Bank TT — clean.py")
    if not RAW_RATES.exists():
        print(f"No raw data at {RAW_RATES}. Run collect.py first.")
        sys.exit(1)

    rows = []
    with open(RAW_RATES, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))

    df = pd.DataFrame(rows)
    print(f"Loaded {len(df)} raw records.")
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)

    # tt_selling_rate 是银行报价的 1 USD = X MYR
    # 转换成 1 MYR = X USD 以便与 mid_rate 对比
    df["bank_rate_myr_per_usd"] = df["tt_selling_rate"]
    df["bank_rate_usd_per_myr"] = 1.0 / df["tt_selling_rate"]

    # spread_pct: 相对 mid（mid_rate 是 1 MYR = X USD）
    df["spread_pct"] = (
        (df["mid_rate_at_quote"] - df["bank_rate_usd_per_myr"]) / df["mid_rate_at_quote"] * 100
    ).round(4)

    # 三种费控模式下的全成本（以 source_amount_myr 为分母）
    # mid 对价的 USD = source_amount * mid_rate
    df["mid_usd"] = df["source_amount"] * df["mid_rate_at_quote"]

    # OUR: sender pays all intermediary fees (sender pays extra)
    df["intermediary_myr_low"] = INTERMEDIARY_LOW / df["mid_rate_at_quote"]
    df["intermediary_myr_mid"] = INTERMEDIARY_MID / df["mid_rate_at_quote"]
    df["intermediary_myr_high"] = INTERMEDIARY_HIGH / df["mid_rate_at_quote"]

    def all_in(row, intermediary_myr):
        """总成本 = spread_pct + (wire_fee + intermediary) / source_amount * 100"""
        total_fee = row["total_fixed_fee_myr"] + intermediary_myr
        return round(row["spread_pct"] + total_fee / row["source_amount"] * 100, 4)

    df["all_in_our_pct"] = df.apply(
        lambda r: all_in(r, r["intermediary_myr_low"]), axis=1)  # OUR: no intermediary cut from receiver
    df["all_in_sha_pct"] = df.apply(
        lambda r: all_in(r, r["intermediary_myr_mid"]), axis=1)  # SHA: $25 mid estimate
    df["all_in_ben_pct"] = df.apply(
        lambda r: all_in(r, r["intermediary_myr_high"]), axis=1)  # BEN: $35 high estimate

    cols = [
        "timestamp", "session", "bank", "source_amount",
        "mid_rate_at_quote", "bank_rate_usd_per_myr",
        "spread_pct", "wire_fee_myr", "cable_fee_myr", "total_fixed_fee_myr",
        "all_in_our_pct", "all_in_sha_pct", "all_in_ben_pct",
    ]
    df = df[[c for c in cols if c in df.columns]]
    df.to_csv(CLEAN_CSV, index=False)
    print(f"Clean CSV saved: {CLEAN_CSV}")
    print(df[["timestamp", "bank", "source_amount", "spread_pct",
               "all_in_sha_pct"]].to_string(index=False))
    return df


if __name__ == "__main__":
    clean()
