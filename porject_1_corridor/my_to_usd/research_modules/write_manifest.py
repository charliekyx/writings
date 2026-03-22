#!/usr/bin/env python3
"""Write data/run_manifest.json after a pipeline run (git sha, env flags)."""

import datetime
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
DATA.mkdir(parents=True, exist_ok=True)


def main() -> None:
    try:
        sha = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        ).stdout.strip()
    except Exception:
        sha = "unknown"
    manifest = {
        "generated_at": datetime.datetime.now(datetime.timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        ),
        "git_sha": sha or "unknown",
        "strict_auto": os.environ.get("STRICT_AUTO", ""),
        "wise_api_configured": bool(os.environ.get("WISE_API_TOKEN", "").strip()),
        "data_quality_notes": {
            "m1_m2": "Wise API / Instarem public API — institution-sourced quotes.",
            "m3_bank_tt": (
                "TT rate and wire fee must come from each bank's own pages "
                "(requests or Playwright); no cross-bank or BNM-substitute labels."
            ),
            "m5_m8": "BNM PDF / Revolut help — browser fetch (Playwright) when requests returns 403.",
        },
    }
    out = DATA / "run_manifest.json"
    out.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"Wrote {out}")


if __name__ == "__main__":
    main()
