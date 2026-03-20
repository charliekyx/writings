"""
m7_reddit/chart.py
───────────────────
路由热度时间轴图（stacked bar + line，按年份）。

用法:
    python chart.py

输出:
    charts/m7_reddit_trend.png
"""

import sys
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))
from utils import save_chart, section

DATA_DIR = Path(__file__).parent.parent.parent / "data" / "m7_reddit"
TREND_CSV = DATA_DIR / "route_trend_summary.csv"

# 路由颜色
ROUTE_COLORS = {
    "Wise": "#1565C0",
    "Revolut": "#6A1B9A",
    "CIMB SG": "#00695C",
    "HSBC Hop": "#E65100",
    "Maybank": "#1B5E20",
    "CIMB": "#0D47A1",
    "PayPal": "#0277BD",
    "Bank TT/SWIFT": "#BF360C",
    "Crypto": "#424242",
    "IDEALPRO": "#880E4F",
    "Instarem": "#2E7D32",
}


def chart() -> None:
    section("M7 Reddit — chart.py")
    if not TREND_CSV.exists():
        print(f"No data at {TREND_CSV}. Run analyze.py first.")
        sys.exit(1)

    df = pd.read_csv(TREND_CSV, index_col=0)
    df = df.loc[df.index < 9000]  # 过滤无年份
    df = df.sort_index()

    # 只保留总提及 >= 3 的路由，避免图太拥挤
    totals = df.sum(axis=0)
    routes_to_show = totals[totals >= 3].index.tolist()
    df = df[routes_to_show]

    years = df.index.tolist()
    colors = [ROUTE_COLORS.get(r, "#9E9E9E") for r in routes_to_show]

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 10))
    fig.suptitle("Reddit Discussion Trend: MYR→IBKR Route Mentions by Year",
                 fontsize=14, fontweight="bold")

    # ── Stacked bar ──
    bottom = [0] * len(years)
    for route, color in zip(routes_to_show, colors):
        vals = df[route].tolist()
        ax1.bar(years, vals, bottom=bottom, label=route, color=color, alpha=0.85)
        bottom = [b + v for b, v in zip(bottom, vals)]

    ax1.set_xlabel("Year")
    ax1.set_ylabel("Post/Comment Mentions")
    ax1.set_title("Stacked: All Routes", fontsize=11)
    ax1.legend(fontsize=8, loc="upper left", ncol=2)
    ax1.grid(True, axis="y", alpha=0.3)

    # ── Line chart — top routes ──
    top_routes = totals[routes_to_show].nlargest(5).index.tolist()
    for route in top_routes:
        color = ROUTE_COLORS.get(route, "#9E9E9E")
        ax2.plot(years, df[route], marker="o", label=route, color=color, linewidth=2)

    ax2.set_xlabel("Year")
    ax2.set_ylabel("Mentions")
    ax2.set_title("Line: Top 5 Routes", fontsize=11)
    ax2.legend(fontsize=9)
    ax2.grid(True, alpha=0.3)

    plt.tight_layout()
    save_chart(fig, "m7_reddit_trend")


if __name__ == "__main__":
    chart()
