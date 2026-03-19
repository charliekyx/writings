"""
analyzer.py - 文章数据分析模块
对抓取到的文章进行统计分析，提取共性与差异
无 NLTK/textstat 依赖，兼容 macOS Python SSL 环境
"""

import re
import math
import pandas as pd
import numpy as np
from collections import Counter
from scraper import Article


# ── 纯 Python 可读性实现（不依赖 NLTK/textstat）─────────────────────────────

def _count_syllables(word: str) -> int:
    """用正则规则估算英文单词音节数"""
    word = word.lower().strip(".,!?;:'\"")
    if not word:
        return 1
    word = re.sub(r"e$", "", word)
    vowels = re.findall(r"[aeiouy]+", word)
    count = len(vowels)
    return max(1, count)


def _readability_stats(text: str):
    """返回 (flesch, gunning_fog, avg_syllables_per_word) 或 None"""
    if not text or len(text) < 200:
        return None
    sentences = [s.strip() for s in re.split(r"[.!?]+", text) if len(s.strip()) > 5]
    words = re.findall(r"[a-zA-Z']+", text)
    if len(sentences) < 3 or len(words) < 50:
        return None
    n_sent = len(sentences)
    n_word = len(words)
    syllables = [_count_syllables(w) for w in words]
    n_syllable = sum(syllables)
    n_complex = sum(1 for s in syllables if s >= 3)
    avg_sent_len = n_word / n_sent
    avg_syl_per_word = n_syllable / n_word
    flesch = 206.835 - 1.015 * avg_sent_len - 84.6 * avg_syl_per_word
    gunning_fog = 0.4 * (avg_sent_len + 100 * n_complex / n_word)
    return round(flesch, 2), round(gunning_fog, 2)


def compute_readability(df: pd.DataFrame) -> pd.DataFrame:
    """计算可读性指标：Flesch Reading Ease、Gunning Fog Index"""
    df = df.copy()
    flesch_vals, fog_vals = [], []
    for text in df["text"]:
        result = _readability_stats(text)
        if result:
            flesch_vals.append(result[0])
            fog_vals.append(result[1])
        else:
            flesch_vals.append(np.nan)
            fog_vals.append(np.nan)
    df["flesch_reading_ease"] = flesch_vals
    df["gunning_fog"] = fog_vals
    return df

# 内置英文停用词（避免 NLTK SSL 问题）
STOP_WORDS = {
    "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "by", "from", "is", "are", "was", "were", "be", "been",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "shall", "can", "this", "that", "these",
    "those", "it", "its", "i", "you", "he", "she", "we", "they", "me",
    "him", "her", "us", "them", "my", "your", "his", "our", "their",
    "what", "which", "who", "when", "where", "why", "how", "if", "not",
    "so", "as", "up", "out", "about", "into", "than", "then", "just",
    "more", "also", "all", "some", "any", "one", "two", "first", "new",
    "get", "use", "can", "see", "know", "make", "take", "time", "year",
    "even", "well", "back", "only", "over", "after", "before", "because",
    "while", "through", "between", "each", "most", "other", "same",
    "much", "many", "such", "very", "here", "there", "both", "few",
    "now", "way", "still", "called", "going", "using", "want", "look",
    "need", "think", "since", "like", "being", "however", "though",
}


def _tokenize(text: str) -> list[str]:
    """简单正则分词，无需 NLTK"""
    return re.findall(r"[a-z]{3,}", text.lower())

FINANCIAL_KEYWORDS = [
    "investment", "portfolio", "return", "risk", "market", "stock",
    "bond", "equity", "dividend", "yield", "inflation", "recession",
    "bull", "bear", "hedge", "fund", "etf", "index", "alpha", "beta",
    "volatility", "diversification", "asset", "wealth", "income",
    "data", "backtesting", "strategy", "python", "code", "api",
    "backtest", "quant", "quantitative", "model", "signal",
    "singapore", "malaysia", "cpf", "sgd", "ibkr", "wise",
    "affiliate", "broker", "platform", "fee", "cost",
]

TONE_WORDS = {
    "calm_educational": [
        "understand", "learn", "simple", "easy", "beginner",
        "explain", "guide", "introduction", "basic", "principle",
        "patient", "long-term", "history", "evidence", "research",
    ],
    "quant_technical": [
        "algorithm", "backtest", "signal", "model", "code",
        "python", "api", "data", "statistical", "correlation",
        "regression", "neural", "machine learning", "optimization",
    ],
    "hedge_fund_elite": [
        "alpha", "thesis", "macro", "positioning", "flow",
        "regime", "catalyst", "conviction", "asymmetric",
        "risk/reward", "edge", "institutional", "smart money",
    ],
    "affiliate_practical": [
        "best", "recommend", "use", "try", "sign up", "click",
        "bonus", "referral", "promo", "deal", "save", "free",
        "comparison", "review", "vs", "versus",
    ],
}


