"""
m7_reddit/collect.py
─────────────────────
薄包装器：调用已有的 research/reddit_fetch_public.py，
将输出同步到 data/m7_reddit/ 目录，方便 M7 其他脚本使用。

用法:
    python collect.py                  # 抓取所有默认子版
    python collect.py --sub ibkr       # 只抓一个子版

输出:
    data/m7_reddit/reddit_*.json       (与 research/data/ 格式兼容)
"""

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from utils import section

RESEARCH_DIR = Path(__file__).parent.parent.parent / "research"
REDDIT_FETCH = RESEARCH_DIR / "reddit_fetch_public.py"
RESEARCH_DATA = RESEARCH_DIR / "data"
M7_DATA = Path(__file__).parent.parent.parent / "data" / "m7_reddit"
M7_DATA.mkdir(parents=True, exist_ok=True)

SUBREDDITS = ["MalaysianPF", "interactivebrokers", "malaysia", "ibkr"]


def collect(sub: str | None = None) -> None:
    section("M7 Reddit — collect.py")

    if not REDDIT_FETCH.exists():
        print(f"reddit_fetch_public.py not found at {REDDIT_FETCH}")
        print("Make sure you are in the correct project directory.")
        sys.exit(1)

    targets = [sub] if sub else SUBREDDITS
    for subreddit in targets:
        print(f"\nFetching r/{subreddit}...")
        result = subprocess.run(
            [sys.executable, str(REDDIT_FETCH), "--sub", subreddit],
            cwd=str(RESEARCH_DIR),
            capture_output=False,
        )
        if result.returncode != 0:
            print(f"  WARNING: fetch returned code {result.returncode} for r/{subreddit}")

    # 同步到 m7_reddit/
    copied = 0
    for f in RESEARCH_DATA.glob("reddit_*.json"):
        dest = M7_DATA / f.name
        shutil.copy2(f, dest)
        copied += 1

    print(f"\nSynced {copied} JSON files to {M7_DATA}")


def main():
    parser = argparse.ArgumentParser(description="Fetch Reddit data for M7 analysis.")
    parser.add_argument("--sub", type=str, default=None,
                        help=f"Single subreddit to fetch. Default: all {SUBREDDITS}")
    args = parser.parse_args()
    collect(sub=args.sub)


if __name__ == "__main__":
    main()
