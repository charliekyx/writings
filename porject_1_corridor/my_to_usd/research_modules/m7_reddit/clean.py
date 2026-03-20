"""
m7_reddit/clean.py
───────────────────
扩展 keyword_frequency.py：
  - 增加二元组（bigrams）统计
  - 按年份分组（用于趋势图）

用法:
    python clean.py

输出:
    data/m7_reddit/unigrams_by_year.csv
    data/m7_reddit/bigrams_by_year.csv
    data/m7_reddit/route_mentions_by_year.csv
"""

import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))
from utils import section

DATA_DIR = Path(__file__).parent.parent.parent / "data" / "m7_reddit"
DATA_DIR.mkdir(parents=True, exist_ok=True)

STOP_WORDS = {
    "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "is", "it", "are", "was", "be", "have", "has", "had",
    "do", "does", "did", "will", "would", "could", "should", "may", "might",
    "i", "you", "he", "she", "we", "they", "my", "your", "this", "that",
    "not", "if", "so", "as", "from", "by", "can", "just", "when", "also",
    "any", "more", "like", "up", "about", "than", "then", "been",
}

ROUTE_PATTERNS = {
    "Wise": ["wise", "transferwise"],
    "Instarem": ["instarem"],
    "Revolut": ["revolut"],
    "CIMB SG": ["cimb sg", "cimb singapore"],
    "HSBC Hop": ["hsbc"],
    "Maybank": ["maybank"],
    "CIMB": ["cimb"],
    "PayPal": ["paypal"],
    "Bank TT/SWIFT": ["swift tt", "telegraphic", r"\btt\b"],
    "Crypto": ["usdt", "binance", "crypto"],
    "IDEALPRO": ["idealpro"],
}


def extract_posts(data_dir: Path) -> list[dict]:
    """从 JSON 文件提取 {year, text} 对。"""
    posts = []
    for f in sorted(data_dir.glob("reddit_*.json")):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            continue
        items = data.get("posts", data) if isinstance(data, dict) else data
        for item in items:
            if not isinstance(item, dict):
                continue
            # 提取年份
            created = item.get("created_utc") or item.get("created", 0)
            year = None
            if created:
                from datetime import datetime, timezone
                try:
                    year = datetime.fromtimestamp(float(created), tz=timezone.utc).year
                except Exception:
                    pass
            text = " ".join([
                item.get("title", ""),
                item.get("selftext", ""),
            ] + [c.get("body", "") for c in item.get("comments", [])])
            posts.append({"year": year, "text": text.lower()})
    return posts


def tokenize(text: str) -> list[str]:
    words = re.findall(r"[a-z][a-z']+", text)
    return [w for w in words if w not in STOP_WORDS and len(w) > 2]


def bigrams(tokens: list[str]) -> list[str]:
    return [f"{tokens[i]} {tokens[i+1]}" for i in range(len(tokens) - 1)]


def count_route_mentions(text: str) -> dict:
    result = {}
    for route, patterns in ROUTE_PATTERNS.items():
        compiled = [re.compile(p, re.IGNORECASE) for p in patterns]
        result[route] = 1 if any(rx.search(text) for rx in compiled) else 0
    return result


def clean() -> None:
    section("M7 Reddit — clean.py")
    posts = extract_posts(DATA_DIR)
    if not posts:
        # 尝试从 research/data 读取
        research_data = Path(__file__).parent.parent.parent / "research" / "data"
        posts = extract_posts(research_data)

    if not posts:
        print("No Reddit data found. Run collect.py first.")
        sys.exit(1)

    print(f"Loaded {len(posts)} posts/segments.")

    uni_by_year: dict[int, Counter] = defaultdict(Counter)
    bi_by_year: dict[int, Counter] = defaultdict(Counter)
    route_by_year: dict[int, dict] = defaultdict(lambda: defaultdict(int))

    for post in posts:
        year = post["year"] or 9999
        tokens = tokenize(post["text"])
        uni_by_year[year].update(tokens)
        bi_by_year[year].update(bigrams(tokens))
        for route, hit in count_route_mentions(post["text"]).items():
            route_by_year[year][route] += hit

    # 输出 unigrams
    uni_rows = []
    for year, counts in sorted(uni_by_year.items()):
        for word, cnt in counts.most_common(100):
            uni_rows.append({"year": year, "word": word, "count": cnt})
    pd.DataFrame(uni_rows).to_csv(DATA_DIR / "unigrams_by_year.csv", index=False)

    # 输出 bigrams
    bi_rows = []
    for year, counts in sorted(bi_by_year.items()):
        for bigram, cnt in counts.most_common(50):
            bi_rows.append({"year": year, "bigram": bigram, "count": cnt})
    pd.DataFrame(bi_rows).to_csv(DATA_DIR / "bigrams_by_year.csv", index=False)

    # 输出 route mentions by year
    route_rows = []
    for year, routes in sorted(route_by_year.items()):
        for route, cnt in routes.items():
            route_rows.append({"year": year, "route": route, "mentions": cnt})
    rdf = pd.DataFrame(route_rows)
    rdf.to_csv(DATA_DIR / "route_mentions_by_year.csv", index=False)

    print(f"Saved: unigrams_by_year.csv, bigrams_by_year.csv, route_mentions_by_year.csv")
    print("\nTop bigrams (all years):")
    all_bi: Counter = sum(bi_by_year.values(), Counter())
    for bigram, cnt in all_bi.most_common(15):
        print(f"  {bigram:<30} {cnt:>5}")


if __name__ == "__main__":
    clean()
