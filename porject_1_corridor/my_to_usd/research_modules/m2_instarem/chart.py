"""
m2_instarem/chart.py
─────────────────────
生成 Wise vs Instarem 成本对比柱状图。

用法:
    python chart.py

输出:
    charts/m2_wise_vs_instarem.png
"""

import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))
from utils import save_chart, section

COMPARISON_CSV = (
    Path(__file__).parent.parent.parent / "data" / "m2_instarem" / "comparison.csv"
)


def chart():
    section("M2 Instarem — chart.py")
    if not COMPARISON_CSV.exists():
        print(f"No comparison data at {COMPARISON_CSV}. Run analyze.py first.")
        sys.exit(1)

    df = pd.read_csv(COMPARISON_CSV)
    amounts = sorted(df["amount_myr"].unique())

    fig, axes = plt.subplots(1, len(amounts), figsize=(6 * len(amounts), 6), sharey=True)
    if len(amounts) == 1:
        axes = [axes]

    fig.suptitle("Wise vs Instarem — All-in Cost (% off mid)",
                 fontsize=14, fontweight="bold")

    colors = {"Wise": "#1565C0", "Instarem": "#2E7D32"}

    for ax, amount in zip(axes, amounts):
        grp = df[df["amount_myr"] == amount]
        wise_mean = grp["wise_all_in_pct"].mean()
        inst_mean = grp["instarem_all_in_pct"].mean()
        wise_std = grp["wise_all_in_pct"].std()
        inst_std = grp["instarem_all_in_pct"].std()

        x = np.array([0, 1])
        vals = [wise_mean, inst_mean]
        errs = [wise_std if not np.isnan(wise_std) else 0,
                inst_std if not np.isnan(inst_std) else 0]

        bars = ax.bar(x, vals, color=[colors["Wise"], colors["Instarem"]],
                      width=0.5, alpha=0.85, yerr=errs, capsize=5)

        # 标注数值
        for bar, val in zip(bars, vals):
            ax.text(bar.get_x() + bar.get_width() / 2, val + 0.01,
                    f"{val:.3f}%", ha="center", va="bottom", fontsize=10, fontweight="bold")

        ax.set_title(f"RM {amount:,.0f}", fontsize=12)
        ax.set_xticks(x)
        ax.set_xticklabels(["Wise", "Instarem"], fontsize=11)
        ax.set_ylabel("All-in cost (% off mid)" if amount == amounts[0] else "")
        ax.grid(True, axis="y", alpha=0.3)

        # 标出哪个更便宜
        cheaper = "Wise" if wise_mean < inst_mean else "Instarem"
        diff = abs(wise_mean - inst_mean)
        ax.text(0.5, max(vals) * 0.7,
                f"{cheaper} cheaper\nby {diff:.3f}%",
                ha="center", transform=ax.transAxes,
                fontsize=9, color="#B71C1C",
                bbox=dict(boxstyle="round,pad=0.3", fc="white", alpha=0.7))

    plt.tight_layout()
    save_chart(fig, "m2_wise_vs_instarem")


if __name__ == "__main__":
    chart()
