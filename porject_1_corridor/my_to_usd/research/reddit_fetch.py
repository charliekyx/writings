#!/usr/bin/env python3
"""
Fetch Reddit posts (and top-level comments) for MYR→USD/IBKR corridor research.
Saves one JSON file per subreddit per search term under data/.

Requires: REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET, REDDIT_USER_AGENT.
"""

import os
import json
import re
from pathlib import Path
from datetime import datetime

try:
    import praw
except ImportError:
    raise SystemExit("Install praw: pip install praw")

# --- Config: edit for your corridor / keywords ---
SUBREDDITS = [
    "Malaysia",
    "MalaysianPF",
    "interactivebrokers",
    "ibkr",
]
SEARCH_TERMS = [
    "MYR IBKR",
    "Malaysia IBKR",
    "MYR wire",
    "Wise MYR",
    "SWIFT Malaysia",
    "IBKR deposit",
    "hidden spread",
    "IBKR fees",
]
MAX_POSTS_PER_SEARCH = 50  # limit per (subreddit, query) to avoid rate limits
OUTPUT_DIR = Path(__file__).resolve().parent / "data"


def slug(s: str) -> str:
    return re.sub(r"[^\w\-]", "_", s.strip())[:60]


def fetch_reddit():
    client_id = os.environ.get("REDDIT_CLIENT_ID")
    client_secret = os.environ.get("REDDIT_CLIENT_SECRET")
    user_agent = os.environ.get("REDDIT_USER_AGENT", "corridor-research/1.0")
    if not client_id or not client_secret:
        raise SystemExit("Set REDDIT_CLIENT_ID and REDDIT_CLIENT_SECRET")

    reddit = praw.Reddit(
        client_id=client_id,
        client_secret=client_secret,
        user_agent=user_agent,
    )

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    seen_ids = set()

    for sub_name in SUBREDDITS:
        sub = reddit.subreddit(sub_name)
        for q in SEARCH_TERMS:
            out_path = OUTPUT_DIR / f"reddit_{slug(sub_name)}_{slug(q)}.json"
            rows = []
            try:
                for post in sub.search(q, limit=MAX_POSTS_PER_SEARCH, time_filter="all"):
                    if post.id in seen_ids:
                        continue
                    seen_ids.add(post.id)
                    row = {
                        "id": post.id,
                        "subreddit": sub_name,
                        "search_term": q,
                        "title": post.title,
                        "selftext": getattr(post, "selftext", "") or "",
                        "created_utc": post.created_utc,
                        "score": post.score,
                        "num_comments": post.num_comments,
                        "url": f"https://reddit.com{post.permalink}",
                    }
                    # optional: top-level comments (uncomment to fetch)
                    # post.comments.replace_more(limit=0)
                    # row["comments"] = [c.body[:2000] for c in post.comments.list()[:50] if hasattr(c, "body")]
                    rows.append(row)
            except Exception as e:
                print(f"Error {sub_name} / {q}: {e}")
                continue

            meta = {
                "subreddit": sub_name,
                "search_term": q,
                "fetched_at": datetime.utcnow().isoformat() + "Z",
                "count": len(rows),
            }
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump({"meta": meta, "posts": rows}, f, ensure_ascii=False, indent=2)
            print(f"Wrote {out_path} ({len(rows)} posts)")


if __name__ == "__main__":
    fetch_reddit()
