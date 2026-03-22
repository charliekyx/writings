"""
Browser-like HTTP fetch via Playwright (Chromium) for sites that block plain requests.

Used by M3/M5/M8 when STRICT / authoritative sources require real page loads.

Some banks (e.g. Maybank) trigger Chromium ``ERR_HTTP2_PROTOCOL_ERROR``; default launch
args disable HTTP/2 and QUIC so TLS falls back to HTTP/1.1. Override with
``PLAYWRIGHT_CHROMIUM_ARGS`` (space-separated) if needed.
"""

from __future__ import annotations

import os

CHROME_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
)


def playwright_available() -> bool:
    try:
        from playwright.sync_api import sync_playwright  # noqa: F401

        return True
    except ImportError:
        return False


def chromium_launch_args() -> list[str]:
    """
    Extra Chromium flags. Empty PLAYWRIGHT_CHROMIUM_ARGS means use defaults
    that avoid flaky HTTP/2 to some corporate sites.
    """
    raw = os.environ.get("PLAYWRIGHT_CHROMIUM_ARGS", "").strip()
    if raw == "-":
        return []
    if raw:
        return [x.strip() for x in raw.split() if x.strip()]
    return [
        "--disable-http2",
        "--disable-quic",
    ]


def _launch_chromium(p):
    return p.chromium.launch(headless=True, args=chromium_launch_args())


def fetch_page_html(
    url: str,
    *,
    timeout_ms: int = 120_000,
    wait_after_ms: int = 3000,
    locale: str = "en-MY",
    wait_until: str = "domcontentloaded",
) -> str:
    """
    Load URL in headless Chromium and return rendered HTML.

    ``wait_until``:
      - ``domcontentloaded`` — full DOM (may never fire on slow/broken sites).
      - ``commit`` — first response received; use longer ``wait_after_ms`` for JS tables.
    """
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = _launch_chromium(p)
        context = browser.new_context(
            user_agent=CHROME_UA,
            locale=locale,
            extra_http_headers={"Accept-Language": f"{locale},en;q=0.9"},
        )
        page = context.new_page()
        page.goto(url, wait_until=wait_until, timeout=timeout_ms)
        page.wait_for_timeout(wait_after_ms)
        html = page.content()
        context.close()
        browser.close()
    return html


def fetch_response_body(
    url: str,
    *,
    timeout_ms: int = 120_000,
    referer: str | None = None,
) -> tuple[bytes, str, int]:
    """
    Navigate to URL and return (body, content-type, status).
    Suitable for PDF and binary responses when server returns 200.
    """
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = _launch_chromium(p)
        extra: dict[str, str] = {"Accept-Language": "en-MY,en;q=0.9"}
        if referer:
            extra["Referer"] = referer
        context = browser.new_context(
            user_agent=CHROME_UA,
            extra_http_headers=extra,
        )
        page = context.new_page()
        resp = page.goto(url, wait_until="commit", timeout=timeout_ms)
        status = resp.status if resp else 0
        if not resp or not resp.ok:
            context.close()
            browser.close()
            raise RuntimeError(f"HTTP {status} for {url}")
        body = resp.body()
        ctype = resp.headers.get("content-type", "")
        context.close()
        browser.close()
    return body, ctype, status


def fetch_pdf_via_policy_page(
    policy_page_url: str,
    *,
    timeout_ms: int = 120_000,
) -> tuple[bytes, str]:
    """
    Open policy HTML page, pick first relevant .pdf link, then fetch PDF bytes.
    Returns (pdf_bytes, pdf_url_used).
    """
    import re
    from urllib.parse import urljoin

    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = _launch_chromium(p)
        context = browser.new_context(
            user_agent=CHROME_UA,
            extra_http_headers={"Accept-Language": "en-MY,en;q=0.9"},
        )
        page = context.new_page()
        page.goto(policy_page_url, wait_until="domcontentloaded", timeout=timeout_ms)
        page.wait_for_timeout(2000)
        html = page.content()
        hrefs = re.findall(
            r'href\s*=\s*["\']([^"\']+\.pdf[^"\']*)["\']',
            html,
            flags=re.I,
        )
        candidates = []
        for h in hrefs:
            full = urljoin(policy_page_url, h)
            low = full.lower()
            if any(
                k in low
                for k in ("fep", "foreign", "exchange", "policy", "fe")
            ):
                candidates.append(full)
        if not candidates and hrefs:
            candidates = [urljoin(policy_page_url, hrefs[0])]
        if not candidates:
            context.close()
            browser.close()
            raise RuntimeError("No PDF link found on policy page")

        pdf_url = candidates[0]
        resp = page.goto(pdf_url, wait_until="commit", timeout=timeout_ms)
        if not resp or not resp.ok:
            st = resp.status if resp else 0
            context.close()
            browser.close()
            raise RuntimeError(f"PDF URL failed HTTP {st}: {pdf_url}")
        data = resp.body()
        context.close()
        browser.close()
    return data, pdf_url
