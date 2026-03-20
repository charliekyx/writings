"""
Heuristic style metrics for English prose (authority, trust, hooks).
No NLTK; safe to run in minimal venvs.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Any

# ── Readability (same spirit as blogger_analysis/analyzer.py) ───────────────

def _count_syllables(word: str) -> int:
    word = word.lower().strip(".,!?;:'\"")
    if not word:
        return 1
    word = re.sub(r"e$", "", word)
    vowels = re.findall(r"[aeiouy]+", word)
    return max(1, len(vowels))


def readability_stats(text: str) -> dict[str, float | None]:
    """Flesch Reading Ease and Gunning Fog when enough text; else nulls."""
    out: dict[str, float | None] = {"flesch_reading_ease": None, "gunning_fog": None}
    if not text or len(text) < 200:
        return out
    sentences = [s.strip() for s in re.split(r"[.!?]+", text) if len(s.strip()) > 5]
    words = re.findall(r"[a-zA-Z']+", text)
    if len(sentences) < 3 or len(words) < 50:
        return out
    n_sent = len(sentences)
    n_word = len(words)
    syllables = [_count_syllables(w) for w in words]
    n_syllable = sum(syllables)
    n_complex = sum(1 for s in syllables if s >= 3)
    avg_sent_len = n_word / n_sent
    avg_syl_per_word = n_syllable / n_word
    flesch = 206.835 - 1.015 * avg_sent_len - 84.6 * avg_syl_per_word
    gunning_fog = 0.4 * (avg_sent_len + 100 * n_complex / n_word)
    out["flesch_reading_ease"] = round(flesch, 2)
    out["gunning_fog"] = round(gunning_fog, 2)
    return out


def split_sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    return [p.strip() for p in parts if len(p.strip()) > 3]


def split_paragraphs(text: str) -> list[str]:
    return [p.strip() for p in re.split(r"\n\s*\n", text.strip()) if p.strip()]


DISCLAIMER_PATTERNS = re.compile(
    r"\b(disclaimer|full disclosure|disclose|conflict of interest|i work at|"
    r"my employer|affiliate|affiliated|i earn|referral link|sponsored)\b",
    re.I,
)

IMPERATIVE_START = re.compile(
    r"^(do|don'?t|try|note|remember|assume|read|see|use|avoid|consider)\b",
    re.I | re.M,
)


def _word_tokens(text: str) -> list[str]:
    return re.findall(r"[a-zA-Z']+", text.lower())


def analyze_text(text: str, source_label: str = "") -> dict[str, Any]:
    """Return a flat dict of metrics for one document body (no frontmatter)."""
    text = text.strip()
    words = _word_tokens(text)
    n_words = max(1, len(words))
    sentences = split_sentences(text)
    paragraphs = split_paragraphs(text)
    sent_word_counts = [len(_word_tokens(s)) for s in sentences] if sentences else [0]

    first_3 = sentences[:3]
    opening_question = sum(1 for s in first_3 if "?" in s)
    opening_has_digit = any(re.search(r"\d", s) for s in first_3)
    opening_has_currency = any(re.search(r"[\$€£¥]|USD|EUR|GBP", s) for s in first_3)
    first_sentence_len = len(_word_tokens(first_3[0])) if first_3 else 0

    pron_i = sum(1 for w in words if w in ("i", "i'd", "i've", "i'm", "i'll"))
    pron_we = sum(1 for w in words if w in ("we", "we're", "we've", "we'd", "we'll"))
    pron_you = sum(1 for w in words if w in ("you", "your", "you're", "you've"))

    paren_count = text.count("(")
    md_heading_lines = len(re.findall(r"(?m)^#{1,6}\s+\S", text))
    md_bullet_lines = len(re.findall(r"(?m)^\s*[-*]\s+\S", text))
    numbered_lines = len(re.findall(r"(?m)^\s*\d+[.)]\s+\S", text))

    digits = len(re.findall(r"\d+", text))
    urls = len(re.findall(r"https?://[^\s)>\]]+", text))

    head = text[:2500]
    disclaimer_hits_early = len(DISCLAIMER_PATTERNS.findall(head))
    disclaimer_hits_total = len(DISCLAIMER_PATTERNS.findall(text))

    imperative_lines = len(IMPERATIVE_START.findall(text))

    read = readability_stats(text)

    return {
        "source_label": source_label,
        "char_count": len(text),
        "word_count": len(words),
        "sentence_count": len(sentences),
        "paragraph_count": len(paragraphs),
        "avg_words_per_sentence": round(sum(sent_word_counts) / max(1, len(sentences)), 2),
        "median_words_per_sentence": float(sorted(sent_word_counts)[len(sent_word_counts) // 2])
        if sent_word_counts
        else 0.0,
        "avg_words_per_paragraph": round(sum(len(_word_tokens(p)) for p in paragraphs) / max(1, len(paragraphs)), 2)
        if paragraphs
        else 0.0,
        "opening_first3_question_count": opening_question,
        "opening_first3_has_digit": opening_has_digit,
        "opening_first3_has_currency": opening_has_currency,
        "opening_first_sentence_word_count": first_sentence_len,
        "pronoun_i_per_1k_words": round(1000 * pron_i / n_words, 2),
        "pronoun_we_per_1k_words": round(1000 * pron_we / n_words, 2),
        "pronoun_you_per_1k_words": round(1000 * pron_you / n_words, 2),
        "parens_per_1k_words": round(1000 * paren_count / n_words, 2),
        "md_headings_count": md_heading_lines,
        "md_bullet_lines_per_1k_words": round(1000 * md_bullet_lines / n_words, 2),
        "numbered_lines_per_1k_words": round(1000 * numbered_lines / n_words, 2),
        "digit_tokens_per_1k_words": round(1000 * digits / n_words, 2),
        "urls_per_1k_words": round(1000 * urls / n_words, 2),
        "disclaimer_hits_first_2500_chars": disclaimer_hits_early,
        "disclaimer_hits_total_per_1k_words": round(1000 * disclaimer_hits_total / n_words, 2),
        "imperative_line_count": imperative_lines,
        **{f"readability_{k}": v for k, v in read.items()},
    }


def _mean(nums: list[float]) -> float:
    return round(sum(nums) / len(nums), 3) if nums else 0.0


def aggregate_docs(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate numeric fields across documents."""
    if not rows:
        return {}
    def _is_numeric(v: Any) -> bool:
        return isinstance(v, (int, float)) and not isinstance(v, bool)

    keys = [k for k in rows[0] if _is_numeric(rows[0][k]) and k != "source_label"]
    agg: dict[str, Any] = {"doc_count": len(rows)}
    for k in keys:
        vals = [float(r[k]) for r in rows if k in r and r[k] is not None]
        if not vals:
            continue
        agg[f"{k}_mean"] = _mean(vals)
        sorted_vals = sorted(vals)
        agg[f"{k}_p50"] = sorted_vals[len(sorted_vals) // 2]

    bool_keys = [
        "opening_first3_has_digit",
        "opening_first3_has_currency",
    ]
    for bk in bool_keys:
        if bk in rows[0]:
            frac = sum(1 for r in rows if r.get(bk)) / len(rows)
            agg[f"{bk}_fraction"] = round(frac, 3)

    return agg


def opening_pattern_tags(row: dict[str, Any]) -> list[str]:
    """Turn metrics into coarse tags for the brief."""
    tags: list[str] = []
    if row.get("opening_first3_question_count", 0) >= 1:
        tags.append("opens_with_question")
    if row.get("opening_first3_has_digit"):
        tags.append("early_numbers")
    if row.get("opening_first3_has_currency"):
        tags.append("early_money_units")
    if row.get("opening_first_sentence_word_count", 0) >= 25:
        tags.append("long_opening_sentence")
    if row.get("opening_first_sentence_word_count", 0) > 0 and row.get("opening_first_sentence_word_count", 0) <= 12:
        tags.append("short_punchy_opening")
    if row.get("disclaimer_hits_first_2500_chars", 0) >= 1:
        tags.append("disclosure_near_top")
    if row.get("pronoun_i_per_1k_words", 0) >= 8:
        tags.append("strong_first_person")
    if row.get("pronoun_you_per_1k_words", 0) >= 12:
        tags.append("direct_reader_address")
    if row.get("parens_per_1k_words", 0) >= 8:
        tags.append("heavy_parenthetical_asides")
    if row.get("md_headings_count", 0) >= 5 or row.get("avg_words_per_paragraph", 0) < 90:
        tags.append("scannable_structure")
    return tags
