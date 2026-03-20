"""
m1_wise/analyze.py
──────────────────
对清洗后的数据做统计分析:
  - 按金额分层: RM 10k vs RM 50k 的 spread、cost 对比
  - 按交易时段: Asia / Europe / US 的 spread 稳定性
  - 摘要统计: mean / std / min / max

用法:
    python analyze.py

输出:
    data/m1_wise/spread_analysis.csv    (按金额 + 时段分组的汇总)
    data/m1_wise/summary.txt            (人类可读摘要，可直接引用进文章)
    console 打印
"""

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))
from utils import section

DATA_DIR = Path(__file__).parent.parent.parent / "data" / "m1_wise"
CLEAN_CSV = DATA_DIR / "quotes_clean.csv"
ANALYSIS_CSV = DATA_DIR / "spread_analysis.csv"
SUMMARY_TXT = DATA_DIR / "summary.txt"

# 断言边界：合理的 Wise MYR→USD spread 范围
SPREAD_MIN = 0.0
SPREAD_MAX = 2.0   # 超过 2% 则数据可疑


def analyze() -> pd.DataFrame:
    section("M1 Wise — analyze.py")

    if not CLEAN_CSV.exists():
        print(f"No clean data at {CLEAN_CSV}. Run clean.py first.")
        sys.exit(1)

    df = pd.read_csv(CLEAN_CSV, parse_dates=["timestamp"])
    print(f"Loaded {len(df)} rows from {CLEAN_CSV}")

    # ── 断言检查 ──────────────────────────────────────────────────────────
    bad = df[(df["spread_pct"] < SPREAD_MIN) | (df["spread_pct"] > SPREAD_MAX)]
    if not bad.empty:
        print(f"WARNING: {len(bad)} row(s) have spread_pct outside "
              f"[{SPREAD_MIN}, {SPREAD_MAX}]. Check data:")
        print(bad[["timestamp", "source_amount", "spread_pct"]])

    # ── 整体摘要 ──────────────────────────────────────────────────────────
    print("\n── Overall spread_pct summary ──")
    overall = df["spread_pct"].describe().round(4)
    print(overall)

    # ── 按金额分组 ────────────────────────────────────────────────────────
    print("\n── By source_amount ──")
    by_amount = (
        df.groupby("source_amount")["spread_pct"]
        .agg(["mean", "std", "min", "max", "count"])
        .round(4)
    )
    print(by_amount)

    # ── 按交易时段分组 ────────────────────────────────────────────────────
    print("\n── By session (Asia / Europe / US) ──")
    by_session = (
        df.groupby("session")["spread_pct"]
        .agg(["mean", "std", "min", "max", "count"])
        .round(4)
    )
    print(by_session)

    # ── 按金额 + 时段 ─────────────────────────────────────────────────────
    by_both = (
        df.groupby(["source_amount", "session"])["spread_pct"]
        .agg(["mean", "std", "min", "max", "count"])
        .round(4)
        .reset_index()
    )
    by_both.to_csv(ANALYSIS_CSV, index=False)
    print(f"\nAnlaysis CSV saved: {ANALYSIS_CSV}")

    # ── all_in_cost_pct (含固定费) ────────────────────────────────────────
    print("\n── all_in_cost_pct (spread + fee) by amount ──")
    cost_summary = (
        df.groupby("source_amount")["all_in_cost_pct"]
        .agg(["mean", "std", "min", "max"])
        .round(4)
    )
    print(cost_summary)

    # ── 生成人类可读摘要 ──────────────────────────────────────────────────
    lines = []
    lines.append("Wise MYR→USD Spread Analysis")
    lines.append(f"Total samples: {len(df)}")
    lines.append("")
    for amt, grp in df.groupby("source_amount"):
        mean_s = grp["spread_pct"].mean()
        std_s = grp["spread_pct"].std()
        mean_c = grp["all_in_cost_pct"].mean()
        lines.append(f"RM {amt:,.0f}:")
        lines.append(f"  spread_pct   = {mean_s:.3f}% (±{std_s:.3f}%)")
        lines.append(f"  all_in_cost  = {mean_c:.3f}% vs mid")
        lines.append(f"  Sessions: {', '.join(grp['session'].unique())}")
        lines.append("")

    summary_text = "\n".join(lines)
    SUMMARY_TXT.write_text(summary_text, encoding="utf-8")
    print(f"\nSummary saved: {SUMMARY_TXT}")
    print(summary_text)

    return by_both


if __name__ == "__main__":
    analyze()
