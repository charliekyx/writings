"""
m4_sg_hop/clean.py
───────────────────
将 SG Hop 费用数据标准化，计算三段式全成本（MYR 跨境 + FX + USD Wire）。

用法:
    python clean.py

输出:
    data/m4_sg_hop/hop_clean.csv
"""

import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))
from utils import fetch_mid_rate, section

DATA_DIR = Path(__file__).parent.parent.parent / "data" / "m4_sg_hop"
FEE_SCHEDULE = DATA_DIR / "fee_schedule.jsonl"
CLEAN_CSV = DATA_DIR / "hop_clean.csv"


def clean() -> pd.DataFrame:
    section("M4 SG Hop — clean.py")
    if not FEE_SCHEDULE.exists():
        print(f"No data at {FEE_SCHEDULE}. Run collect.py first.")
        sys.exit(1)

    rows = []
    with open(FEE_SCHEDULE, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))

    df = pd.DataFrame(rows)
    print(f"Loaded {len(df)} records.")
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)

    # Leg 1 成本 (MYR) — 跨境转账费
    df["leg1_cost_myr"] = df["leg1_fee_myr"].fillna(0.0)

    # Leg 2 FX spread 成本 (MYR 等价)
    df["leg2_fx_cost_myr"] = (
        df["leg2_fx_spread_pct"] / 100 * df["source_amount_myr"]
    ).fillna(0.0)

    # Leg 2 Wire fee (SGD → MYR 转换)
    # 用 mid_rate_myr_sgd: 1 MYR = X SGD → 1 SGD = 1/X MYR
    if "mid_rate_myr_sgd" not in df.columns or df["mid_rate_myr_sgd"].isna().all():
        fallback = fetch_mid_rate("MYR", "SGD")["mid_rate"]
        df["mid_rate_myr_sgd"] = fallback
    sgd_to_myr = 1.0 / df["mid_rate_myr_sgd"]
    df["leg2_wire_cost_myr"] = df["leg2_wire_fee_sgd"].fillna(0.0) * sgd_to_myr

    # 中间行费用 (USD → MYR)
    df["intermediary_cost_myr"] = (
        df["leg2_intermediary_usd"].fillna(25.0) / df["mid_rate_at_quote"]
    )

    # 总成本
    df["total_cost_myr"] = (
        df["leg1_cost_myr"]
        + df["leg2_fx_cost_myr"]
        + df["leg2_wire_cost_myr"]
        + df["intermediary_cost_myr"]
    )

    df["total_cost_pct"] = (
        df["total_cost_myr"] / df["source_amount_myr"] * 100
    ).round(4)

    df["fx_spread_pct"] = df["leg2_fx_spread_pct"].fillna(0.0)

    cols = [
        "timestamp", "session", "bank", "source_amount_myr",
        "leg1_cost_myr", "leg2_fx_cost_myr", "leg2_wire_cost_myr",
        "intermediary_cost_myr", "total_cost_myr", "total_cost_pct",
        "fx_spread_pct", "swift_mode", "mid_rate_at_quote",
    ]
    df = df[[c for c in cols if c in df.columns]]
    df.to_csv(CLEAN_CSV, index=False)
    print(f"Clean CSV saved: {CLEAN_CSV}")
    print(df[["bank", "source_amount_myr", "total_cost_pct", "swift_mode"]].to_string(index=False))
    return df


if __name__ == "__main__":
    clean()
