"""
m6_tn_cost/chart.py
────────────────────
全成本（显性 + T+N 机会成本）堆叠柱状图，让读者直观看到"速度慢的隐性成本"。

用法:
    python chart.py

输出:
    charts/m6_tn_full_cost.png
"""

import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))
from utils import save_chart, section

DATA_DIR = Path(__file__).parent.parent.parent / "data" / "m6_tn_cost"
OUT_CSV = DATA_DIR / "full_cost_comparison.csv"


def chart() -> None:
    section("M6 T+N — chart.py")
    if not OUT_CSV.exists():
        print(f"No data at {OUT_CSV}. Run analyze.py first.")
        sys.exit(1)

    df = pd.read_csv(OUT_CSV)

    # 若还没有显性成本数据，仅绘制 T+N 机会成本（作为 fallback）
    has_explicit = df["explicit_cost_pct"].notna().any()
    if has_explicit:
        df = df.dropna(subset=["explicit_cost_pct"])
    else:
        print("  No explicit cost data yet (run M1/M3/M4 first). Showing T+N-only chart.")

    amounts = sorted(df["amount_myr"].unique())
    if not amounts:
        print("No data to chart.")
        sys.exit(0)

    fig, axes = plt.subplots(1, len(amounts), figsize=(8 * len(amounts), 7), sharey=False)
    if len(amounts) == 1:
        axes = [axes]

    fig.suptitle("Full Cost per Route: Explicit Fees + T+N Opportunity Cost\n"
                 "(Annual risk-free rate = 4%)",
                 fontsize=13, fontweight="bold")

    for ax, amount in zip(axes, amounts):
        sub = df[df["amount_myr"] == amount].copy()
        sub = sub.sort_values("full_cost_pct")
        routes = sub["route"].tolist()
        x = np.arange(len(routes))
        width = 0.5

        # 堆叠：显性 + 机会成本
        bars_exp = ax.bar(x, sub["explicit_cost_pct"].fillna(0), width,
                          label="Explicit cost", color="#1565C0", alpha=0.85)
        bars_opp = ax.bar(x, sub["opp_cost_pct"], width,
                          bottom=sub["explicit_cost_pct"].fillna(0),
                          label="T+N opp. cost", color="#F9A825", alpha=0.85)

        # 顶部标注全成本
        for i, (_, row) in enumerate(sub.iterrows()):
            total = (row["explicit_cost_pct"] or 0) + row["opp_cost_pct"]
            ax.text(i, total + 0.01, f"{total:.3f}%",
                    ha="center", va="bottom", fontsize=8, fontweight="bold")

        ax.set_title(f"RM {amount:,.0f}", fontsize=12)
        ax.set_xticks(x)
        ax.set_xticklabels(routes, rotation=25, ha="right", fontsize=9)
        ax.set_ylabel("Cost (% of transfer amount)")
        ax.legend(fontsize=9)
        ax.grid(True, axis="y", alpha=0.3)

    plt.tight_layout()
    save_chart(fig, "m6_tn_full_cost")


if __name__ == "__main__":
    chart()
