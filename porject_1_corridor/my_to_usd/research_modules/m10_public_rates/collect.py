"""
m10_public_rates/collect.py
───────────────────────────
抓取 Merchantrade / BigPay 官网费率与条款页快照（无公开 API 时的自动化来源）。

输出:
  data/m10_public_rates/*.html
  data/m10_public_rates/summary.json
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

DATA_DIR = Path(__file__).parent.parent.parent / "data" / "m10_public_rates"
DATA_DIR.mkdir(parents=True, exist_ok=True)

DEFAULT_TARGETS = [
    ("merchantrade_fees", "https://www.merchantrademoney.com/fees/"),
    ("bigpay_fees", "https://www.bigpayme.com/fees-charges"),
    ("bigpay_intl", "https://www.bigpayme.com/international-bank-transfers"),
]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    ),
}


def main():
    section("M10 Merchantrade/BigPay pages — collect.py")
    strict = os.environ.get("STRICT_AUTO", "").lower() in ("1", "true", "yes")
    summary = {
        "collected_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "pages": [],
    }
    ok_count = 0

    for name, url in DEFAULT_TARGETS:
        try:
            r = requests.get(url, headers=HEADERS, timeout=25)
            r.raise_for_status()
            body = r.text
            h = hashlib.sha256(body.encode("utf-8", errors="replace")).hexdigest()
            out = DATA_DIR / f"{name}.html"
            out.write_text(body, encoding="utf-8", errors="replace")
            summary["pages"].append(
                {
                    "id": name,
                    "url": url,
                    "status": r.status_code,
                    "content_sha256": h,
                    "path": str(out.relative_to(DATA_DIR.parent.parent)),
                }
            )
            ok_count += 1
            print(f"  OK {name} <- {url}")
        except Exception as e:
            summary["pages"].append({"id": name, "url": url, "error": str(e)})
            print(f"  FAIL {name}: {e}")

    (DATA_DIR / "summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    if ok_count == 0 and strict:
        print("STRICT_AUTO: no M10 pages fetched.", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
