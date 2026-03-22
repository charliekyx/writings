"""
从 CIMB SG / HSBC SG 官网页面解析 SG Hop Leg2 费用，并结合 Frankfurter 中间价折算 SGD。

Leg1（MY→SG 同集团）：
  CIMB：解析 my-to-sg 页面「Zero Fees」类表述 → 0 MYR
  HSBC：解析 GlobalView 相关页（若可得）或仅记来源 URL

Leg2 FX spread：银行费用页通常不提供相对 mid 的 spread 百分比 → 记 0，
  在 leg1_rate_note 中说明「需另通道抓取牌价再建模」。
"""

from __future__ import annotations

import re

import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-SG,en;q=0.9",
}

CIMB_MY_TO_SG_URL = (
    "https://www.cimb.com.my/en/personal/day-to-day-banking/remittance/my-to-sg.html"
)
CIMB_SG_REMITTANCE_URL = (
    "https://www.cimb.com.sg/en/personal/help-support/rates-charges/"
    "fees-charges/remittance.html"
)
HSBC_GM_URL = (
    "https://www.hsbc.com.sg/accounts/products/global-money-transfers/"
)
HSBC_GLOBALVIEW_MY = "https://www.hsbc.com.my/help/transfer/global-view/"


def _get(url: str, timeout: int = 30) -> str:
    r = requests.get(url, headers=HEADERS, timeout=timeout)
    r.raise_for_status()
    return r.text


def parse_cimb_sg_usd_tt_usd_fee(html: str) -> float:
    """Outward TT 列表中「USD - 27」形式。"""
    m = re.search(
        r"USD\s*[-–]\s*(\d+)",
        html,
        re.I,
    )
    if not m:
        raise ValueError("CIMB SG: USD TT fee bullet not found")
    v = float(m.group(1))
    if v <= 0:
        raise ValueError(f"CIMB SG: invalid USD TT fee {v}")
    return v


def parse_cimb_sg_cable_sgd(html: str) -> float:
    m = re.search(
        r"cable\s+charges?\s*\([^)]*flat\s+rate\s+of\s+S\$\s*(\d+)",
        html,
        re.I | re.DOTALL,
    )
    if m:
        return float(m.group(1))
    m2 = re.search(r"flat\s+rate\s+of\s+S\$\s*(\d+)", html, re.I)
    if m2:
        return float(m2.group(1))
    raise ValueError("CIMB SG: cable S$ amount not found")


def parse_cimb_sg_commission_pct_bounds(html: str) -> tuple[float, float, float]:
    """
    返回 (pct_as_fraction, min_sgd, max_sgd)，如 0.125% → 0.00125, 10, 100
    """
    m = re.search(
        r"([\d.]+)\s*%\s*commission\s*\(\s*min\s+S\$\s*(\d+)\s*,\s*max\s+S\$\s*(\d+)\s*\)",
        html,
        re.I | re.DOTALL,
    )
    if not m:
        raise ValueError("CIMB SG: commission % min max not found")
    pct = float(m.group(1)) / 100.0
    lo = float(m.group(2))
    hi = float(m.group(3))
    return pct, lo, hi


def cimb_leg2_wire_fee_sgd(
    source_amount_myr: float,
    mid_myr_sgd: float,
    mid_usd_sgd: float,
    html: str,
) -> tuple[float, str]:
    """
    Leg2 银行侧费用折算为单一 SGD 数（建模用）：
    USD TT 标价(USD) * (1 USD = mid_usd_sgd SGD) + cable SGD + commission(按转出额 SGD 计).
    """
    usd_tt = parse_cimb_sg_usd_tt_usd_fee(html)
    cable = parse_cimb_sg_cable_sgd(html)
    pct, cmin, cmax = parse_cimb_sg_commission_pct_bounds(html)
    amount_sgd = source_amount_myr * mid_myr_sgd
    comm = max(cmin, min(cmax, amount_sgd * pct))
    usd_part_sgd = usd_tt * mid_usd_sgd
    total = cable + comm + usd_part_sgd
    note = (
        f"CIMB SG remittance page: USD TT USD{usd_tt:.0f} + cable S${cable:.0f} + "
        f"commission {pct*100:.3f}% (min S${cmin:.0f} max S${cmax:.0f}) on ~S${amount_sgd:.2f}; "
        f"USD block converted at Frankfurter 1 USD={mid_usd_sgd:.4f} SGD."
    )
    return round(total, 2), note


def scrape_cimb_leg1_fee_myr() -> tuple[float, str, str]:
    html = _get(CIMB_MY_TO_SG_URL)
    text = BeautifulSoup(html, "html.parser").get_text(" ", strip=True).lower()
    if "zero fee" in text or "no fees" in text or "no fee" in text:
        return (
            0.0,
            CIMB_MY_TO_SG_URL,
            "Parsed: Malaysia-to-Singapore Cross Border (CIMB) marketing copy indicates zero fees for linked transfer; confirm T&C.",
        )
    raise ValueError("CIMB MY→SG: could not confirm zero-fee wording on page")


def hsbc_leg2_from_global_money_page(
    html: str, *, strict_validate: bool = False
) -> tuple[float, float, str]:
    """
    HSBC Global Money：HSBC 侧费用常豁免；中间行无固定数字 → intermediary 记 0，
    在 note 中引用脚注「intermediary may apply」。
    strict_validate=True 时：若页面中找不到任何「豁免/零费」表述，则拒绝静默返回 0。
    """
    low = html.lower()
    if len(html.strip()) < 500:
        raise ValueError(
            "HSBC Global Money: HTML too short — page blocked or wrong URL."
        )
    wire_sgd = 0.0
    inter_usd = 0.0
    note = (
        "HSBC SG Global Money page: HSBC-side fees described as waived for eligible transfers; "
        "intermediary/correspondent charges not quantified on page — modeled as 0 USD here; "
        "check app estimate before transfer."
    )
    if strict_validate:
        waiver_signals = (
            "waived",
            "complimentary",
            "no fee",
            "no charge",
            "s$0",
            "s$ 0",
            "sgd 0",
            "zero fee",
            "fee free",
            "free transfer",
        )
        if not any(s in low for s in waiver_signals):
            raise ValueError(
                "HSBC Global Money (strict): no fee-waiver wording found; "
                "refusing silent leg2_wire_sgd=0 — verify page or parser."
            )
    return wire_sgd, inter_usd, note


def scrape_hsbc_leg1_note() -> tuple[float, str, str]:
    """尝试拉 GlobalView MY 页；失败则 leg1=0 并写明未抓取。"""
    try:
        html = _get(HSBC_GLOBALVIEW_MY, timeout=20)
        return (
            0.0,
            HSBC_GLOBALVIEW_MY,
            "HSBC MY Global View page fetched; leg1 fee assumed 0 pending structured fee table parse — verify in app.",
        )
    except Exception as e:
        return (
            0.0,
            HSBC_GLOBALVIEW_MY,
            f"HSBC MY GlobalView fetch failed ({e}); leg1_fee_myr=0 placeholder.",
        )
