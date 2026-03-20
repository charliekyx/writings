"""
m6_tn_cost/analyze.py
──────────────────────
按各路由计算 T+N 机会成本，并合并 M1–M4 的显性成本，生成全成本比较表。

公式:
    opp_cost_pct = annual_rate × transit_days / 365 × 100

用法:
    python analyze.py

输出:
    data/m6_tn_cost/full_cost_comparison.csv
    data/m6_tn_cost/summary.txt
"""

import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))
from utils import section

DATA_DIR = Path(__file__).parent.parent.parent / "data" / "m6_tn_cost"
M1_CLEAN = Path(__file__).parent.parent.parent / "data" / "m1_wise" / "quotes_clean.csv"
M3_CLEAN = Path(__file__).parent.parent.parent / "data" / "m3_bank_tt" / "rates_clean.csv"
M4_CLEAN = Path(__file__).parent.parent.parent / "data" / "m4_sg_hop" / "hop_clean.csv"
PARAMS_FILE = DATA_DIR / "transit_params.json"
OUT_CSV = DATA_DIR / "full_cost_comparison.csv"
SUMMARY_TXT = DATA_DIR / "summary.txt"

AMOUNTS = [10_000.0, 50_000.0]


def opp_cost_pct(annual_rate: float, transit_days: float) -> float:
    return round(annual_rate * transit_days / 365 * 100, 4)


def analyze() -> None:
    section("M6 T+N — analyze.py")
    if not PARAMS_FILE.exists():
        print(f"No params at {PARAMS_FILE}. Run collect.py first.")
        sys.exit(1)

    params = json.loads(PARAMS_FILE.read_text(encoding="utf-8"))
    annual_rate = params["annual_risk_free_rate"]
    routes_params = params["routes"]

    # 加载各路由的显性成本
    explicit_costs = {}

    if M1_CLEAN.exists():
        w = pd.read_csv(M1_CLEAN, parse_dates=["timestamp"])
        for amt in AMOUNTS:
            sub = w[w["source_amount"] == amt]
            if not sub.empty:
                explicit_costs[("Wise", amt)] = sub["all_in_cost_pct"].mean()

    if M4_CLEAN.exists():
        s = pd.read_csv(M4_CLEAN, parse_dates=["timestamp"])
        for bank in s["bank"].unique():
            for amt in AMOUNTS:
                sub = s[(s["bank"] == bank) & (s["source_amount_myr"] == amt)]
                if not sub.empty:
                    key_name = f"{bank.upper()} SG Hop"
                    explicit_costs[(key_name, amt)] = sub["total_cost_pct"].mean()

    if M3_CLEAN.exists():
        b = pd.read_csv(M3_CLEAN, parse_dates=["timestamp"])
        for bank in b["bank"].unique():
            for amt in AMOUNTS:
                sub = b[(b["bank"] == bank) & (b["source_amount"] == amt)]
                if not sub.empty:
                    key_name = "Bank SWIFT TT"
                    explicit_costs[(key_name, amt)] = sub["all_in_sha_pct"].mean()

    rows = []
    for route_name, rp in routes_params.items():
        transit = rp["transit_days"]
        opp = opp_cost_pct(annual_rate, transit)

        for amt in AMOUNTS:
            explicit = explicit_costs.get((route_name, amt), None)
            full_cost = round(explicit + opp, 4) if explicit is not None else None
            rows.append({
                "route": route_name,
                "amount_myr": amt,
                "transit_days": transit,
                "opp_cost_pct": opp,
                "opp_cost_myr": round(amt * opp / 100, 2),
                "explicit_cost_pct": round(explicit, 4) if explicit else None,
                "full_cost_pct": full_cost,
                "full_cost_myr": round(amt * full_cost / 100, 2) if full_cost else None,
                "note": rp.get("notes", ""),
            })

    df = pd.DataFrame(rows)
    df.to_csv(OUT_CSV, index=False)
    print(f"Full cost comparison saved: {OUT_CSV}\n")

    lines = [f"Full Cost (Explicit + T+N Opportunity Cost)\n",
             f"Annual risk-free rate: {annual_rate*100:.1f}%\n"]
    for amt in AMOUNTS:
        sub = df[df["amount_myr"] == amt].copy()
        sub = sub.sort_values("full_cost_pct", na_position="last")
        lines.append(f"=== RM {amt:,.0f} ===")
        for _, r in sub.iterrows():
            fc = f"{r['full_cost_pct']:.3f}%" if r["full_cost_pct"] else "N/A"
            ex = f"{r['explicit_cost_pct']:.3f}%" if r["explicit_cost_pct"] else "N/A"
            lines.append(
                f"  {r['route']:<22} explicit={ex:>8}  T+N={r['opp_cost_pct']:.3f}%"
                f"  full={fc:>8}  ≈ RM {r['opp_cost_myr']:,.0f} in opp cost"
            )
        lines.append("")

    text = "\n".join(lines)
    SUMMARY_TXT.write_text(text, encoding="utf-8")
    print(text)
    print(f"Summary saved: {SUMMARY_TXT}")


if __name__ == "__main__":
    analyze()
