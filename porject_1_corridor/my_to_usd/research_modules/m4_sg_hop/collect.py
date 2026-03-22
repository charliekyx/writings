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
    python collect.py --mode scrape --bank cimb    # 默认：官网动态解析
    python collect.py --mode scrape --bank hsbc
    python collect.py --mode manual --bank cimb
    python collect.py --mode json --json-file path/to/m4_records.json  # 仅调试/回放

输出:
    data/m4_sg_hop/fee_schedule.jsonl
"""

import argparse
import json
import os
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


def _record_from_json_item(item: dict, mid_myr_usd: dict, mid_myr_sgd: dict) -> dict:
    required = (
        "bank",
        "source_amount_myr",
        "leg1_fee_myr",
        "leg1_rate_note",
        "leg2_fx_spread_pct",
        "leg2_wire_fee_sgd",
    )
    for k in required:
        if k not in item:
            raise KeyError(f"JSON item missing required key: {k}")
    ts = datetime.now(timezone.utc)
    return {
        "timestamp": ts.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "session": session_for(ts),
        "bank": item["bank"],
        "source": "m4_config_json",
        "source_amount_myr": float(item["source_amount_myr"]),
        "leg1_fee_myr": float(item["leg1_fee_myr"]),
        "leg1_rate_note": str(item["leg1_rate_note"]),
        "leg2_fx_spread_pct": float(item["leg2_fx_spread_pct"]),
        "leg2_wire_fee_sgd": float(item["leg2_wire_fee_sgd"]),
        "leg2_intermediary_usd": float(
            item.get("leg2_intermediary_usd", 25.0)
        ),
        "swift_mode": str(item.get("swift_mode") or "SHA"),
        "mid_rate_myr_usd": mid_myr_usd["mid_rate"],
        "mid_rate_myr_sgd": mid_myr_sgd["mid_rate"],
        "mid_rate_at_quote": mid_myr_usd["mid_rate"],
    }


def run_scrape(bank: str, amounts: list) -> None:
    """从 CIMB / HSBC 官网拉取费用页并解析；中间价来自 Frankfurter。"""
    from fee_scrape import (
        CIMB_SG_REMITTANCE_URL,
        HSBC_GM_URL,
        _get,
        cimb_leg2_wire_fee_sgd,
        hsbc_leg2_from_global_money_page,
        scrape_cimb_leg1_fee_myr,
        scrape_hsbc_leg1_note,
    )

    section("M4 SG Hop — collect.py (scrape)")
    bank = bank.lower()
    strict = os.environ.get("STRICT_AUTO", "").lower() in ("1", "true", "yes")
    print(f"Bank: {bank.upper()}")

    mid_myr_usd = fetch_mid_rate("MYR", "USD")
    mid_myr_sgd = fetch_mid_rate("MYR", "SGD")
    mid_usd_sgd = fetch_mid_rate("USD", "SGD")
    print(f"  mid: 1 MYR = {mid_myr_usd['mid_rate']:.6f} USD")
    print(f"  mid: 1 MYR = {mid_myr_sgd['mid_rate']:.6f} SGD")
    print(f"  mid: 1 USD = {mid_usd_sgd['mid_rate']:.6f} SGD")

    fx_note = (
        " leg2_fx_spread_pct=0 (fee pages do not publish vs mid; model FX in a separate quote scrape)."
    )

    if bank == "cimb":
        cimb_html = _get(CIMB_SG_REMITTANCE_URL)
        leg1_fee, leg1_url, leg1_note = scrape_cimb_leg1_fee_myr()
        for amount in amounts:
            wire_sgd, l2note = cimb_leg2_wire_fee_sgd(
                amount,
                mid_myr_sgd["mid_rate"],
                mid_usd_sgd["mid_rate"],
                cimb_html,
            )
            ts = datetime.now(timezone.utc)
            record = {
                "timestamp": ts.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "session": session_for(ts),
                "bank": "cimb",
                "source": "m4_official_scrape",
                "source_amount_myr": amount,
                "leg1_fee_myr": leg1_fee,
                "leg1_rate_note": f"{leg1_note} | {leg1_url}{fx_note} | {l2note}",
                "leg2_fx_spread_pct": 0.0,
                "leg2_wire_fee_sgd": wire_sgd,
                "leg2_intermediary_usd": 0.0,
                "swift_mode": "SHA",
                "mid_rate_myr_usd": mid_myr_usd["mid_rate"],
                "mid_rate_myr_sgd": mid_myr_sgd["mid_rate"],
                "mid_rate_at_quote": mid_myr_usd["mid_rate"],
                "leg2_fee_source_url": CIMB_SG_REMITTANCE_URL,
            }
            append_jsonl(FEE_SCHEDULE, record)
            print(f"  Saved cimb RM{amount:,.0f} leg2_wire_sgd={wire_sgd}")
    elif bank == "hsbc":
        gm_html = _get(HSBC_GM_URL)
        wire_sgd, inter_usd, l2note = hsbc_leg2_from_global_money_page(
            gm_html,
            strict_validate=strict,
        )
        leg1_fee, leg1_url, leg1_note = scrape_hsbc_leg1_note()
        for amount in amounts:
            ts = datetime.now(timezone.utc)
            record = {
                "timestamp": ts.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "session": session_for(ts),
                "bank": "hsbc",
                "source": "m4_official_scrape",
                "source_amount_myr": amount,
                "leg1_fee_myr": leg1_fee,
                "leg1_rate_note": f"{leg1_note} | {leg1_url}{fx_note} | {l2note}",
                "leg2_fx_spread_pct": 0.0,
                "leg2_wire_fee_sgd": wire_sgd,
                "leg2_intermediary_usd": inter_usd,
                "swift_mode": "SHA",
                "mid_rate_myr_usd": mid_myr_usd["mid_rate"],
                "mid_rate_myr_sgd": mid_myr_sgd["mid_rate"],
                "mid_rate_at_quote": mid_myr_usd["mid_rate"],
                "leg2_fee_source_url": HSBC_GM_URL,
            }
            append_jsonl(FEE_SCHEDULE, record)
            print(f"  Saved hsbc RM{amount:,.0f} leg2_wire_sgd={wire_sgd}")
    else:
        print(f"scrape mode does not support bank={bank}", file=sys.stderr)
        sys.exit(1)

    print(f"\nDone. Fee schedule -> {FEE_SCHEDULE}")


def run_from_json(json_path: Path) -> None:
    section("M4 SG Hop — collect.py (json mode)")
    raw = json_path.read_text(encoding="utf-8")
    items = json.loads(raw)
    if not isinstance(items, list):
        raise ValueError("M4 JSON root must be an array")

    print("\nFetching mid-rate for SGD/MYR and USD/MYR...")
    mid_myr_usd = fetch_mid_rate("MYR", "USD")
    mid_myr_sgd = fetch_mid_rate("MYR", "SGD")
    print(f"  1 MYR = {mid_myr_usd['mid_rate']:.6f} USD")
    print(f"  1 MYR = {mid_myr_sgd['mid_rate']:.6f} SGD")

    for item in items:
        record = _record_from_json_item(item, mid_myr_usd, mid_myr_sgd)
        append_jsonl(FEE_SCHEDULE, record)
        print(
            f"  Saved: {record['bank']} amount={record['source_amount_myr']} "
            f"leg2 wire SGD {record['leg2_wire_fee_sgd']}"
        )
    print(f"\nDone. Fee schedule -> {FEE_SCHEDULE}")


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
    parser.add_argument(
        "--mode",
        choices=["manual", "json", "scrape"],
        default="scrape",
        help="scrape: official pages (cimb|hsbc); manual: CLI; json: replay file",
    )
    parser.add_argument("--bank", choices=["cimb", "hsbc", "maybank", "ocbc", "sc"],
                        default="cimb")
    parser.add_argument("--amount", type=float, action="append",
                        help="Amount in MYR. Default: 10000 50000")
    parser.add_argument("--json-file", type=str, default=None,
                        help="Path to JSON array of SG hop records (json mode)")
    args = parser.parse_args()
    amounts = args.amount if args.amount else [10000.0, 50000.0]
    if args.mode == "json":
        path_str = args.json_file or os.environ.get("M4_CONFIG_JSON", "").strip()
        if not path_str:
            print("json mode requires --json-file or M4_CONFIG_JSON", file=sys.stderr)
            sys.exit(1)
        run_from_json(Path(path_str))
        return
    if args.mode == "scrape":
        if args.bank not in ("cimb", "hsbc"):
            print("scrape mode: --bank must be cimb or hsbc", file=sys.stderr)
            sys.exit(1)
        run_scrape(args.bank, amounts)
        return
    run(bank=args.bank, amounts=amounts)


if __name__ == "__main__":
    main()
