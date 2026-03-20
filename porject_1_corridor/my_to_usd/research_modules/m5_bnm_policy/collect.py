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
import sys
from datetime import datetime, timezone
from pathlib import Path

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


def download_pdf(url: str, dest: Path) -> bool:
    import requests
    print(f"Downloading: {url}")
    try:
        resp = requests.get(url, timeout=30, stream=True)
        resp.raise_for_status()
        dest.write_bytes(resp.content)
        print(f"  Saved to: {dest} ({dest.stat().st_size:,} bytes)")
        return True
    except Exception as e:
        print(f"  Download failed: {e}")
        return False


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

    if local_pdf:
        src = Path(local_pdf)
        if not src.exists():
            print(f"Local PDF not found: {src}")
            sys.exit(1)
        import shutil
        shutil.copy(src, PDF_PATH)
        print(f"Using local PDF: {src}")
    else:
        ok = download_pdf(BNM_FEP_PDF_DIRECT, PDF_PATH)
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
        "source_url": BNM_FEP_PDF_DIRECT,
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
