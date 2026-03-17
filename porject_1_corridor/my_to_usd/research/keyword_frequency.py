#!/usr/bin/env python3
"""
Compute word and bigram frequency from Reddit JSON (or a CSV with a 'text' column).
Writes data/keyword_frequency_<date>.csv.

Usage:
  python keyword_frequency.py
  python keyword_frequency.py --input data/reddit_*.json
  python keyword_frequency.py --input my_posts.csv --text-column body
"""

import argparse
import json
import re
from pathlib import Path
from datetime import datetime
from collections import Counter

# Optional: better tokenization
try:
    import pandas as pd
    HAS_PANDAS = True
except ImportError:
    HAS_PANDAS = False

OUTPUT_DIR = Path(__file__).resolve().parent / "data"

# Terms we care about for corridor (cost/fees/spread/route); count these explicitly too
FOCUS_TERMS = [
    "fee", "fees", "spread", "cost", "rate", "rates", "wire", "swift",
    "myr", "usd", "ibkr", "wise", "transfer", "bank", "conversion",
    "hidden", "intermediary", "exchange", "deposit", "receive", "received",
]


def slug(s: str) -> str:
    return re.sub(r"[^\w\-]", "_", s.strip().lower())[:80]


def tokenize(text: str) -> list[str]:
    """Simple word tokenization: letters/numbers, lowercased."""
    if not text:
        return []
    text = text.lower()
    tokens = re.findall(r"[a-z0-9]+", text)
    return [t for t in tokens if len(t) > 1]


def bigrams(tokens: list[str]) -> list[tuple[str, str]]:
    return list(zip(tokens[:-1], tokens[1:])) if len(tokens) > 1 else []


def load_reddit_jsons(glob_path: str) -> list[str]:
    base = Path(__file__).resolve().parent
    texts = []
    for path in base.glob(glob_path.lstrip("./")):
        if not path.suffix == ".json":
            continue
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            for post in data.get("posts", []):
                title = post.get("title") or ""
                selftext = post.get("selftext") or ""
                texts.append(f"{title}\n{selftext}")
        except Exception as e:
            print(f"Skip {path}: {e}")
    return texts


def main():
    ap = argparse.ArgumentParser(description="Keyword frequency from Reddit JSON or CSV")
    ap.add_argument("--input", default="data/reddit_*.json", help="Glob for JSON or path to CSV")
    ap.add_argument("--text-column", default="text", help="CSV column for text (or title+selftext for JSON)")
    ap.add_argument("--top", type=int, default=200, help="Top N words and bigrams to keep")
    args = ap.parse_args()

    input_path = Path(args.input)
    texts = []

    if "*" in str(input_path) or str(input_path).endswith(".json"):
        texts = load_reddit_jsons(str(input_path))
    elif input_path.suffix.lower() == ".csv" and HAS_PANDAS:
        df = pd.read_csv(input_path)
        col = args.text_column
        if col not in df.columns:
            raise SystemExit(f"CSV must have column: {col}")
        texts = df[col].fillna("").astype(str).tolist()
    else:
        raise SystemExit("Use --input with data/reddit_*.json or a CSV path")

    if not texts:
        print("No text collected. Check --input paths.")
        return

    all_tokens = []
    for t in texts:
        all_tokens.extend(tokenize(t))

    word_counts = Counter(all_tokens)
    bigram_counts = Counter(bigrams(all_tokens))
    bigram_str = Counter(f"{a} {b}" for a, b in bigram_counts)

    # Focus terms: ensure they appear in output with count (may be 0)
    focus_counts = {slug(term): word_counts.get(term.lower(), 0) for term in FOCUS_TERMS}

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    date_suffix = datetime.now().strftime("%Y%m%d")
    out_csv = OUTPUT_DIR / f"keyword_frequency_{date_suffix}.csv"

    rows = []
    for word, count in word_counts.most_common(args.top):
        rows.append({"type": "word", "term": word, "count": count})
    for big, count in bigram_str.most_common(args.top):
        rows.append({"type": "bigram", "term": big, "count": count})
    seen_terms = {r["term"] for r in rows}
    for term, count in sorted(focus_counts.items(), key=lambda x: -x[1]):
        if term and term not in seen_terms:
            rows.append({"type": "focus", "term": term, "count": count})
            seen_terms.add(term)

    if HAS_PANDAS:
        pd.DataFrame(rows).to_csv(out_csv, index=False)
    else:
        import csv
        with open(out_csv, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=["type", "term", "count"])
            w.writeheader()
            w.writerows(rows)

    print(f"Wrote {out_csv} ({len(rows)} rows from {len(texts)} documents)")


if __name__ == "__main__":
    main()
