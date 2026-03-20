"""
m1_wise/clean.py
────────────────
将 raw_quotes.jsonl 标准化为 CSV，计算 implied_rate 和 spread_pct。

用法:
    python clean.py

输出:
    data/m1_wise/quotes_clean.csv
"""

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))
from utils import section

DATA_DIR = Path(__file__).parent.parent.parent / "data" / "m1_wise"
RAW_QUOTES = DATA_DIR / "raw_quotes.jsonl"
CLEAN_CSV = DATA_DIR / "quotes_clean.csv"


def clean() -> pd.DataFrame:
    section("M1 Wise — clean.py")

    if not RAW_QUOTES.exists():
        print(f"No raw data found at {RAW_QUOTES}. Run collect.py first.")
        sys.exit(1)

    rows = []
    with open(RAW_QUOTES, encoding="utf-8") as f:
        import json
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))

    df = pd.DataFrame(rows)
    print(f"Loaded {len(df)} raw records.")

    # 转换 timestamp
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)

    # 计算 implied_rate:
    # Wise 直接给出了 wise_rate (1 MYR → USD)，也等价于：
    # implied_rate = target_amount / (source_amount - fee_total_myr)
    # 两种方法交叉验证
    df["implied_rate_direct"] = df["wise_rate"]
    df["implied_rate_calc"] = (
        df["target_amount"] / (df["source_amount"] - df["fee_total_myr"])
    ).round(6)

    # spread_pct: 相对 mid，正值表示 Wise 报价比 mid 差
    # spread_pct = (mid_rate - wise_rate) / mid_rate * 100
    df["spread_pct"] = (
        (df["mid_rate_at_quote"] - df["wise_rate"]) / df["mid_rate_at_quote"] * 100
    ).round(4)

    # all_in_cost_pct: 含固定费的全成本占 source_amount 的百分比
    df["all_in_cost_pct"] = (
        (df["fee_total_myr"] / df["source_amount"] * 100
         + df["spread_pct"])
    ).round(4)

    # 保留核心列
    cols = [
        "timestamp", "session", "source_amount", "target_amount",
        "mid_rate_at_quote", "wise_rate", "implied_rate_calc",
        "fee_total_myr", "fee_fixed_myr", "fee_variable_myr",
        "spread_pct", "all_in_cost_pct",
    ]
    df = df[cols]
    df.to_csv(CLEAN_CSV, index=False)
    print(f"Clean CSV saved: {CLEAN_CSV}  ({len(df)} rows)")
    print(df[["timestamp", "source_amount", "spread_pct", "all_in_cost_pct"]].to_string(index=False))
    return df


if __name__ == "__main__":
    clean()
