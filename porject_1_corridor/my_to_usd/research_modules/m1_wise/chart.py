"""
m1_wise/chart.py
────────────────
生成 Wise MYR→USD spread 随时间变化的折线图（带交易时段背景色）。

用法:
    python chart.py

输出:
    charts/m1_wise_spread_over_time.png
"""

import sys
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))
from utils import save_chart, section

DATA_DIR = Path(__file__).parent.parent.parent / "data" / "m1_wise"
CLEAN_CSV = DATA_DIR / "quotes_clean.csv"

SESSION_COLORS = {
    "Asia": "#e8f4f8",
    "Europe": "#fff8e1",
    "US": "#f3e5f5",
}


def chart():
    section("M1 Wise — chart.py")

    if not CLEAN_CSV.exists():
        print(f"No clean data at {CLEAN_CSV}. Run collect.py + clean.py first.")
        sys.exit(1)

    df = pd.read_csv(CLEAN_CSV, parse_dates=["timestamp"])
    df = df.sort_values("timestamp")

    amounts = sorted(df["source_amount"].unique())
    n = len(amounts)

    fig, axes = plt.subplots(n, 1, figsize=(12, 4 * n), sharex=False)
    if n == 1:
        axes = [axes]

    fig.suptitle("Wise MYR→USD Spread vs Mid-Market Rate\n(by source amount & trading session)",
                 fontsize=14, fontweight="bold", y=1.01)

    for ax, amount in zip(axes, amounts):
        sub = df[df["source_amount"] == amount].copy()

        # 画 spread_pct 折线
        ax.plot(sub["timestamp"], sub["spread_pct"],
                marker="o", markersize=5, linewidth=1.5,
                color="#1565C0", label="spread_pct")

        # 交易时段背景
        for _, row in sub.iterrows():
            color = SESSION_COLORS.get(row["session"], "#f5f5f5")
            ax.axvspan(row["timestamp"] - pd.Timedelta(minutes=15),
                       row["timestamp"] + pd.Timedelta(minutes=15),
                       alpha=0.3, color=color)

        # 均值基准线
        mean_val = sub["spread_pct"].mean()
        ax.axhline(mean_val, linestyle="--", color="#B71C1C", linewidth=1,
                   label=f"Mean {mean_val:.3f}%")

        ax.set_title(f"RM {amount:,.0f}", fontsize=12)
        ax.set_ylabel("Spread vs Mid (%)")
        ax.set_xlabel("Timestamp (UTC)")
        ax.grid(True, alpha=0.3)
        ax.legend(loc="upper right", fontsize=9)

        # 标注每个点的时段
        for _, row in sub.iterrows():
            ax.annotate(row["session"][0],  # 首字母: A/E/U
                        xy=(row["timestamp"], row["spread_pct"]),
                        xytext=(0, 8), textcoords="offset points",
                        fontsize=7, color="#555555", ha="center")

    # 图例说明时段颜色
    legend_patches = [
        mpatches.Patch(color=c, alpha=0.5, label=s)
        for s, c in SESSION_COLORS.items()
    ]
    fig.legend(handles=legend_patches, loc="lower center", ncol=3,
               title="Session", fontsize=9, bbox_to_anchor=(0.5, -0.02))

    plt.tight_layout()
    save_chart(fig, "m1_wise_spread_over_time")


if __name__ == "__main__":
    chart()
