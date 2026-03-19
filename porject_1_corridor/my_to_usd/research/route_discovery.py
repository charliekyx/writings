"""
route_discovery.py
──────────────────
扫描所有 Reddit JSON 文件，穷举每个 provider / 路由 / 银行名被提到的次数。
用于确保文章覆盖所有 available options，不遗漏。

用法（在 research/ 目录下运行）：
    python3 route_discovery.py
    python3 route_discovery.py --detail wise   # 显示某 provider 的原始句子
"""

import json
import re
import sys
from pathlib import Path
from collections import Counter, defaultdict

DATA_DIR = Path(__file__).parent / "data"

# ═══════════════════════════════════════════════════════════════════════
# PROVIDER / ROUTE DICTIONARY
# 每个 key = 规范名称，values = 搜索时用的所有变体（不区分大小写）
# ═══════════════════════════════════════════════════════════════════════
PROVIDERS = {
    # ── Fintech 汇款 ──────────────────────────────────────────────────
    "Wise":              ["wise", "transferwise"],
    "Instarem":          ["instarem"],
    "Merchantrade":      ["merchantrade", "merchant trade"],
    "BigPay":            ["bigpay", "big pay"],
    "Remitly":           ["remitly"],
    "WorldRemit":        ["worldremit", "world remit"],
    "MoneyMatch":        ["moneymatch", "money match"],
    "SkyRem":            ["skyrem", "sky rem"],
    "CurrencyFair":      ["currencyfair", "currency fair"],
    "XE Transfer":       [r"\bxe\b", "xe.com", "xe money"],
    "Panda Remit":       ["panda remit", "pandaRemit"],
    "SingX":             ["singx", "sing x"],
    "Airwallex":         ["airwallex", "air wallex"],
    "Payoneer":          ["payoneer"],
    "Revolut":           ["revolut"],

    # ── 马来西亚本地银行 ───────────────────────────────────────────────
    "Maybank":           ["maybank", "mbb"],
    "CIMB":              ["cimb"],
    "RHB":               [r"\brhb\b"],
    "Public Bank":       ["public bank", "pbbank"],
    "Hong Leong Bank":   ["hong leong bank", "hlb", r"\bhlbb\b"],
    "AmBank":            ["ambank", "am bank"],
    "Bank Islam":        ["bank islam"],
    "Alliance Bank":     ["alliance bank"],
    "Affin Bank":        ["affin bank"],
    "Bank Rakyat":       ["bank rakyat"],

    # ── SG routing 路径（同集团跨境）────────────────────────────────────
    "CIMB SG":           ["cimb sg", "cimb singapore", "cimb clicks sg"],
    "OCBC MY→SG":        ["ocbc my", "ocbc malaysia", "ocbc sg", "ocbc singapore"],
    "Standard Chartered MY→SG": ["standard chartered", "stanchart", "sc bank"],
    "HSBC MY→SG":        ["hsbc malaysia", "hsbc sg", "hsbc singapore", r"\bhsbc\b"],
    "Maybank SG":        ["maybank sg", "maybank singapore", "kim eng"],
    "DBS":               [r"\bdbs\b"],
    "UOB":               [r"\buob\b"],
    "POSB":              [r"\bposb\b"],

    # ── IBKR 内部 ────────────────────────────────────────────────────
    "IBKR IDEALPRO":     ["idealpro", "ideal pro"],
    "IBKR MYR deposit":  ["myr deposit", "deposit myr", "deposit in myr"],

    # ── 其他结构 ─────────────────────────────────────────────────────
    "SWIFT TT":          ["swift tt", "telegraphic transfer", r"\btt\b"],
    "Crypto bridge":     ["usdt", "binance", "crypto bridge", "moonpay"],
    "PayPal":            ["paypal"],
}

# ═══════════════════════════════════════════════════════════════════════
def extract_text_from_json(path: Path) -> list[str]:
    """从 Reddit JSON 提取所有 title + selftext 文本。
    实际结构: {"meta": {...}, "posts": [{title, selftext, ...}, ...]}
    """
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []

    posts = []
    if isinstance(data, dict):
        posts = data.get("posts", data.get("data", []))
    elif isinstance(data, list):
        posts = data

    texts = []
    for item in posts:
        if isinstance(item, dict):
            texts.append(item.get("title", ""))
            texts.append(item.get("selftext", ""))
            for c in item.get("comments", []):
                if isinstance(c, dict):
                    texts.append(c.get("body", ""))
    return [t for t in texts if t and len(t) > 3]


