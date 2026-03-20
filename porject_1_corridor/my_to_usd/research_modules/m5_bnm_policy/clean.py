"""
m5_bnm_policy/clean.py
───────────────────────
从 BNM FEP 文本中提取关键条文：
  - 居民/非居民汇出限额
  - 本地借贷情况下的限额
  - 相关路由约束

用法:
    python clean.py

输出:
    data/m5_bnm_policy/key_clauses.json   (结构化条文摘要)
    console 打印
"""

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from utils import section

DATA_DIR = Path(__file__).parent.parent.parent / "data" / "m5_bnm_policy"
TEXT_PATH = DATA_DIR / "bnm_fek_text.txt"
CLAUSES_PATH = DATA_DIR / "key_clauses.json"

# 关键词列表：围绕限额、居民、投资汇出
KEYWORDS = [
    r"resident",
    r"investment",
    r"remittance",
    r"limit",
    r"RM\s*[\d,]+\s*(million|thousand)?",
    r"1\s*million",
    r"borrowing",
    r"domestic\s*credit",
    r"permitted",
]


def extract_clauses(text: str) -> list:
    """提取包含关键词的段落。"""
    paragraphs = re.split(r"\n{2,}", text)
    hits = []
    for para in paragraphs:
        para_clean = para.strip()
        if len(para_clean) < 30:
            continue
        score = sum(1 for kw in KEYWORDS if re.search(kw, para_clean, re.IGNORECASE))
        if score >= 2:
            hits.append({
                "relevance_score": score,
                "text": para_clean[:800],  # 截断超长段落
            })
    hits.sort(key=lambda x: -x["relevance_score"])
    return hits[:20]  # 最多返回前 20 条


def run() -> None:
    section("M5 BNM Policy — clean.py")
    if not TEXT_PATH.exists():
        print(f"No text file at {TEXT_PATH}. Run collect.py first.")
        print("\nFallback: using manual summary mode.")
        print("If you have NOT downloaded the BNM FEP PDF, please record the key clauses manually.")
        manual_fallback()
        return

    text = TEXT_PATH.read_text(encoding="utf-8")
    print(f"Loaded {len(text):,} chars from {TEXT_PATH}")

    clauses = extract_clauses(text)
    print(f"Extracted {len(clauses)} relevant clauses.")

    for i, c in enumerate(clauses[:5], 1):
        print(f"\n[{i}] Score={c['relevance_score']}")
        print(f"  {c['text'][:300]}...")

    CLAUSES_PATH.write_text(json.dumps({"clauses": clauses}, indent=2, ensure_ascii=False),
                            encoding="utf-8")
    print(f"\nKey clauses saved: {CLAUSES_PATH}")


def manual_fallback() -> None:
    """若无 PDF，提示用户手动记录关键条文。"""
    print("\n请手动输入以下信息（来源: BNM Foreign Exchange Policy）：")
    print("参考: https://www.bnm.gov.my/foreign-exchange-policy\n")

    limit_with_debt = input(
        "有本地借贷时，居民海外投资每年限额 (RM)，如 1000000: ").strip()
    limit_no_debt = input(
        "无本地借贷时，居民海外投资每年限额 (RM，如无上限则填 unlimited): ").strip()
    notes = input("其他重要条文（可留空）: ").strip()

    data = {
        "source": "manual",
        "clauses": [
            {"text": f"居民有本地借贷: 海外投资限额 RM {limit_with_debt}/年", "relevance_score": 10},
            {"text": f"居民无本地借贷: {limit_no_debt}", "relevance_score": 10},
        ]
    }
    if notes:
        data["clauses"].append({"text": notes, "relevance_score": 5})

    CLAUSES_PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Manual clauses saved: {CLAUSES_PATH}")


if __name__ == "__main__":
    run()
