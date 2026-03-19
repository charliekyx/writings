"""
scraper.py - 博主文章抓取模块
支持从 RSS feed 或直接网页抓取文章内容
"""

import time
import requests
import feedparser
from bs4 import BeautifulSoup
from dataclasses import dataclass, field
from typing import Optional
from tqdm import tqdm
import re

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

# 博主配置：名称、RSS feed URL、主站 URL、特殊解析规则
BLOGGERS = {
    "Of Dollars and Data": {
        "rss": "https://ofdollarsanddata.com/feed/",
        "base_url": "https://ofdollarsanddata.com",
        "content_selector": "div.entry-content",
        "max_articles": 30,
    },
    "Quant Galore": {
        "rss": "https://quantgalore.substack.com/feed",
        "base_url": "https://quantgalore.substack.com",
        "content_selector": "div.body.markup",
        "max_articles": 30,
    },
    "Citrini Research": {
        "rss": "https://www.citriniresearch.com/feed",
        "base_url": "https://www.citriniresearch.com",
        "content_selector": "div.post-content",
        "max_articles": 30,
    },
    "Financial Horse": {
        "rss": "https://financialhorse.com/feed/",
        "base_url": "https://financialhorse.com",
        "content_selector": "div.entry-content",
        "max_articles": 30,
    },
}


@dataclass
class Article:
    blogger: str
    title: str
    url: str
    published: str
    raw_html: str = ""
    text: str = ""
    word_count: int = 0
    has_code: bool = False
    has_table: bool = False
    has_chart: bool = False
    image_count: int = 0
    link_count: int = 0
    affiliate_link_count: int = 0
    heading_count: int = 0
    code_block_count: int = 0
    table_count: int = 0
    paragraph_count: int = 0
    avg_sentence_length: float = 0.0
    tags: list = field(default_factory=list)


AFFILIATE_PATTERNS = [
    r"wise\.com/invite",
    r"refer\.wise",
    r"ibkr\.com/referral",
    r"go\.skimresources",
    r"shareasale\.com",
    r"awin1\.com",
    r"impact\.com",
    r"prf\.hn",
    r"moo\.com/share",
    r"amzn\.to",
    r"geni\.us",
    r"financialhorse\.com.*ref=",
    r"tiger.*referral",
    r"moomoo.*referral",
    r"\?ref=",
    r"&ref=",
    r"affiliate",
    r"referral",
]

CHART_KEYWORDS = [
    "chart", "graph", "plot", "figure", "visualization",
    "data viz", "scatter", "histogram", "bar chart", "line chart",
]

CHART_COLORS = [
    "#dce775", "#4fc3f7", "#ff8a65", "#ce93d8",
]


def fetch_rss(blogger_name: str, config: dict) -> list[Article]:
    """通过 RSS feed 获取文章列表
    先用 requests（内建 certifi）下载 XML，再交给 feedparser 解析文本，
    完全绕过 macOS Python urllib SSL 证书问题。
    """
    articles = []
    try:
        resp = requests.get(
            config["rss"],
            headers=HEADERS,
            timeout=15,
        )
        resp.raise_for_status()
        feed = feedparser.parse(resp.text)
        entries = feed.entries[: config["max_articles"]]
        print(f"  [RSS] {blogger_name}: 获取到 {len(entries)} 篇文章")
        for entry in entries:
            pub = entry.get("published", entry.get("updated", "unknown"))
            articles.append(
                Article(
                    blogger=blogger_name,
                    title=entry.get("title", ""),
                    url=entry.get("link", ""),
                    published=pub,
                )
            )
    except Exception as e:
        print(f"  [RSS ERROR] {blogger_name}: {e}")
    return articles


def parse_article_content(article: Article, config: dict) -> Article:
    """抓取文章正文 HTML 并解析各类特征"""
    try:
        resp = requests.get(article.url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "lxml")

        # 尝试主 selector，失败则用通用 fallback
        content = soup.select_one(config["content_selector"])
        if content is None:
            content = (
                soup.find("article")
                or soup.find("main")
                or soup.find("div", class_=re.compile(r"content|post|entry", re.I))
            )
        if content is None:
            return article

        article.raw_html = str(content)

        # --- 基础文本 ---
        text = content.get_text(separator=" ", strip=True)
        article.text = text

        sentences = re.split(r"[.!?]+", text)
        sentences = [s.strip() for s in sentences if len(s.strip()) > 10]
        words = text.split()
        article.word_count = len(words)
        article.avg_sentence_length = (
            len(words) / len(sentences) if sentences else 0
        )
        article.paragraph_count = len(content.find_all("p"))

        # --- 结构特征 ---
        headings = content.find_all(["h1", "h2", "h3", "h4"])
        article.heading_count = len(headings)

        code_blocks = content.find_all(["code", "pre"])
        article.code_block_count = len(code_blocks)
        article.has_code = len(code_blocks) > 0

        tables = content.find_all("table")
        article.table_count = len(tables)
        article.has_table = len(tables) > 0

        imgs = content.find_all("img")
        article.image_count = len(imgs)

        # --- 图表检测（通过 img alt/title 关键词 + canvas/svg）---
        chart_elements = content.find_all(["canvas", "svg"])
        chart_imgs = [
            img for img in imgs
            if any(
                kw in (img.get("alt", "") + img.get("title", "") + img.get("src", "")).lower()
                for kw in CHART_KEYWORDS
            )
        ]
        article.has_chart = len(chart_elements) > 0 or len(chart_imgs) > 0

        # --- 链接分析 ---
        links = content.find_all("a", href=True)
        article.link_count = len(links)
        aff_count = 0
        for link in links:
            href = link["href"]
            if any(re.search(pat, href, re.I) for pat in AFFILIATE_PATTERNS):
                aff_count += 1
        article.affiliate_link_count = aff_count

    except Exception as e:
        print(f"    [PARSE ERROR] {article.url}: {e}")

    return article


def scrape_all(delay: float = 1.5, max_articles: Optional[int] = None) -> list[Article]:
    """主入口：抓取所有博主所有文章"""
    all_articles = []

    for blogger_name, config in BLOGGERS.items():
        print(f"\n>> 正在处理: {blogger_name}")
        articles = fetch_rss(blogger_name, config)

        if max_articles:
            articles = articles[:max_articles]

        for art in tqdm(articles, desc=f"  解析 {blogger_name}"):
            parsed = parse_article_content(art, config)
            all_articles.append(parsed)
            time.sleep(delay)

    print(f"\n总计抓取: {len(all_articles)} 篇文章")
    return all_articles
