#!/usr/bin/env python3
"""
Fetch article URLs listed in urls.yaml → markdown files under corpus/.

Respects robots.txt via urllib.robotparser. Use responsibly; do not republish
full text. corpus/*.md is gitignored by default.
"""

from __future__ import annotations

import argparse
from typing import Any
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import requests
import yaml
from bs4 import BeautifulSoup

DEFAULT_SELECTORS = [
    "article",
    "main article",
    "main",
    '[role="main"]',
    ".entry-content",
    ".post-content",
    ".article-content",
    ".content",
]

SCRIPT_DIR = Path(__file__).resolve().parent


def load_config(path: Path) -> dict:
    raw = path.read_text(encoding="utf-8")
    return yaml.safe_load(raw) or {}


def robots_allowed(url: str, user_agent: str) -> tuple[bool, str]:
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        return False, "invalid_url"
    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
    rp = RobotFileParser()
    rp.set_url(robots_url)
    try:
        rp.read()
    except Exception as exc:
        return True, f"robots_unavailable ({exc!s})"
    try:
        ok = rp.can_fetch(user_agent or "*", url)
    except Exception as exc:
        return True, f"robots_check_error ({exc!s})"
    return ok, "ok" if ok else "disallowed_by_robots"


def slug_from_url(url: str) -> str:
    p = urlparse(url)
    path = p.path.strip("/") or "index"
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", path).strip("_").lower()
    if len(slug) > 80:
        slug = slug[:80]
    if not slug:
        slug = "page"
    host = re.sub(r"[^a-zA-Z0-9]+", "_", p.netloc.lower())
    return f"{host}__{slug}"


def extract_title(soup: BeautifulSoup) -> str:
    og = soup.find("meta", property="og:title")
    if og and og.get("content"):
        return og["content"].strip()
    t = soup.find("title")
    if t and t.string:
        return t.string.strip()
    h1 = soup.find("h1")
    if h1:
        return h1.get_text(strip=True)
    return ""


def extract_main_html(soup: BeautifulSoup, selectors: list[str]) -> BeautifulSoup | None:
    for sel in selectors:
        try:
            node = soup.select_one(sel)
        except Exception:
            node = None
        if node:
            return node
    return None


def html_to_markdownish(node: BeautifulSoup) -> str:
    for tag in node.find_all(["script", "style", "noscript", "iframe", "nav", "footer", "aside"]):
        tag.decompose()
    lines: list[str] = []
    for el in node.find_all(["p", "li", "h1", "h2", "h3", "h4", "blockquote", "pre"]):
        t = el.get_text(" ", strip=True)
        if not t or len(t) < 2:
            continue
        if el.name.startswith("h"):
            level = int(el.name[1])
            lines.append(f"\n{'#' * level} {t}\n")
        elif el.name == "li":
            lines.append(f"- {t}")
        elif el.name == "blockquote":
            lines.append(f"> {t}")
        elif el.name == "pre":
            lines.append(f"```\n{t}\n```")
        else:
            lines.append(t)
    if not lines:
        return node.get_text("\n\n", strip=True)
    return "\n\n".join(lines)


def fetch_one(
    session: requests.Session,
    url: str,
    user_agent: str,
    hosts_cfg: dict[str, Any],
) -> tuple[int, str, str]:
    headers = {"User-Agent": user_agent}
    r = session.get(url, headers=headers, timeout=45)
    r.raise_for_status()
    ctype = r.headers.get("Content-Type", "")
    if "html" not in ctype.lower() and not url.lower().endswith((".htm", ".html")):
        return r.status_code, "", f"skip_non_html: {ctype}"

    soup = BeautifulSoup(r.text, "html.parser")
    title = extract_title(soup)
    host = urlparse(url).netloc.split(":")[0]
    host_entry = hosts_cfg.get(host)
    if isinstance(host_entry, dict):
        extra = host_entry.get("article_selectors") or []
    else:
        extra = []
    selectors = list(extra) + list(DEFAULT_SELECTORS)
    main = extract_main_html(soup, selectors)
    if not main:
        return r.status_code, "", "no_main_content_selector_match"

    body = html_to_markdownish(main)
    if len(body.strip()) < 200:
        return r.status_code, "", "extracted_body_too_short"

    frontmatter = {
        "source_url": url,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "http_status": r.status_code,
        "title": title,
    }
    yaml_fm = yaml.safe_dump(frontmatter, allow_unicode=True, sort_keys=False).strip()
    md = f"---\n{yaml_fm}\n---\n\n{body}\n"
    return r.status_code, md, ""


def main() -> int:
    parser = argparse.ArgumentParser(description="Fetch URLs from urls.yaml into corpus/*.md")
    parser.add_argument(
        "--urls",
        type=Path,
        default=SCRIPT_DIR / "urls.yaml",
        help="YAML config with settings + urls list",
    )
    parser.add_argument("--out-dir", type=Path, default=SCRIPT_DIR / "corpus")
    parser.add_argument("--delay", type=float, default=None, help="Override settings.delay_seconds")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Ignore robots.txt disallow (use only when you have permission)",
    )
    args = parser.parse_args()

    if not args.urls.is_file():
        print(f"Missing {args.urls}; copy urls.example.yaml to urls.yaml and add URLs.", file=sys.stderr)
        return 1

    cfg = load_config(args.urls)
    settings = cfg.get("settings") or {}
    delay = float(args.delay if args.delay is not None else settings.get("delay_seconds", 1.5))
    user_agent = str(settings.get("user_agent") or "OnStyleResearch/1.0 (personal research)")
    hosts = cfg.get("hosts") or {}
    urls = cfg.get("urls") or []
    if isinstance(urls, str):
        urls = [urls]
    if not urls:
        print("No URLs in yaml (urls: []). Add entries and retry.", file=sys.stderr)
        return 1

    args.out_dir.mkdir(parents=True, exist_ok=True)
    session = requests.Session()

    ok_count = 0
    for i, item in enumerate(urls):
        if isinstance(item, dict):
            url = str(item.get("url") or item.get("href") or "").strip()
        else:
            url = str(item).strip()
        if not url or url.startswith("#"):
            continue
        slug = slug_from_url(url)
        out_path = args.out_dir / f"{slug}.md"

        allowed, robots_note = robots_allowed(url, user_agent)
        if not allowed and not args.force:
            print(f"SKIP robots: {url} ({robots_note})", file=sys.stderr)
            continue
        if not allowed and args.force:
            print(f"WARN force fetch disallowed URL: {url}", file=sys.stderr)

        try:
            status, md, err = fetch_one(session, url, user_agent, hosts)
        except requests.RequestException as exc:
            print(f"FAIL {url}: {exc}", file=sys.stderr)
            time.sleep(delay)
            continue

        if err:
            print(f"FAIL {url}: {err} (status={status})", file=sys.stderr)
            time.sleep(delay)
            continue

        out_path.write_text(md, encoding="utf-8")
        print(f"OK {url} -> {out_path.name} ({len(md)} chars)")
        ok_count += 1
        if i < len(urls) - 1:
            time.sleep(delay)

    print(f"Done. Wrote {ok_count} file(s) to {args.out_dir}")
    return 0 if ok_count else 2


if __name__ == "__main__":
    raise SystemExit(main())
