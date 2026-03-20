"""
m3_bank_tt/analyze.py
──────────────────────
分析银行 TT 成本：与 Wise 对比，量化"选银行的代价"。

用法:
    python analyze.py

输出:
    data/m3_bank_tt/analysis.csv
    data/m3_bank_tt/summary.txt
"""

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))
from utils import section

DATA_DIR = Path(__file__).parent.parent.parent / "data" / "m3_bank_tt"
M1_CLEAN = Path(__file__).parent.parent.parent / "data" / "m1_wise" / "quotes_clean.csv"
CLEAN_CSV = DATA_DIR / "rates_clean.csv"
ANALYSIS_CSV = DATA_DIR / "analysis.csv"
SUMMARY_TXT = DATA_DIR / "summary.txt"


def analyze():
    section("M3 Bank TT — analyze.py")
    if not CLEAN_CSV.exists():
        print(f"No clean data at {CLEAN_CSV}. Run clean.py first.")
        sys.exit(1)

    df = pd.read_csv(CLEAN_CSV, parse_dates=["timestamp"])

    # 按银行和金额分组汇总
    summary = (
        df.groupby(["bank", "source_amount"])
        .agg(
            spread_mean=("spread_pct", "mean"),
            all_in_sha_mean=("all_in_sha_pct", "mean"),
            all_in_sha_max=("all_in_sha_pct", "max"),
            count=("spread_pct", "count"),
        )
        .round(4)
        .reset_index()
    )
    summary.to_csv(ANALYSIS_CSV, index=False)
    print(f"Analysis CSV saved: {ANALYSIS_CSV}")

    # 对比 Wise（若有数据）
    lines = ["Bank TT Cost Analysis\n"]
    if M1_CLEAN.exists():
        wise = pd.read_csv(M1_CLEAN, parse_dates=["timestamp"])
        for _, row in summary.iterrows():
            amount = row["source_amount"]
            wrow = wise[wise["source_amount"] == amount]
            wise_cost = wrow["all_in_cost_pct"].mean() if not wrow.empty else None
            lines.append(f"Bank: {row['bank']} | RM {amount:,.0f}")
            lines.append(f"  Bank all-in (SHA): {row['all_in_sha_mean']:.3f}%")
            if wise_cost is not None:
                diff = row["all_in_sha_mean"] - wise_cost
                myr_cost = diff / 100 * amount
                lines.append(f"  Wise all-in      : {wise_cost:.3f}%")
                lines.append(f"  Extra cost vs Wise: {diff:.3f}% = RM {myr_cost:.2f}")
            lines.append("")
    else:
        for _, row in summary.iterrows():
            lines.append(f"Bank: {row['bank']} | RM {row['source_amount']:,.0f}")
            lines.append(f"  spread: {row['spread_mean']:.3f}% | all-in SHA: {row['all_in_sha_mean']:.3f}%")
            lines.append("")

    text = "\n".join(lines)
    SUMMARY_TXT.write_text(text, encoding="utf-8")
    print(f"Summary saved: {SUMMARY_TXT}")
    print(text)


if __name__ == "__main__":
    analyze()
