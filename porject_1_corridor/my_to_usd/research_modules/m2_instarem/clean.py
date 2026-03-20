"""
m2_instarem/clean.py + analyze.py + chart.py — combined helper
────────────────────────────────────────────────────────────────
clean:
  raw_quotes.jsonl → quotes_clean.csv  (含 spread_pct, all_in_cost_pct)

analyze:
  比较 Wise vs Instarem 在同一时刻（或最近时间点）的成本

chart:
  双路由成本对比柱状图

用法:
    python clean.py
    python analyze.py
    python chart.py
"""

# ── clean.py ────────────────────────────────────────────────────────────────
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))
from utils import section

DATA_DIR = Path(__file__).parent.parent.parent / "data" / "m2_instarem"
RAW_QUOTES = DATA_DIR / "raw_quotes.jsonl"
CLEAN_CSV = DATA_DIR / "quotes_clean.csv"


def clean() -> pd.DataFrame:
    section("M2 Instarem — clean.py")
    if not RAW_QUOTES.exists():
        print(f"No raw data at {RAW_QUOTES}. Run collect.py first.")
        sys.exit(1)

    import json
    rows = []
    with open(RAW_QUOTES, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))

    df = pd.DataFrame(rows)
    print(f"Loaded {len(df)} raw records.")
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)

    # spread_pct = (mid - instarem_rate) / mid * 100
    # instarem_rate 是 1 MYR → USD 的执行汇率
    df["spread_pct"] = (
        (df["mid_rate_at_quote"] - df["instarem_rate"]) / df["mid_rate_at_quote"] * 100
    ).round(4)

    df["all_in_cost_pct"] = (
        df["spread_pct"] + df["fee_total_myr"] / df["source_amount"] * 100
    ).round(4)

    cols = [
        "timestamp", "session", "source", "source_amount", "target_amount",
        "mid_rate_at_quote", "instarem_rate", "fee_total_myr",
        "spread_pct", "all_in_cost_pct",
    ]
    df = df[cols]
    df.to_csv(CLEAN_CSV, index=False)
    print(f"Clean CSV saved: {CLEAN_CSV}")
    print(df[["timestamp", "source_amount", "spread_pct", "all_in_cost_pct"]].to_string(index=False))
    return df


if __name__ == "__main__":
    clean()
