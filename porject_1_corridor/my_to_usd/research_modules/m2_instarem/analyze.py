"""
m2_instarem/analyze.py
───────────────────────
将 Wise（M1）和 Instarem（M2）的数据合并对比。
对于每个 source_amount，找到时间最接近的一对报价进行比较。

用法:
    python analyze.py

输出:
    data/m2_instarem/comparison.csv
    console 打印
"""

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))
from utils import section

M1_CLEAN = Path(__file__).parent.parent.parent / "data" / "m1_wise" / "quotes_clean.csv"
M2_CLEAN = Path(__file__).parent.parent.parent / "data" / "m2_instarem" / "quotes_clean.csv"
DATA_DIR = Path(__file__).parent.parent.parent / "data" / "m2_instarem"
COMPARISON_CSV = DATA_DIR / "comparison.csv"


def analyze():
    section("M2 Instarem — analyze.py")

    if not M1_CLEAN.exists():
        print(f"M1 clean data not found: {M1_CLEAN}. Run M1 clean.py first.")
        sys.exit(1)
    if not M2_CLEAN.exists():
        print(f"M2 clean data not found: {M2_CLEAN}. Run M2 clean.py first.")
        sys.exit(1)

    wise = pd.read_csv(M1_CLEAN, parse_dates=["timestamp"])
    instarem = pd.read_csv(M2_CLEAN, parse_dates=["timestamp"])

    rows = []
    for amount in sorted(wise["source_amount"].unique()):
        w = wise[wise["source_amount"] == amount].sort_values("timestamp")
        i = instarem[instarem["source_amount"] == amount].sort_values("timestamp")
        if i.empty:
            print(f"  No Instarem data for RM {amount:,.0f}, skipping.")
            continue

        # 取每个 instarem 报价，匹配时间最近的 wise 报价
        for _, ir in i.iterrows():
            time_diffs = abs(w["timestamp"] - ir["timestamp"])
            closest_w = w.loc[time_diffs.idxmin()]
            rows.append({
                "amount_myr": amount,
                "wise_timestamp": closest_w["timestamp"],
                "instarem_timestamp": ir["timestamp"],
                "time_diff_min": (ir["timestamp"] - closest_w["timestamp"]).total_seconds() / 60,
                "wise_spread_pct": closest_w["spread_pct"],
                "instarem_spread_pct": ir["spread_pct"],
                "wise_all_in_pct": closest_w["all_in_cost_pct"],
                "instarem_all_in_pct": ir["all_in_cost_pct"],
                "diff_spread_pct": ir["spread_pct"] - closest_w["spread_pct"],
                "diff_all_in_pct": ir["all_in_cost_pct"] - closest_w["all_in_cost_pct"],
                "mid_rate": ir["mid_rate_at_quote"],
            })

    if not rows:
        print("No comparison data generated.")
        return

    df = pd.DataFrame(rows)
    df.to_csv(COMPARISON_CSV, index=False)
    print(f"\nComparison CSV saved: {COMPARISON_CSV}")

    print("\n── Wise vs Instarem (all_in_cost_pct) ──")
    for amt, grp in df.groupby("amount_myr"):
        print(f"\n  RM {amt:,.0f}:")
        print(f"    Wise     : {grp['wise_all_in_pct'].mean():.3f}% all-in")
        print(f"    Instarem : {grp['instarem_all_in_pct'].mean():.3f}% all-in")
        diff = grp["diff_all_in_pct"].mean()
        winner = "Wise" if diff > 0 else "Instarem"
        print(f"    Delta    : {abs(diff):.3f}% → {winner} cheaper")

    print("\n  NOTE: Compare only if |time_diff_min| < 60.")


if __name__ == "__main__":
    analyze()
