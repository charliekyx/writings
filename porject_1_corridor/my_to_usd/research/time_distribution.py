#!/usr/bin/env python3
"""
Read all data/reddit_*.json and output post count by year (and year-month).
Optionally: count posts that contain anxiety-related terms, by year.
Usage: python time_distribution.py
"""

import json
from pathlib import Path
from collections import defaultdict
from datetime import datetime, timezone

DATA_DIR = Path(__file__).resolve().parent / "data"
ANXIETY_TERMS = {"fee", "fees", "spread", "wire", "swift", "cost", "transfer", "wise", "bank", "hidden", "rate", "myr", "usd", "ibkr"}


def main():
    by_year = defaultdict(int)
    by_ym = defaultdict(int)
    anxiety_by_year = defaultdict(int)
    total = 0

    for path in sorted(DATA_DIR.glob("reddit_*.json")):
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            print(f"Skip {path}: {e}")
            continue
        for post in data.get("posts", []):
            ts = post.get("created_utc")
            if not ts:
                continue
            total += 1
            try:
                dt = datetime.fromtimestamp(float(ts), timezone.utc)
            except (TypeError, OSError):
                continue
            y = dt.year
            ym = dt.strftime("%Y-%m")
            by_year[y] += 1
            by_ym[ym] += 1
            text = ((post.get("title") or "") + " " + (post.get("selftext") or "")).lower()
            if any(t in text for t in ANXIETY_TERMS):
                anxiety_by_year[y] += 1

    print("Post count by year:")
    for y in sorted(by_year):
        print(f"  {y}: {by_year[y]}")
    print("\nPost count by year-month (recent first):")
    for ym in sorted(by_ym, reverse=True)[:24]:
        print(f"  {ym}: {by_ym[ym]}")
    print(f"\nTotal posts: {total}")
    print("\nPosts containing anxiety-related terms (fee/spread/wire/swift/cost/transfer/...) by year:")
    for y in sorted(anxiety_by_year):
        print(f"  {y}: {anxiety_by_year[y]}")


if __name__ == "__main__":
    main()
