#!/usr/bin/env python3
"""
Fetch Reddit posts via public JSON endpoints (no API app required).
Saves one JSON file per subreddit per search term under data/.
Output format matches reddit_fetch.py so keyword_frequency.py works unchanged.
"""

import json
import re
import time
import urllib.parse
from pathlib import Path
from datetime import datetime

try:
    import urllib.request
    HAS_URLLIB = True
except ImportError:
    HAS_URLLIB = False

# Prefer requests if available (clearer for timeouts/errors)
try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

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
MAX_POSTS_PER_SEARCH = 25  # public API is stricter; keep modest
REQUEST_DELAY_SEC = 2  # be polite to Reddit
OUTPUT_DIR = Path(__file__).resolve().parent / "data"
USER_AGENT = "corridor-research/1.0 (research; no API key)"


def slug(s: str) -> str:
    return re.sub(r"[^\w\-]", "_", s.strip())[:60]


def get_url(url: str) -> dict:
    if HAS_REQUESTS:
        r = requests.get(
            url,
            headers={"User-Agent": USER_AGENT},
            timeout=15,
        )
        r.raise_for_status()
        return r.json()
    if HAS_URLLIB:
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode())
    raise SystemExit("Install requests: pip install requests")


def fetch_reddit_public():
    if not HAS_REQUESTS and not HAS_URLLIB:
        raise SystemExit("Install requests: pip install requests")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    seen_ids = set()

    for sub_name in SUBREDDITS:
        for q in SEARCH_TERMS:
            # Reddit search: /r/SUBREDDIT/search.json?q=...&restrict_sr=on&limit=...
            query = urllib.parse.quote(q.strip())
            url = (
                f"https://www.reddit.com/r/{sub_name}/search.json"
                f"?q={query}&restrict_sr=on&limit={MAX_POSTS_PER_SEARCH}&sort=relevance"
            )
            out_path = OUTPUT_DIR / f"reddit_{slug(sub_name)}_{slug(q)}.json"
            rows = []
            try:
                data = get_url(url)
                time.sleep(REQUEST_DELAY_SEC)
            except Exception as e:
                print(f"Error {sub_name} / {q}: {e}")
                continue

            for child in data.get("data", {}).get("children", []):
                d = child.get("data", {})
                post_id = d.get("id")
                if not post_id or post_id in seen_ids:
                    continue
                seen_ids.add(post_id)
                permalink = d.get("permalink", "")
                if not permalink.startswith("/"):
                    permalink = "/" + permalink
                row = {
                    "id": post_id,
                    "subreddit": sub_name,
                    "search_term": q,
                    "title": d.get("title") or "",
                    "selftext": d.get("selftext") or "",
                    "created_utc": d.get("created_utc"),
                    "score": d.get("score", 0),
                    "num_comments": d.get("num_comments", 0),
                    "url": f"https://reddit.com{permalink}",
                }
                rows.append(row)

            meta = {
                "subreddit": sub_name,
                "search_term": q,
                "fetched_at": datetime.utcnow().isoformat() + "Z",
                "count": len(rows),
                "source": "public_json",
            }
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump({"meta": meta, "posts": rows}, f, ensure_ascii=False, indent=2)
            print(f"Wrote {out_path} ({len(rows)} posts)")


if __name__ == "__main__":
    fetch_reddit_public()
