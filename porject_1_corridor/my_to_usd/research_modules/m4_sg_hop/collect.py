"""
m4_sg_hop/collect.py
─────────────────────
收集 SG Hop 路由的费用信息。
包含两段：
  Leg 1: MYR → 同集团 SG 账户（通常免费或近似免费）
  Leg 2: SG 账户 → IBKR USD Wire（SGD 计价费用 + FX spread）

支持的银行:
  cimb   : CIMB MY → CIMB SG → IBKR
  hsbc   : HSBC MY → HSBC SG → IBKR

用法:
    python collect.py --bank cimb
    python collect.py --bank hsbc

输出:
    data/m4_sg_hop/fee_schedule.jsonl
"""

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from utils import append_jsonl, fetch_mid_rate, section, session_for

DATA_DIR = Path(__file__).parent.parent.parent / "data" / "m4_sg_hop"
DATA_DIR.mkdir(parents=True, exist_ok=True)
FEE_SCHEDULE = DATA_DIR / "fee_schedule.jsonl"

# 参考链接（手动核查时使用）
REFERENCE_URLS = {
    "cimb": {
        "cross_border": "https://www.cimbclicks.com.sg/cimbclicks/html/mobile/terms/cross-border.html",
        "wire_fee": "https://www.cimb.com.sg/en/personal/banking/fees-and-charges.html",
    },
    "hsbc": {
        "globalview": "https://www.hsbc.com.my/transfers/globalview/",
        "wire_fee": "https://www.hsbc.com.sg/transfers/fees/",
    },
}


def manual_input_sg_hop(bank: str, amount_myr: float) -> dict:
    """
    引导用户从银行官网 Fee Schedule 收集 SG Hop 的费用结构。
    两段分开填写。
    """
    ref = REFERENCE_URLS.get(bank, {})
    print(f"\n  SG Hop — {bank.upper()}")
    print(f"  金额: RM {amount_myr:,.0f}")
    if ref:
        for k, v in ref.items():
            print(f"  参考链接 [{k}]: {v}")
    print()

    # Leg 1: MYR 跨境转账到 SG 同集团
    print("  === Leg 1: MYR 跨境转账（MY → SG 同集团账户）===")
    leg1_fee_str = input("  Leg 1 费用 (MYR, 通常 0 或 RM 0-10): ").strip()
    leg1_rate_note = input("  Leg 1 汇率备注（如 '1:1 MYR, 无 FX'，或 SGD 到账汇率如 '0.312'）: ").strip()

    # Leg 2: SG 账户发 USD Wire 到 IBKR
    print("\n  === Leg 2: SG 账户 USD Wire 到 IBKR ===")
    print("  (MYR→SGD 或 MYR→USD 的 FX 由 SG 账户端完成)")
    fx_spread_str = input("  SG 端 FX spread 估计 (%, 如 '0.6'): ").strip()
    wire_fee_sgd_str = input("  SG USD Wire fee (SGD, 如 '25'): ").strip()
    intermediary_str = input("  预估中间行费 (USD, 通常 15-35, 如 '25'): ").strip()
    swift_mode = input("  费控模式 (OUR/SHA/BEN, 默认 SHA): ").strip() or "SHA"

    ts = datetime.now(timezone.utc)
    return {
        "timestamp": ts.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "session": session_for(ts),
        "bank": bank,
        "source_amount_myr": amount_myr,
        # Leg 1
        "leg1_fee_myr": float(leg1_fee_str) if leg1_fee_str else 0.0,
        "leg1_rate_note": leg1_rate_note,
        # Leg 2
        "leg2_fx_spread_pct": float(fx_spread_str) if fx_spread_str else None,
        "leg2_wire_fee_sgd": float(wire_fee_sgd_str) if wire_fee_sgd_str else None,
        "leg2_intermediary_usd": float(intermediary_str) if intermediary_str else 25.0,
        "swift_mode": swift_mode,
        "mid_rate_at_quote": None,
    }


def run(bank: str, amounts: list) -> None:
    section("M4 SG Hop — collect.py")
    print(f"Bank: {bank.upper()}")

    print("\nFetching mid-rate for SGD/MYR and USD/MYR...")
    mid_myr_usd = fetch_mid_rate("MYR", "USD")
    mid_myr_sgd = fetch_mid_rate("MYR", "SGD")
    print(f"  1 MYR = {mid_myr_usd['mid_rate']:.6f} USD")
    print(f"  1 MYR = {mid_myr_sgd['mid_rate']:.6f} SGD")

    for amount in amounts:
        record = manual_input_sg_hop(bank, amount)
        record["mid_rate_myr_usd"] = mid_myr_usd["mid_rate"]
        record["mid_rate_myr_sgd"] = mid_myr_sgd["mid_rate"]
        record["mid_rate_at_quote"] = mid_myr_usd["mid_rate"]
        append_jsonl(FEE_SCHEDULE, record)
        print(f"  Saved: {bank} leg1={record['leg1_fee_myr']} MYR, "
              f"leg2 spread={record['leg2_fx_spread_pct']}%, "
              f"wire={record['leg2_wire_fee_sgd']} SGD")

    print(f"\nDone. Fee schedule -> {FEE_SCHEDULE}")


def main():
    parser = argparse.ArgumentParser(description="Collect SG hop route fee data.")
    parser.add_argument("--bank", choices=["cimb", "hsbc", "maybank", "ocbc", "sc"],
                        default="cimb")
    parser.add_argument("--amount", type=float, action="append",
                        help="Amount in MYR. Default: 10000 50000")
    args = parser.parse_args()
    amounts = args.amount if args.amount else [10000.0, 50000.0]
    run(bank=args.bank, amounts=amounts)


if __name__ == "__main__":
    main()
