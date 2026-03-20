"""
m7_reddit/analyze.py
─────────────────────
路由提及频率 × 年份趋势分析。

用法:
    python analyze.py

输出:
    data/m7_reddit/route_trend_summary.csv
    console 打印
"""

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))
from utils import section

DATA_DIR = Path(__file__).parent.parent.parent / "data" / "m7_reddit"
ROUTE_CSV = DATA_DIR / "route_mentions_by_year.csv"
TREND_CSV = DATA_DIR / "route_trend_summary.csv"


def analyze() -> None:
    section("M7 Reddit — analyze.py")
    if not ROUTE_CSV.exists():
        print(f"No data at {ROUTE_CSV}. Run clean.py first.")
        sys.exit(1)

    df = pd.read_csv(ROUTE_CSV)
    df = df[df["year"] < 9000]  # 过滤无年份记录

    # 按路由统计总提及
    total = df.groupby("route")["mentions"].sum().sort_values(ascending=False)
    print("\n── Total route mentions (all years) ──")
    print(total.to_string())

    # 年份趋势（宽表）
    pivot = df.pivot_table(index="year", columns="route", values="mentions",
                           aggfunc="sum", fill_value=0)
    pivot.to_csv(TREND_CSV)
    print(f"\nTrend pivot saved: {TREND_CSV}")

    # 逐年增速
    print("\n── Year-over-Year trend ──")
    print(pivot.to_string())

    # 识别热度上升最快的路由
    if len(pivot) >= 2:
        last_year = pivot.index.max()
        prev_year = pivot.index[-2] if len(pivot) >= 2 else last_year
        growth = (pivot.loc[last_year] - pivot.loc[prev_year]).sort_values(ascending=False)
        print(f"\n── Growth from {prev_year} to {last_year} ──")
        print(growth.to_string())


if __name__ == "__main__":
    analyze()