def articles_to_df(articles: list[Article]) -> pd.DataFrame:
    """将 Article 列表转为 DataFrame"""
    rows = []
    for a in articles:
        rows.append({
            "blogger": a.blogger,
            "title": a.title,
            "url": a.url,
            "published": a.published,
            "word_count": a.word_count,
            "paragraph_count": a.paragraph_count,
            "heading_count": a.heading_count,
            "avg_sentence_length": a.avg_sentence_length,
            "has_code": a.has_code,
            "code_block_count": a.code_block_count,
            "has_table": a.has_table,
            "table_count": a.table_count,
            "has_chart": a.has_chart,
            "image_count": a.image_count,
            "link_count": a.link_count,
            "affiliate_link_count": a.affiliate_link_count,
            "text": a.text,
        })
    df = pd.DataFrame(rows)
    return df




def compute_tone_scores(df: pd.DataFrame) -> pd.DataFrame:
    """计算各文章四种 tone 关键词命中率"""
    df = df.copy()
    for tone, keywords in TONE_WORDS.items():
        def score_tone(text, kws=keywords):
            if not text:
                return 0.0
            text_lower = text.lower()
            hits = sum(1 for kw in kws if kw in text_lower)
            return round(hits / len(kws), 4)
        df[f"tone_{tone}"] = df["text"].apply(score_tone)
    return df


def compute_financial_keyword_density(df: pd.DataFrame) -> pd.DataFrame:
    """计算金融关键词密度"""
    df = df.copy()

    def density(text):
        if not text or len(text) < 50:
            return 0.0
        tokens = _tokenize(text)
        total = len(tokens)
        hits = sum(1 for t in tokens if t in FINANCIAL_KEYWORDS)
        return round(hits / total * 100, 4) if total > 0 else 0.0

    df["finance_keyword_density"] = df["text"].apply(density)
    return df


def get_top_keywords(texts: list[str], n: int = 30) -> list[tuple]:
    """提取一组文章的高频词（去停用词）"""
    all_tokens = []
    for text in texts:
        if not text:
            continue
        tokens = [
            t for t in _tokenize(text)
            if t not in STOP_WORDS
        ]
        all_tokens.extend(tokens)
    return Counter(all_tokens).most_common(n)


def compute_structure_score(df: pd.DataFrame) -> pd.DataFrame:
    """综合结构化程度评分（headings + tables + code per 1000 words）"""
    df = df.copy()
    wc = df["word_count"].replace(0, 1)
    df["structure_score"] = (
        df["heading_count"] * 2
        + df["table_count"] * 3
        + df["code_block_count"] * 2
        + df["image_count"] * 1
    ) / (wc / 1000)
    return df


def summarize_by_blogger(df: pd.DataFrame) -> pd.DataFrame:
    """按博主生成汇总统计"""
    numeric_cols = [
        "word_count", "paragraph_count", "heading_count",
        "avg_sentence_length", "code_block_count", "table_count",
        "image_count", "link_count", "affiliate_link_count",
        "flesch_reading_ease", "gunning_fog",
        "finance_keyword_density", "structure_score",
        "tone_calm_educational", "tone_quant_technical",
        "tone_hedge_fund_elite", "tone_affiliate_practical",
    ]
    existing = [c for c in numeric_cols if c in df.columns]
    summary = df.groupby("blogger")[existing].mean().round(3)

    # 布尔特征转比率
    for col in ["has_code", "has_table", "has_chart"]:
        if col in df.columns:
            summary[f"{col}_rate"] = df.groupby("blogger")[col].mean().round(3)

    summary["article_count"] = df.groupby("blogger").size()
    return summary


def run_analysis(articles: list[Article]) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """完整分析流程，返回 (article_df, summary_df, keywords_dict)"""
    print("\n[分析] 转换为 DataFrame...")
    df = articles_to_df(articles)
    df = df[df["word_count"] > 200].reset_index(drop=True)

    print("[分析] 计算可读性指标...")
    df = compute_readability(df)

    print("[分析] 计算 Tone 关键词评分...")
    df = compute_tone_scores(df)

    print("[分析] 计算金融关键词密度...")
    df = compute_financial_keyword_density(df)

    print("[分析] 计算结构化评分...")
    df = compute_structure_score(df)

    print("[分析] 提取各博主高频词...")
    keywords = {}
    for blogger in df["blogger"].unique():
        texts = df[df["blogger"] == blogger]["text"].tolist()
        keywords[blogger] = get_top_keywords(texts, n=30)

    print("[分析] 生成汇总统计...")
    summary = summarize_by_blogger(df)

    return df, summary, keywords
