"""
m5_bnm_policy/analyze.py
─────────────────────────
基于 BNM FEP 关键条文，构建决策矩阵:
  有/无本地借贷 × 金额 × 选定路由 → 合规状态 + 限额约束

用法:
    python analyze.py

输出:
    data/m5_bnm_policy/decision_matrix.csv
    console 打印
"""

import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))
from utils import section

DATA_DIR = Path(__file__).parent.parent.parent / "data" / "m5_bnm_policy"
CLAUSES_PATH = DATA_DIR / "key_clauses.json"
MATRIX_CSV = DATA_DIR / "decision_matrix.csv"

# 金额档位（MYR）
AMOUNTS = [10_000, 50_000, 200_000, 500_000, 1_000_000]

# BNM 限额（以实际政策为准，这里是合理默认值）
LIMIT_WITH_BORROWING_MYR = 1_000_000   # RM 1M / 年（有本地借贷）
LIMIT_NO_BORROWING_MYR = float("inf")  # 实际上更高，需核实

ROUTES = ["Wise", "Instarem", "CIMB SG Hop", "HSBC Hop", "Bank TT"]

# 路由附加约束说明
ROUTE_NOTES = {
    "Wise": "Licensed remittance; generally compliant",
    "Instarem": "SG-licensed; BNM registered; generally compliant",
    "CIMB SG Hop": "Needs active CIMB SG account; cross-border within same group",
    "HSBC Hop": "Needs HSBC SG account; GlobalView cross-border",
    "Bank TT": "Standard SWIFT; confirm bank's per-transaction limit",
}


def analyze() -> None:
    section("M5 BNM Policy — analyze.py")

    if CLAUSES_PATH.exists():
        clauses = json.loads(CLAUSES_PATH.read_text(encoding="utf-8")).get("clauses", [])
        print(f"Loaded {len(clauses)} clauses from {CLAUSES_PATH}")
    else:
        print("No clauses file; using hardcoded default limits.")
        clauses = []

    rows = []
    for has_debt in [True, False]:
        annual_limit = LIMIT_WITH_BORROWING_MYR if has_debt else LIMIT_NO_BORROWING_MYR
        limit_label = "RM 1M/yr" if has_debt else "Generally no annual cap"

        for amount in AMOUNTS:
            for route in ROUTES:
                within_limit = (amount <= annual_limit) if annual_limit != float("inf") else True
                status = "OK" if within_limit else "EXCEEDS ANNUAL LIMIT"
                rows.append({
                    "has_local_borrowing": has_debt,
                    "annual_limit_myr": annual_limit if annual_limit != float("inf") else "unlimited",
                    "transfer_amount_myr": amount,
                    "route": route,
                    "compliance_status": status,
                    "limit_label": limit_label,
                    "route_notes": ROUTE_NOTES.get(route, ""),
                })

    df = pd.DataFrame(rows)
    df.to_csv(MATRIX_CSV, index=False)
    print(f"\nDecision matrix saved: {MATRIX_CSV}")

    # 打印汇总
    print("\n── Compliance Summary ──")
    print("  With local borrowing (RM 1M/yr limit):")
    sub = df[df["has_local_borrowing"] == True]
    for amt in AMOUNTS:
        ok = sub[(sub["transfer_amount_myr"] == amt)]["compliance_status"].iloc[0]
        print(f"    RM {amt:>10,.0f}  →  {ok}")

    print("\n  Without local borrowing:")
    sub2 = df[df["has_local_borrowing"] == False]
    print("    Generally no annual cap — all amounts OK (verify with bank)")


if __name__ == "__main__":
    analyze()
