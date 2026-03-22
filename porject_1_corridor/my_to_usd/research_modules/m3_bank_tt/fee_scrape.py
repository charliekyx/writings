"""
从银行官网 HTML 解析 Foreign TT / Remittance 手续费（MYR），无环境变量硬编码。

数据源 URL 为代码内常量（仅页面地址，非费率数值）。
"""

from __future__ import annotations

import io
import re
from pathlib import Path

import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-MY,en;q=0.9",
}

CIMB_MY_REMITTANCE_URL = (
    "https://www.cimb.com.my/en/personal/help-support/rates-charges/"
    "profit-rates-charges/fees-and-charges/remittance.html"
)

MAYBANK_FTT_URLS = (
    "https://www.maybank2u.com.my/maybank2u/malaysia/en/personal/banking_fees/cost_of_wire.page",
    "https://www.maybank2u.com.my/maybank2u/malaysia/en/personal/banking_fees/transfer_funds.page",
    "https://www.maybank2u.com.my/maybank2u/malaysia/en/personal/banking_fees/transfer.page",
)

MAYBANK_FTT_PDF = (
    "https://www.maybank2u.com.my/iwov-resources/pdf/personal/services/"
    "funds_transfer/ftt-m2u-m2ubiz-faq.pdf"
)


def _get(url: str, timeout: int = 30) -> str:
    r = requests.get(url, headers=HEADERS, timeout=timeout)
    r.raise_for_status()
    return r.text


def parse_cimb_my_ftt_fee_clicks_myr(html: str) -> float:
    """
    解析「Foreign Telegraphic Transfer」首行 Charges 列中 Clicks 对应 RM 金额。
    官网表格：Branch 三档后接 Clicks 一行，Charges 列末段为 RM10.00（Clicks）。
    """
    soup = BeautifulSoup(html, "html.parser")
    h3 = None
    for tag in soup.find_all("h3"):
        if tag.get_text(strip=True) == "Foreign Telegraphic Transfer":
            h3 = tag
            break
    if not h3:
        raise ValueError("CIMB: Foreign Telegraphic Transfer heading not found")

    table = h3.find_next("table")
    if not table:
        raise ValueError("CIMB: fee table not found after FTT heading")

    rows = table.find_all("tr")
    if len(rows) < 2:
        raise ValueError("CIMB: unexpected FTT table shape")

    first_data = rows[1]
    tds = first_data.find_all("td")
    if len(tds) < 2:
        raise ValueError("CIMB: FTT row missing Charges column")

    charges_cell = tds[1]
    amounts: list[float] = []
    for p in charges_cell.find_all("p"):
        for m in re.finditer(r"RM\s*(\d+\.?\d*)", p.get_text(), re.I):
            amounts.append(float(m.group(1)))
    if not amounts:
        raise ValueError("CIMB: no RM amounts in FTT Charges cell")

    # 与官网结构一致：SGD, IDR, All other (branch), 空行, Clicks → 取最后一档为 Clicks
    fee = amounts[-1]
    if fee <= 0 or fee > 500:
        raise ValueError(f"CIMB: parsed fee out of range: {fee}")
    return fee


def scrape_cimb_tt_fee_myr() -> tuple[float, str]:
    html = _get(CIMB_MY_REMITTANCE_URL)
    fee = parse_cimb_my_ftt_fee_clicks_myr(html)
    return fee, CIMB_MY_REMITTANCE_URL


