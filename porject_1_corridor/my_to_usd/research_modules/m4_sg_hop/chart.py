"""
m4_sg_hop/chart.py
───────────────────
生成 SG Hop 三段成本堆叠图 + 与 Wise 全成本对比。

用法:
    python chart.py

输出:
    charts/m4_sg_hop_comparison.png
"""

import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))
from utils import save_chart, section

DATA_DIR = Path(__file__).parent.parent.parent / "data" / "m4_sg_hop"
COMPARISON_CSV = DATA_DIR / "comparison.csv"
M1_CLEAN = Path(__file__).parent.parent.parent / "data" / "m1_wise" / "quotes_clean.csv"


def chart():
    section("M4 SG Hop — chart.py")
    if not COMPARISON_CSV.exists():
        print(f"No data at {COMPARISON_CSV}. Run analyze.py first.")
        sys.exit(1)

    df = pd.read_csv(COMPARISON_CSV)
    amounts = sorted(df["amount_myr"].unique())
    banks = sorted(df["bank"].unique())

    fig, axes = plt.subplots(1, len(amounts), figsize=(8 * len(amounts), 7), sharey=False)
    if len(amounts) == 1:
        axes = [axes]

    fig.suptitle("SG Hop — Full Cost Breakdown vs Wise",
                 fontsize=13, fontweight="bold")

    leg_cols = ["leg1_pct", "leg2_fx_pct", "leg2_wire_pct", "intermediary_pct"]
    leg_labels = ["Leg1: Cross-border", "Leg2: FX Spread", "Leg2: Wire Fee", "Intermediary"]
    leg_colors = ["#B3E5FC", "#0288D1", "#01579B", "#880E4F"]

    for ax, amount in zip(axes, amounts):
        sub = df[df["amount_myr"] == amount]
        x = np.arange(len(banks))
        width = 0.4
        bottoms = np.zeros(len(banks))

        for col, label, color in zip(leg_cols, leg_labels, leg_colors):
            vals = [sub[sub["bank"] == b][col].values[0] if not sub[sub["bank"] == b].empty else 0
                    for b in banks]
            ax.bar(x, vals, width, bottom=bottoms, label=label, color=color, alpha=0.9)
            bottoms += np.array(vals)

        # 顶部标注总成本
        for i, bank in enumerate(banks):
            total = sub[sub["bank"] == bank]["hop_total_pct"].values
            if len(total) > 0:
                ax.text(i, bottoms[i] + 0.01, f"{total[0]:.2f}%",
                        ha="center", va="bottom", fontsize=9, fontweight="bold")

        # Wise 基准线
        wise_row = sub.dropna(subset=["wise_all_in_pct"])
        if not wise_row.empty:
            wval = wise_row["wise_all_in_pct"].mean()
            ax.axhline(wval, linestyle="--", color="#B71C1C", linewidth=1.5,
                       label=f"Wise ({wval:.2f}%)")

        ax.set_title(f"RM {amount:,.0f}", fontsize=12)
        ax.set_xticks(x)
        ax.set_xticklabels([b.upper() for b in banks], fontsize=10)
        ax.set_ylabel("Cost (%)")
        ax.legend(fontsize=8, loc="upper right")
        ax.grid(True, axis="y", alpha=0.3)

    plt.tight_layout()
    save_chart(fig, "m4_sg_hop_comparison")


if __name__ == "__main__":
    chart()
