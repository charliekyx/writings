"""
m3_bank_tt/chart.py
────────────────────
生成银行 TT 成本堆叠柱状图（FX spread + wire fee + 中间行，三种费控）。

用法:
    python chart.py

输出:
    charts/m3_bank_cost_stack.png
"""

import sys
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))
from utils import save_chart, section

DATA_DIR = Path(__file__).parent.parent.parent / "data" / "m3_bank_tt"
M1_CLEAN = Path(__file__).parent.parent.parent / "data" / "m1_wise" / "quotes_clean.csv"
CLEAN_CSV = DATA_DIR / "rates_clean.csv"

INTERMEDIARY_MYR_ESTIMATES = {
    "OUR (no cut)": 0.0,
    "SHA (~USD 25)": 25.0,
    "BEN (~USD 35)": 35.0,
}


def chart():
    section("M3 Bank TT — chart.py")
    if not CLEAN_CSV.exists():
        print(f"No data at {CLEAN_CSV}. Run collect.py + clean.py first.")
        sys.exit(1)

    df = pd.read_csv(CLEAN_CSV, parse_dates=["timestamp"])
    wise = pd.read_csv(M1_CLEAN, parse_dates=["timestamp"]) if M1_CLEAN.exists() else None

    amounts = sorted(df["source_amount"].unique())
    banks = sorted(df["bank"].unique())
    n_amounts = len(amounts)

    fig, axes = plt.subplots(1, n_amounts, figsize=(8 * n_amounts, 7), sharey=False)
    if n_amounts == 1:
        axes = [axes]

    fig.suptitle("Bank TT — All-in Cost by Fee Control Mode\n(FX spread + wire + intermediary)",
                 fontsize=13, fontweight="bold")

    fee_modes = ["all_in_our_pct", "all_in_sha_pct", "all_in_ben_pct"]
    mode_labels = ["OUR", "SHA (~$25)", "BEN (~$35)"]
    mode_colors = ["#90CAF9", "#1565C0", "#0D47A1"]

    for ax, amount in zip(axes, amounts):
        sub = df[df["source_amount"] == amount]
        x = np.arange(len(banks))
        width = 0.25

        for j, (col, label, color) in enumerate(zip(fee_modes, mode_labels, mode_colors)):
            vals = [sub[sub["bank"] == b][col].mean() for b in banks]
            bars = ax.bar(x + j * width, vals, width, label=label, color=color, alpha=0.85)
            for bar, val in zip(bars, vals):
                ax.text(bar.get_x() + bar.get_width() / 2, val + 0.01,
                        f"{val:.2f}%", ha="center", va="bottom", fontsize=7)

        # Wise 基准线
        if wise is not None:
            w = wise[wise["source_amount"] == amount]["all_in_cost_pct"]
            if not w.empty:
                ax.axhline(w.mean(), linestyle="--", color="#B71C1C", linewidth=1.5,
                           label=f"Wise ({w.mean():.2f}%)")

        ax.set_title(f"RM {amount:,.0f}", fontsize=12)
        ax.set_xticks(x + width)
        ax.set_xticklabels([b.upper() for b in banks], fontsize=10)
        ax.set_ylabel("All-in cost (% off mid)")
        ax.legend(fontsize=8)
        ax.grid(True, axis="y", alpha=0.3)

    plt.tight_layout()
    save_chart(fig, "m3_bank_cost_stack")


if __name__ == "__main__":
    chart()
