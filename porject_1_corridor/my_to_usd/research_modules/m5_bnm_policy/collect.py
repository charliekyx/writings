"""
m5_bnm_policy/collect.py
─────────────────────────
下载 BNM Foreign Exchange Policy 文件，提取关键文本。

BNM FEK 文件通常是 PDF，存放在 BNM 官网:
  https://www.bnm.gov.my/foreign-exchange-policy

用法:
    python collect.py                   # 下载最新 FEP 文件
    python collect.py --local FILE.pdf  # 使用本地已下载的 PDF

输出:
    data/m5_bnm_policy/bnm_fek_raw.pdf
    data/m5_bnm_policy/bnm_fek_text.txt   (纯文本提取)
    data/m5_bnm_policy/metadata.json
"""

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin

sys.path.insert(0, str(Path(__file__).parent.parent))
from utils import section

DATA_DIR = Path(__file__).parent.parent.parent / "data" / "m5_bnm_policy"
DATA_DIR.mkdir(parents=True, exist_ok=True)
PDF_PATH = DATA_DIR / "bnm_fek_raw.pdf"
TEXT_PATH = DATA_DIR / "bnm_fek_text.txt"
META_PATH = DATA_DIR / "metadata.json"

# BNM 官网外汇政策页（手动确认最新链接）
BNM_FEP_PAGE = "https://www.bnm.gov.my/foreign-exchange-policy"
# 下次更新时替换为直接 PDF 链接:
BNM_FEP_PDF_DIRECT = (
    "https://www.bnm.gov.my/documents/20124/166931/FEP+"
    "effective+2+May+2023.pdf"
)

_BNM_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-MY,en;q=0.9",
}


def discover_pdf_url_from_policy_page() -> str | None:
    """
    Parse BNM foreign-exchange-policy HTML for .pdf links (FEP / foreign exchange).
    """
    import requests

    try:
        resp = requests.get(
            BNM_FEP_PAGE,
            timeout=45,
            headers=_BNM_HEADERS,
        )
        resp.raise_for_status()
        text = resp.text
    except Exception as e:
        print(f"  Policy page fetch failed: {e}")
        return None

    # href="...pdf" or href='...pdf'
    hrefs = re.findall(
        r'href\s*=\s*["\']([^"\']+\.pdf[^"\']*)["\']',
        text,
        flags=re.I,
    )
    candidates = []
    for h in hrefs:
        full = urljoin(BNM_FEP_PAGE, h)
        low = full.lower()
        if "fep" in low or "foreign" in low or "exchange" in low or "policy" in low:
            candidates.append(full)
    if candidates:
        return candidates[0]
    if hrefs:
        return urljoin(BNM_FEP_PAGE, hrefs[0])
    return None


def download_pdf(url: str, dest: Path) -> bool:
    import requests

    print(f"Downloading: {url}")
    try:
        resp = requests.get(
            url,
            timeout=60,
            stream=True,
            headers={
                **_BNM_HEADERS,
                "Accept": "application/pdf,*/*;q=0.8",
                "Referer": BNM_FEP_PAGE,
            },
        )
        resp.raise_for_status()
        dest.write_bytes(resp.content)
        print(f"  Saved to: {dest} ({dest.stat().st_size:,} bytes)")
        return True
    except Exception as e:
        print(f"  Download failed: {e}")
        return False


def download_pdf_playwright(url: str, dest: Path) -> bool:
    """Use Chromium to fetch PDF (same-origin cookies / anti-bot)."""
    try:
        from playwright_helper import fetch_response_body
    except ImportError:
        print("  Playwright not installed.")
        return False
    print(f"Playwright download: {url}")
    try:
        data, ctype, _ = fetch_response_body(
            url,
            referer=BNM_FEP_PAGE,
        )
        if not data.startswith(b"%PDF"):
            print(f"  Not a PDF (content-type={ctype!r}, magic={data[:8]!r})")
            return False
        dest.write_bytes(data)
        print(f"  Saved to: {dest} ({dest.stat().st_size:,} bytes)")
        return True
    except Exception as e:
        print(f"  Playwright download failed: {e}")
        return False


