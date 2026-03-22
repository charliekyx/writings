"""
m9_ibkr_funding/collect.py
──────────────────────────
拉取 IBKR 官方 funding 参考页（机读来源），保存 HTML + 摘要。

默认 URL: MYR Deposits and Withdrawals

输出:
  data/m9_ibkr_funding/myr_deposits.html
  data/m9_ibkr_funding/summary.json
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

DATA_DIR = Path(__file__).parent.parent.parent / "data" / "m9_ibkr_funding"
DATA_DIR.mkdir(parents=True, exist_ok=True)

DEFAULT_URL = os.environ.get(
    "IBKR_MYR_FUNDING_URL",
    "https://ibkrguides.com/fundingreference/myr.htm",
)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; IBKR-funding-snapshot/1.0; research)"
    ),
}


def main():
    section("M9 IBKR funding — collect.py")
    strict = os.environ.get("STRICT_AUTO", "").lower() in ("1", "true", "yes")

    try:
        r = requests.get(DEFAULT_URL, headers=HEADERS, timeout=30)
        r.raise_for_status()
        body = r.text
    except Exception as e:
        print(f"  Fetch failed: {e}")
        if strict:
            sys.exit(1)
        return

    h = hashlib.sha256(body.encode("utf-8", errors="replace")).hexdigest()
    out_html = DATA_DIR / "myr_deposits.html"
    out_html.write_text(body, encoding="utf-8", errors="replace")

    # 粗略正文：去 tag 后取前 8k 字符便于检索（非严谨 NLP）
    import re

    text = re.sub(r"<script[^>]*>[\s\S]*?</script>", " ", body, flags=re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()[:8000]

    summary = {
        "collected_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source_url": DEFAULT_URL,
        "content_sha256": h,
        "html_path": str(out_html.relative_to(DATA_DIR.parent.parent)),
        "text_preview": text,
    }
    (DATA_DIR / "summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"  Saved {out_html.name} sha256={h[:16]}...")


if __name__ == "__main__":
    main()
