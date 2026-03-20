"""
m4_sg_hop/analyze.py
─────────────────────
比较 SG Hop 路由与 Wise 的全链路成本。

用法:
    python analyze.py

输出:
    data/m4_sg_hop/comparison.csv
    data/m4_sg_hop/summary.txt
"""

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))
from utils import section

DATA_DIR = Path(__file__).parent.parent.parent / "data" / "m4_sg_hop"
M1_CLEAN = Path(__file__).parent.parent.parent / "data" / "m1_wise" / "quotes_clean.csv"
HOP_CLEAN = DATA_DIR / "hop_clean.csv"
OUT_CSV = DATA_DIR / "comparison.csv"
SUMMARY_TXT = DATA_DIR / "summary.txt"


def analyze():
    section("M4 SG Hop — analyze.py")
    if not HOP_CLEAN.exists():
        print(f"No data at {HOP_CLEAN}. Run clean.py first.")
        sys.exit(1)

    hop = pd.read_csv(HOP_CLEAN, parse_dates=["timestamp"])
    wise = pd.read_csv(M1_CLEAN, parse_dates=["timestamp"]) if M1_CLEAN.exists() else None

    rows = []
    for amount in sorted(hop["source_amount_myr"].unique()):
        for bank in sorted(hop["bank"].unique()):
            sub = hop[(hop["source_amount_myr"] == amount) & (hop["bank"] == bank)]
            if sub.empty:
                continue
            hop_cost = sub["total_cost_pct"].mean()
            hop_leg_breakdown = {
                "leg1_pct": (sub["leg1_cost_myr"] / sub["source_amount_myr"] * 100).mean(),
                "leg2_fx_pct": (sub["leg2_fx_cost_myr"] / sub["source_amount_myr"] * 100).mean(),
                "leg2_wire_pct": (sub["leg2_wire_cost_myr"] / sub["source_amount_myr"] * 100).mean(),
                "intermediary_pct": (sub["intermediary_cost_myr"] / sub["source_amount_myr"] * 100).mean(),
            }
            wise_cost = None
            if wise is not None:
                w = wise[wise["source_amount"] == amount]
                wise_cost = w["all_in_cost_pct"].mean() if not w.empty else None

            rows.append({
                "bank": bank,
                "amount_myr": amount,
                "hop_total_pct": round(hop_cost, 4),
                **{k: round(v, 4) for k, v in hop_leg_breakdown.items()},
                "wise_all_in_pct": round(wise_cost, 4) if wise_cost else None,
                "diff_vs_wise": round(hop_cost - wise_cost, 4) if wise_cost else None,
            })

    df = pd.DataFrame(rows)
    df.to_csv(OUT_CSV, index=False)
    print(f"Comparison CSV: {OUT_CSV}")

    lines = ["SG Hop vs Wise — Cost Comparison\n"]
    for _, r in df.iterrows():
        lines.append(f"Bank: {r['bank']} | RM {r['amount_myr']:,.0f}")
        lines.append(f"  Leg 1 (cross-border) : {r['leg1_pct']:.3f}%")
        lines.append(f"  Leg 2 FX spread      : {r['leg2_fx_pct']:.3f}%")
        lines.append(f"  Leg 2 wire fee       : {r['leg2_wire_pct']:.3f}%")
        lines.append(f"  Intermediary         : {r['intermediary_pct']:.3f}%")
        lines.append(f"  TOTAL                : {r['hop_total_pct']:.3f}%")
        if r["wise_all_in_pct"] is not None:
            diff = r["diff_vs_wise"]
            winner = "SG Hop" if diff < 0 else "Wise"
            lines.append(f"  Wise all-in          : {r['wise_all_in_pct']:.3f}%")
            lines.append(f"  Delta vs Wise        : {diff:+.3f}% → {winner} cheaper")
        lines.append("")

    text = "\n".join(lines)
    SUMMARY_TXT.write_text(text, encoding="utf-8")
    print(f"Summary: {SUMMARY_TXT}")
    print(text)


if __name__ == "__main__":
    analyze()
