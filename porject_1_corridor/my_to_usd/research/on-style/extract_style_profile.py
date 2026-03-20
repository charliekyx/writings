#!/usr/bin/env python3
"""
Read corpus/*.md (fetched or local), compute style heuristics, write JSON + Markdown brief.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

import yaml

from style_heuristics import aggregate_docs, analyze_text, opening_pattern_tags

SCRIPT_DIR = Path(__file__).resolve().parent

FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


def parse_md_body(path: Path) -> tuple[dict[str, Any], str]:
    raw = path.read_text(encoding="utf-8")
    meta: dict[str, Any] = {}
    body = raw
    m = FRONTMATTER_RE.match(raw)
    if m:
        try:
            meta = yaml.safe_load(m.group(1)) or {}
        except yaml.YAMLError:
            meta = {}
        body = raw[m.end() :]
    return meta, body


def main() -> int:
    parser = argparse.ArgumentParser(description="Build style profile from corpus markdown")
    parser.add_argument("--corpus-dir", type=Path, default=SCRIPT_DIR / "corpus")
    parser.add_argument("--out-dir", type=Path, default=SCRIPT_DIR / "output")
    parser.add_argument("--min-chars", type=int, default=500)
    args = parser.parse_args()

    if not args.corpus_dir.is_dir():
        print(f"Missing corpus dir: {args.corpus_dir}", file=sys.stderr)
        return 1

    files = sorted(args.corpus_dir.glob("*.md"))
    if not files:
        print(f"No .md files in {args.corpus_dir}. Run fetch_corpus.py first.", file=sys.stderr)
        return 1

    per_doc: list[dict[str, Any]] = []
    for fp in files:
        meta, body = parse_md_body(fp)
        if len(body.strip()) < args.min_chars:
            print(f"SKIP too_short: {fp.name}", file=sys.stderr)
            continue
        label = meta.get("source_url") or meta.get("title") or fp.stem
        row = analyze_text(body, source_label=str(label))
        row["corpus_file"] = fp.name
        row["meta_title"] = meta.get("title")
        per_doc.append(row)

    if not per_doc:
        print("No documents passed min-chars.", file=sys.stderr)
        return 2

    agg = aggregate_docs(per_doc)
    tag_counter: dict[str, int] = {}
    for row in per_doc:
        for t in opening_pattern_tags(row):
            tag_counter[t] = tag_counter.get(t, 0) + 1

    args.out_dir.mkdir(parents=True, exist_ok=True)
    profile_path = args.out_dir / "style_profile.json"
    brief_path = args.out_dir / "style_brief.md"

    payload = {
        "aggregate": agg,
        "tag_counts_across_docs": dict(sorted(tag_counter.items(), key=lambda x: -x[1])),
        "documents": per_doc,
    }
    profile_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    lines = [
        "# Style brief (heuristic)",
        "",
        "Use as a **checklist of mechanisms**, not copy-paste phrasing. Interpret with your own topic and data.",
        "",
        f"Documents analyzed: **{len(per_doc)}**",
        "",
        "## Cross-document pattern tags",
        "",
    ]
    for tag, c in sorted(tag_counter.items(), key=lambda x: -x[1]):
        lines.append(f"- `{tag}` — {c} doc(s)")
    lines.extend(["", "## Aggregate numeric hints (means)", ""])
    for k, v in sorted(agg.items()):
        if k.endswith("_mean") and isinstance(v, (int, float)):
            lines.append(f"- **{k}**: {v}")
    lines.extend(
        [
            "",
            "## Per-document tags",
            "",
        ]
    )
    for row in per_doc:
        tags = opening_pattern_tags(row)
        src = row.get("source_label", "")
        lines.append(f"- {src}: {', '.join(tags) if tags else '(no tags)'}")

    brief_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote {profile_path}")
    print(f"Wrote {brief_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