def download_pdf_via_policy_playwright(dest: Path) -> tuple[bool, str | None]:
    """Open policy HTML in browser, follow first PDF link."""
    try:
        from playwright_helper import fetch_pdf_via_policy_page
    except ImportError:
        return False, None
    try:
        data, pdf_url = fetch_pdf_via_policy_page(BNM_FEP_PAGE)
        if not data.startswith(b"%PDF"):
            return False, None
        dest.write_bytes(data)
        print(f"  Playwright policy-page PDF saved ({len(data):,} bytes)")
        return True, pdf_url
    except Exception as e:
        print(f"  Playwright policy navigation failed: {e}")
        return False, None


def extract_text(pdf_path: Path) -> str:
    try:
        import pdfplumber
        pages_text = []
        with pdfplumber.open(pdf_path) as pdf:
            for i, page in enumerate(pdf.pages):
                t = page.extract_text()
                if t:
                    pages_text.append(f"[PAGE {i+1}]\n{t}")
        return "\n\n".join(pages_text)
    except ImportError:
        print("  pdfplumber not installed. Run: pip install pdfplumber")
        return ""
    except Exception as e:
        print(f"  Text extraction failed: {e}")
        return ""


def run(local_pdf: str | None = None) -> None:
    section("M5 BNM Policy — collect.py")

    source_url_used = BNM_FEP_PDF_DIRECT

    if local_pdf:
        src = Path(local_pdf)
        if not src.exists():
            print(f"Local PDF not found: {src}")
            sys.exit(1)
        import shutil
        shutil.copy(src, PDF_PATH)
        print(f"Using local PDF: {src}")
        source_url_used = f"file:{src}"
    else:
        discovered = discover_pdf_url_from_policy_page()
        ok = False
        if discovered:
            print(f"Discovered PDF URL from policy page: {discovered}")
            ok = download_pdf(discovered, PDF_PATH)
            if ok:
                source_url_used = discovered
        if not ok and discovered:
            print("  Retrying discovered URL with Playwright...")
            ok = download_pdf_playwright(discovered, PDF_PATH)
            if ok:
                source_url_used = discovered
        if not ok:
            print("  Trying direct PDF URL (requests)...")
            ok = download_pdf(BNM_FEP_PDF_DIRECT, PDF_PATH)
            if ok:
                source_url_used = BNM_FEP_PDF_DIRECT
        if not ok:
            print("  Trying direct PDF URL (Playwright)...")
            ok = download_pdf_playwright(BNM_FEP_PDF_DIRECT, PDF_PATH)
            if ok:
                source_url_used = BNM_FEP_PDF_DIRECT
        if not ok:
            print("  Trying policy page navigation (Playwright)...")
            ok_pw, pw_url = download_pdf_via_policy_playwright(PDF_PATH)
            if ok_pw and pw_url:
                source_url_used = pw_url
                ok = True
        if not ok:
            print(f"\nAuto-download failed. Please manually download from:")
            print(f"  {BNM_FEP_PAGE}")
            print(f"  and save to: {PDF_PATH}")
            print(f"  Then run: python collect.py --local {PDF_PATH}")
            sys.exit(1)

    print("\nExtracting text...")
    text = extract_text(PDF_PATH)
    if text:
        TEXT_PATH.write_text(text, encoding="utf-8")
        print(f"Text saved: {TEXT_PATH} ({len(text):,} chars)")
    else:
        print("  No text extracted.")

    meta = {
        "collected_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source_url": source_url_used,
        "pdf_path": str(PDF_PATH),
        "text_path": str(TEXT_PATH),
        "pages": len(text.split("[PAGE")) - 1 if text else 0,
    }
    META_PATH.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    print(f"Metadata: {META_PATH}")


def main():
    parser = argparse.ArgumentParser(description="Collect BNM FEP policy document.")
    parser.add_argument("--local", type=str, default=None,
                        help="Path to a locally downloaded PDF file.")
    args = parser.parse_args()
    run(local_pdf=args.local)


if __name__ == "__main__":
    main()