def find_mentions(texts: list[str], patterns: list[str]) -> list[str]:
    """在文本列表中找出包含任一 pattern 的句子。"""
    compiled = [re.compile(p, re.IGNORECASE) for p in patterns]
    hits = []
    for text in texts:
        sentences = re.split(r"[.\n!?]", text)
        for sent in sentences:
            if any(rx.search(sent) for rx in compiled):
                hits.append(sent.strip())
    return hits


def main():
    detail_target = None
    if "--detail" in sys.argv:
        idx = sys.argv.index("--detail")
        if idx + 1 < len(sys.argv):
            detail_target = sys.argv[idx + 1].lower()

    # 加载所有 JSON
    all_texts: list[str] = []
    for f in sorted(DATA_DIR.glob("reddit_*.json")):
        all_texts.extend(extract_text_from_json(f))

    print(f"\nLoaded {len(all_texts)} text segments from {len(list(DATA_DIR.glob('reddit_*.json')))} files.\n")

    # 统计每个 provider 的提及次数
    counts: dict[str, int] = {}
    sentences_map: dict[str, list[str]] = defaultdict(list)

    for name, patterns in PROVIDERS.items():
        hits = find_mentions(all_texts, patterns)
        counts[name] = len(hits)
        sentences_map[name] = hits

    # 按频次排序输出
    print("=" * 60)
    print("PROVIDER MENTION COUNTS (all Reddit files combined)")
    print("=" * 60)

    categories = [
        ("Fintech 汇款", ["Wise", "Instarem", "Merchantrade", "BigPay",
                          "Remitly", "WorldRemit", "MoneyMatch", "SkyRem",
                          "CurrencyFair", "XE Transfer", "Panda Remit",
                          "SingX", "Airwallex", "Payoneer", "Revolut"]),
        ("马来西亚本地银行", ["Maybank", "CIMB", "RHB", "Public Bank",
                             "Hong Leong Bank", "AmBank", "Bank Islam",
                             "Alliance Bank", "Affin Bank", "Bank Rakyat"]),
        ("SG Routing 路径", ["CIMB SG", "OCBC MY→SG", "Standard Chartered MY→SG",
                             "HSBC MY→SG", "Maybank SG", "DBS", "UOB", "POSB"]),
        ("IBKR 内部", ["IBKR IDEALPRO", "IBKR MYR deposit"]),
        ("其他", ["SWIFT TT", "Crypto bridge", "PayPal"]),
    ]

    for cat_name, names in categories:
        print(f"\n── {cat_name} ──")
        cat_rows = [(n, counts.get(n, 0)) for n in names]
        cat_rows.sort(key=lambda x: -x[1])
        for name, count in cat_rows:
            bar = "█" * min(count, 40)
            print(f"  {name:<35} {count:>4}  {bar}")

    print("\n")
    print("=" * 60)
    print("ROUTE UNIVERSE RECOMMENDATION")
    print("(providers with ≥1 mention OR known from market research)")
    print("=" * 60)
    mentioned = {k for k, v in counts.items() if v > 0}
    known_no_mention = {"Instarem", "Merchantrade", "CIMB SG", "OCBC MY→SG",
                        "Standard Chartered MY→SG", "BigPay", "Panda Remit"}
    all_to_cover = mentioned | known_no_mention
    print("\nRoutes to cover in article:")
    for name in sorted(all_to_cover):
        mark = "Reddit ✓" if counts.get(name, 0) > 0 else "Market research"
        print(f"  [{mark}]  {name}  (mentions: {counts.get(name, 0)})")

    # Detail mode
    if detail_target:
        print(f"\n{'='*60}")
        print(f"SAMPLE SENTENCES mentioning: {detail_target}")
        print("=" * 60)
        for name, sents in sentences_map.items():
            if detail_target in name.lower():
                for s in sents[:15]:
                    if len(s) > 20:
                        print(f"  · {s[:200]}")
                break


if __name__ == "__main__":
    main()
