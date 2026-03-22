"""
m8_revolut/collect.py
─────────────────────
抓取 Revolut 公开帮助/产品页（无 Business API 时的 B 路径），保存原文供审计。

优先使用 Playwright（Chromium）加载页面；失败时回退 requests。
环境变量:
  STRICT_AUTO=1 且所有 URL 均失败时 exit 1

输出:
  data/m8_revolut/*.html / summary.json
"""

import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).parent.parent))
from utils import section

DATA_DIR = Path(__file__).parent.parent.parent / "data" / "m8_revolut"
DATA_DIR.mkdir(parents=True, exist_ok=True)

DEFAULT_URLS = [
    "https://help.revolut.com/help/malaysia/",
    "https://www.revolut.com/en-MY/help/",
    "https://www.revolut.com/legal/",
]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-MY,en;q=0.9",
}


def _fetch_requests(url: str) -> str:
    r = requests.get(url, headers=HEADERS, timeout=35)
    r.raise_for_status()
    return r.text


def _fetch_playwright(url: str) -> str:
    from playwright_helper import fetch_page_html

    return fetch_page_html(url, timeout_ms=90_000, wait_after_ms=4000, locale="en-MY")


def main():
    section("M8 Revolut — collect.py")
    strict = os.environ.get("STRICT_AUTO", "").lower() in ("1", "true", "yes")
    urls_env = os.environ.get("REVOLUT_HELP_URLS", "").strip()
    urls = [u.strip() for u in urls_env.split(",") if u.strip()] if urls_env else DEFAULT_URLS

    summary = {
        "collected_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "pages": [],
    }
    any_ok = False

    for url in urls:
        body: str | None = None
        method = ""
        err: str | None = None
        try:
            body = _fetch_requests(url)
            method = "requests"
        except Exception as e:
            err = str(e)
            try:
                body = _fetch_playwright(url)
                method = "playwright"
                err = None
            except Exception as e2:
                err = f"requests: {e}; playwright: {e2}"

        if body is not None:
            h = hashlib.sha256(body.encode("utf-8", errors="replace")).hexdigest()[:16]
            safe_name = hashlib.sha256(url.encode()).hexdigest()[:12] + ".html"
            out = DATA_DIR / safe_name
            out.write_text(body, encoding="utf-8", errors="replace")
            summary["pages"].append(
                {
                    "url": url,
                    "fetch_method": method,
                    "bytes": len(body.encode("utf-8", errors="replace")),
                    "content_sha256_16": h,
                    "saved_path": str(out.relative_to(DATA_DIR.parent.parent)),
                }
            )
            any_ok = True
            print(f"  OK {method} {url} -> {out.name} sha16={h}")
        else:
            summary["pages"].append({"url": url, "error": err})
            print(f"  FAIL {url}: {err}")

    (DATA_DIR / "summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    if not any_ok and strict:
        print("STRICT_AUTO: no Revolut pages fetched.", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
