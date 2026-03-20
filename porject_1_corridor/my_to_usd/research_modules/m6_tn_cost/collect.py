"""
M6 T+N 机会成本模块 — 四合一文件
   collect.py : 生成参数表（无外部数据依赖）
   clean.py   : 占位（无需清洗，数据由 collect 直接生成）
   analyze.py : 按路由和金额计算 T+N 隐性机会成本
   chart.py   : 全成本（显性 + 隐性）堆叠对比图

用法（任选其一）:
    python collect.py
    python analyze.py
    python chart.py
"""

# ── collect.py ────────────────────────────────────────────────────────────────
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from utils import section

DATA_DIR = Path(__file__).parent.parent.parent / "data" / "m6_tn_cost"
DATA_DIR.mkdir(parents=True, exist_ok=True)
PARAMS_FILE = DATA_DIR / "transit_params.json"

# 各路由的在途天数（T+N）估算
TRANSIT_PARAMS = {
    "Wise": {
        "transit_days": 1.0,
        "source": "Wise website estimate; 0-1 business day",
        "notes": "Same-day possible in some corridors"
    },
    "Instarem": {
        "transit_days": 1.5,
        "source": "Instarem website estimate",
        "notes": "1-2 business days"
    },
    "CIMB SG Hop": {
        "transit_days": 2.5,
        "source": "Community estimate",
        "notes": "Leg1 instant; Leg2 SWIFT 1-2 days; IBKR credit 0-1 day"
    },
    "HSBC Hop": {
        "transit_days": 2.5,
        "source": "Community estimate",
        "notes": "Similar to CIMB hop"
    },
    "Bank SWIFT TT": {
        "transit_days": 4.0,
        "source": "Industry standard SWIFT estimate",
        "notes": "3-5 business days"
    },
}

# 无风险利率（年化，用于机会成本计算）
ANNUAL_RISK_FREE_RATE = 0.04   # 4% — 参考 MYR 固定存款 / USD 货币市场


def collect():
    section("M6 T+N — collect.py")
    data = {
        "annual_risk_free_rate": ANNUAL_RISK_FREE_RATE,
        "note": "Rate for opportunity cost calculation (MYR FD / USD MMF reference)",
        "routes": TRANSIT_PARAMS,
    }
    PARAMS_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Transit params saved: {PARAMS_FILE}")
    for route, p in TRANSIT_PARAMS.items():
        print(f"  {route:<20}  T+{p['transit_days']} days  ({p['notes']})")


if __name__ == "__main__":
    collect()
