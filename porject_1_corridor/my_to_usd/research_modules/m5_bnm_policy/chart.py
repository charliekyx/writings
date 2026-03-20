"""
m5_bnm_policy/chart.py
───────────────────────
输出 BNM 合规决策 Mermaid 流程图（Markdown 格式，可直接嵌入文章）。

用法:
    python chart.py

输出:
    charts/m5_bnm_decision_flow.md
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from utils import section

CHARTS_DIR = Path(__file__).parent.parent.parent / "charts"
OUT_MD = CHARTS_DIR / "m5_bnm_decision_flow.md"
DATA_DIR = Path(__file__).parent.parent.parent / "data" / "m5_bnm_policy"
MATRIX_CSV = DATA_DIR / "decision_matrix.csv"


MERMAID = '''```mermaid
flowchart TD
    A[开始汇款规划] --> B{是否是马来西亚居民?}

    B -->|否| C[非居民另行适用<br/>BNM 非居民规则]
    B -->|是| D{本地是否有未结清<br/>房贷或其他贷款?}

    D -->|有本地借贷| E[年度海外投资限额<br/>RM 1,000,000]
    D -->|无本地借贷| F[年度限额较高<br/>请确认最新 BNM FEP]

    E --> G{单笔金额是否<br/>超过 RM 1,000,000?}
    G -->|是| H[需要银行额外审批<br/>拆单或等下一年度]
    G -->|否| I[金额在限额内]

    F --> I

    I --> J{选择汇款路由}
    J --> K[Wise / Instarem<br/>持牌汇款商]
    J --> L[SG Hop<br/>CIMB / HSBC 同集团]
    J --> M[银行 SWIFT TT<br/>本地银行]

    K --> N[合规 — 汇款商已向<br/>BNM 申报]
    L --> O[合规 — 需双边账户<br/>建议保留记录]
    M --> P[合规 — 银行负责申报<br/>TT 费用较高]

    N --> Q[完成 — 记录转账凭证]
    O --> Q
    P --> Q

    style H fill:#FFCDD2,stroke:#C62828
    style Q fill:#C8E6C9,stroke:#1B5E20
    style E fill:#FFF9C4,stroke:#F9A825
    style F fill:#FFF9C4,stroke:#F9A825
```'''

DISCLAIMER = """
> **免责声明:** 以上流程图基于 BNM Foreign Exchange Policy (FEP) 的公开文本，
> 仅供参考，不构成法律或税务建议。政策随时可能更新，请在汇款前核实最新规定。
> 来源: [BNM FEP](https://www.bnm.gov.my/foreign-exchange-policy)
"""


def chart() -> None:
    section("M5 BNM Policy — chart.py")
    CHARTS_DIR.mkdir(exist_ok=True)

    content = f"# BNM 外汇政策合规决策流程\n\n{MERMAID}\n\n{DISCLAIMER}\n"
    OUT_MD.write_text(content, encoding="utf-8")
    print(f"Mermaid decision flow saved: {OUT_MD}")
    print("\nPreview (first 20 lines):")
    for line in content.splitlines()[:20]:
        print(f"  {line}")


if __name__ == "__main__":
    chart()