def _parse_maybank_fee_from_html(html: str) -> float | None:
    """
    在 Maybank 费用页中查找与 FTT / wire / telegraphic 相关的 RM 手续费。
    优先匹配「online / MAE / Maybank2u」附近的 RM 金额。
    """
    lower = html.lower()
    # 常见：网上 FTT RM10、柜台 RM30
    candidates: list[tuple[int, float]] = []
    for m in re.finditer(r"RM\s*(\d+\.?\d*)", html, re.I):
        val = float(m.group(1))
        if not (5 <= val <= 200):
            continue
        pos = m.start()
        window = lower[max(0, pos - 200) : pos + 80]
        if any(
            k in window
            for k in (
                "telegraphic",
                "ftt",
                "foreign transfer",
                "wire",
                "international",
                "overseas",
            )
        ):
            candidates.append((pos, val))
    if not candidates:
        return None
    # 若有小金额（网上通道）优先取 ≤20 的较小值
    small = [v for _, v in candidates if v <= 25]
    if small:
        return min(small)
    return min(v for _, v in candidates)


def _parse_maybank_fee_from_pdf(data: bytes) -> float | None:
    try:
        import pdfplumber
    except ImportError:
        return None
    text = ""
    with pdfplumber.open(io.BytesIO(data)) as pdf:
        for page in pdf.pages:
            t = page.extract_text()
            if t:
                text += t + "\n"
    if not text.strip():
        return None
    return _parse_maybank_fee_from_html(text)


def scrape_maybank_tt_fee_myr() -> tuple[float, str]:
    last_err: str | None = None
    for url in MAYBANK_FTT_URLS:
        try:
            html = _get(url)
            fee = _parse_maybank_fee_from_html(html)
            if fee is not None:
                return fee, url
        except Exception as e:
            last_err = str(e)
            continue

    try:
        r = requests.get(MAYBANK_FTT_PDF, headers=HEADERS, timeout=35)
        r.raise_for_status()
        fee = _parse_maybank_fee_from_pdf(r.content)
        if fee is not None:
            return fee, MAYBANK_FTT_PDF
    except Exception as e:
        last_err = str(e)

    raise RuntimeError(
        "Maybank: could not parse TT fee from official HTML/PDF. "
        f"Tried {MAYBANK_FTT_URLS} and PDF. Last error: {last_err}"
    )


def _maybank_fee_playwright() -> tuple[float, str]:
    from playwright_helper import fetch_page_html, fetch_response_body

    last_err: str | None = None
    for url in MAYBANK_FTT_URLS:
        try:
            html = fetch_page_html(url)
            fee = _parse_maybank_fee_from_html(html)
            if fee is not None:
                return fee, url
        except Exception as e:
            last_err = str(e)
            continue
    try:
        body, _, _ = fetch_response_body(MAYBANK_FTT_PDF)
        fee = _parse_maybank_fee_from_pdf(body)
        if fee is not None:
            return fee, MAYBANK_FTT_PDF
    except Exception as e:
        last_err = str(e)
    raise RuntimeError(
        "Maybank Playwright: could not parse TT fee from HTML/PDF. "
        f"Last error: {last_err}"
    )


def _cimb_fee_playwright() -> tuple[float, str]:
    from playwright_helper import fetch_page_html

    html = fetch_page_html(CIMB_MY_REMITTANCE_URL)
    fee = parse_cimb_my_ftt_fee_clicks_myr(html)
    return fee, CIMB_MY_REMITTANCE_URL


def scrape_wire_fee_myr(bank: str) -> tuple[float, str]:
    """
    Prefer requests; on failure retry with Playwright (same official URLs).
    """
    from playwright_helper import playwright_available

    bank = bank.lower()

    def _chain(req_fn, pw_fn, label: str) -> tuple[float, str]:
        try:
            return req_fn()
        except Exception as e1:
            if not playwright_available():
                raise
            try:
                return pw_fn()
            except Exception as e2:
                raise RuntimeError(
                    f"{label}: requests failed ({e1}); playwright failed ({e2})"
                ) from e2

    if bank == "cimb":
        return _chain(scrape_cimb_tt_fee_myr, _cimb_fee_playwright, "CIMB")
    if bank == "maybank":
        return _chain(scrape_maybank_tt_fee_myr, _maybank_fee_playwright, "Maybank")
    raise ValueError(f"Unsupported bank for fee scrape: {bank}")
