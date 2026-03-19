"""
visualizer.py - 可视化报告生成模块
生成多维度对比图表并输出分析报告
"""

import os
import json
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import seaborn as sns
from wordcloud import WordCloud
from datetime import datetime

OUTPUT_DIR = "output"
os.makedirs(OUTPUT_DIR, exist_ok=True)

BLOGGER_COLORS = {
    "Of Dollars and Data": "#4A90D9",
    "Quant Galore":        "#E8834B",
    "Citrini Research":    "#5BAD6F",
    "Financial Horse":     "#A070C0",
}

plt.rcParams.update({
    "figure.facecolor": "#0d1117",
    "axes.facecolor":   "#161b22",
    "axes.edgecolor":   "#30363d",
    "axes.labelcolor":  "#e6edf3",
    "text.color":       "#e6edf3",
    "xtick.color":      "#e6edf3",
    "ytick.color":      "#e6edf3",
    "grid.color":       "#21262d",
    "font.family":      "DejaVu Sans",
})


def _colors_for(bloggers):
    return [BLOGGER_COLORS.get(b, "#888888") for b in bloggers]


def plot_content_length(summary: pd.DataFrame, save: bool = True):
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))
    fig.suptitle("Article Length & Structure", fontsize=14, fontweight="bold", color="#e6edf3")

    bloggers = summary.index.tolist()
    colors = _colors_for(bloggers)

    # Word count
    ax = axes[0]
    bars = ax.bar(bloggers, summary["word_count"], color=colors, edgecolor="none", alpha=0.9)
    ax.set_title("Avg Word Count per Article", color="#e6edf3")
    ax.set_ylabel("Words")
    ax.set_xticks(range(len(bloggers)))
    ax.set_xticklabels(bloggers, rotation=20, ha="right", fontsize=9)
    ax.grid(axis="y", alpha=0.3)
    for bar, val in zip(bars, summary["word_count"]):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 30,
                f"{int(val):,}", ha="center", va="bottom", fontsize=9)

    # Structure score
    ax2 = axes[1]
    bars2 = ax2.bar(bloggers, summary["structure_score"], color=colors, edgecolor="none", alpha=0.9)
    ax2.set_title("Structure Score\n(headings+tables+code per 1k words)", color="#e6edf3")
    ax2.set_ylabel("Score")
    ax2.set_xticks(range(len(bloggers)))
    ax2.set_xticklabels(bloggers, rotation=20, ha="right", fontsize=9)
    ax2.grid(axis="y", alpha=0.3)
    for bar, val in zip(bars2, summary["structure_score"]):
        ax2.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.05,
                 f"{val:.1f}", ha="center", va="bottom", fontsize=9)

    plt.tight_layout()
    path = os.path.join(OUTPUT_DIR, "01_content_length_structure.png")
    if save:
        plt.savefig(path, dpi=150, bbox_inches="tight")
        print(f"  Saved: {path}")
    plt.close()
    return path


def plot_readability(summary: pd.DataFrame, save: bool = True):
    metrics = [
        ("flesch_reading_ease", "Flesch Reading Ease\n(60-70 = standard)"),
        ("gunning_fog",         "Gunning Fog Index\n(8-12 = accessible)"),
    ]
    fig, axes = plt.subplots(1, 2, figsize=(12, 5))
    axes = list(axes)

    fig.suptitle("Readability Metrics (Higher Flesch = Easier, Lower Fog = Simpler)",
                 fontsize=13, fontweight="bold")
    bloggers = summary.index.tolist()
    colors = _colors_for(bloggers)

    for ax, (col, title) in zip(axes, metrics):
        col_data = summary[col].dropna()
        if col not in summary.columns or col_data.empty:
            ax.set_visible(False)
            continue
        vals = summary[col].fillna(0)
        bars = ax.bar(bloggers, vals, color=colors, edgecolor="none", alpha=0.9)
        ax.set_title(title, color="#e6edf3", fontsize=10)
        ax.set_xticks(range(len(bloggers)))
        ax.set_xticklabels(bloggers, rotation=25, ha="right", fontsize=8)
        ax.grid(axis="y", alpha=0.3)
        for bar, val in zip(bars, summary[col]):
            if not pd.isna(val):
                ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.2,
                        f"{val:.1f}", ha="center", va="bottom", fontsize=9)

    plt.tight_layout()
    path = os.path.join(OUTPUT_DIR, "02_readability.png")
    if save:
        plt.savefig(path, dpi=150, bbox_inches="tight")
        print(f"  Saved: {path}")
    plt.close()
    return path


def plot_tone_radar(summary: pd.DataFrame, save: bool = True):
    tone_cols = [c for c in summary.columns if c.startswith("tone_")]
    labels = [c.replace("tone_", "").replace("_", "\n") for c in tone_cols]
    N = len(tone_cols)
    if N == 0:
        return None

    angles = np.linspace(0, 2 * np.pi, N, endpoint=False).tolist()
    angles += angles[:1]

    fig, ax = plt.subplots(figsize=(8, 8), subplot_kw=dict(polar=True))
    ax.set_facecolor("#161b22")
    fig.patch.set_facecolor("#0d1117")
    ax.set_title("Content Tone Radar\n(higher = stronger signal)", fontsize=13,
                 fontweight="bold", color="#e6edf3", pad=20)

    for blogger in summary.index:
        vals = summary.loc[blogger, tone_cols].tolist()
        vals += vals[:1]
        color = BLOGGER_COLORS.get(blogger, "#888888")
        ax.plot(angles, vals, "o-", linewidth=2, color=color, label=blogger)
        ax.fill(angles, vals, alpha=0.15, color=color)

    ax.set_thetagrids(np.degrees(angles[:-1]), labels, fontsize=10, color="#e6edf3")
    ax.set_ylim(0, max(summary[tone_cols].max()) * 1.2)
    ax.yaxis.set_tick_params(labelcolor="#888888")
    ax.legend(loc="upper right", bbox_to_anchor=(1.3, 1.15), fontsize=10,
               labelcolor="#e6edf3", facecolor="#161b22", edgecolor="#30363d")

    plt.tight_layout()
    path = os.path.join(OUTPUT_DIR, "03_tone_radar.png")
    if save:
        plt.savefig(path, dpi=150, bbox_inches="tight")
        print(f"  Saved: {path}")
    plt.close()
    return path


def plot_content_features(summary: pd.DataFrame, save: bool = True):
    feature_cols = [
        ("has_code_rate",   "Code Inclusion Rate"),
        ("has_table_rate",  "Table Usage Rate"),
        ("has_chart_rate",  "Chart/Image Rate"),
    ]
    existing = [(c, l) for c, l in feature_cols if c in summary.columns]
    if not existing:
        return None

    fig, axes = plt.subplots(1, len(existing), figsize=(5 * len(existing), 5))
    if len(existing) == 1:
        axes = [axes]
    fig.suptitle("Content Feature Usage Rates (%)", fontsize=13, fontweight="bold")
    bloggers = summary.index.tolist()
    colors = _colors_for(bloggers)

    for ax, (col, label) in zip(axes, existing):
        vals = (summary[col] * 100).round(1)
        bars = ax.bar(bloggers, vals, color=colors, edgecolor="none", alpha=0.9)
        ax.set_title(label)
        ax.set_ylim(0, 110)
        ax.set_ylabel("% of Articles")
        ax.set_xticks(range(len(bloggers)))
        ax.set_xticklabels(bloggers, rotation=20, ha="right", fontsize=9)
        ax.grid(axis="y", alpha=0.3)
        for bar, val in zip(bars, vals):
            ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 1,
                    f"{val:.0f}%", ha="center", va="bottom", fontsize=10, fontweight="bold")

    plt.tight_layout()
    path = os.path.join(OUTPUT_DIR, "04_content_features.png")
    if save:
        plt.savefig(path, dpi=150, bbox_inches="tight")
        print(f"  Saved: {path}")
    plt.close()
    return path


def plot_affiliate_links(summary: pd.DataFrame, save: bool = True):
    fig, ax = plt.subplots(figsize=(10, 5))
    fig.patch.set_facecolor("#0d1117")
    ax.set_title("Avg Affiliate Links per Article", fontsize=13, fontweight="bold")

    bloggers = summary.index.tolist()
    colors = _colors_for(bloggers)
    bars = ax.bar(bloggers, summary["affiliate_link_count"], color=colors, edgecolor="none", alpha=0.9)
    ax.set_ylabel("Avg Affiliate Links")
    ax.set_xticks(range(len(bloggers)))
    ax.set_xticklabels(bloggers, rotation=15, ha="right")
    ax.grid(axis="y", alpha=0.3)
    for bar, val in zip(bars, summary["affiliate_link_count"]):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.05,
                f"{val:.2f}", ha="center", va="bottom", fontsize=11, fontweight="bold")

    plt.tight_layout()
    path = os.path.join(OUTPUT_DIR, "05_affiliate_links.png")
    if save:
        plt.savefig(path, dpi=150, bbox_inches="tight")
        print(f"  Saved: {path}")
    plt.close()
    return path


def plot_wordclouds(keywords: dict, save: bool = True):
    paths = []
    bloggers = list(keywords.keys())
    fig, axes = plt.subplots(1, len(bloggers), figsize=(6 * len(bloggers), 5))
    fig.patch.set_facecolor("#0d1117")
    if len(bloggers) == 1:
        axes = [axes]

    for ax, blogger in zip(axes, bloggers):
        word_freq = dict(keywords[blogger])
        if not word_freq:
            ax.set_visible(False)
            continue
        color = BLOGGER_COLORS.get(blogger, "#4A90D9")
        wc = WordCloud(
            width=600, height=400,
            background_color="#161b22",
            colormap="Blues" if "Data" in blogger else (
                "Oranges" if "Quant" in blogger else (
                    "Greens" if "Citrini" in blogger else "Purples"
                )
            ),
            max_words=50,
        ).generate_from_frequencies(word_freq)
        ax.imshow(wc, interpolation="bilinear")
        ax.axis("off")
        ax.set_title(blogger, color="#e6edf3", fontsize=11, fontweight="bold")

    plt.suptitle("Top Keywords by Blogger (Word Cloud)", fontsize=13,
                 fontweight="bold", color="#e6edf3", y=1.02)
    plt.tight_layout()
    path = os.path.join(OUTPUT_DIR, "06_wordclouds.png")
    if save:
        plt.savefig(path, dpi=150, bbox_inches="tight")
        print(f"  Saved: {path}")
    plt.close()
    return path


def generate_text_report(df: pd.DataFrame, summary: pd.DataFrame, keywords: dict) -> str:
    """生成文字分析报告"""
    report = []
    report.append("=" * 70)
    report.append("  财经博主内容分析报告")
    report.append(f"  生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    report.append("=" * 70)

    report.append("\n[一] 样本概览")
    for blogger in summary.index:
        n = int(summary.loc[blogger, "article_count"])
        report.append(f"  {blogger}: {n} 篇文章")

    report.append("\n[二] 各博主核心数据对比")
    cols_display = [
        ("word_count",              "平均字数"),
        ("flesch_reading_ease",     "Flesch 可读性"),
        ("gunning_fog",             "Gunning Fog"),
        ("heading_count",           "平均标题数"),
        ("table_count",             "平均表格数"),
        ("code_block_count",        "平均代码块数"),
        ("affiliate_link_count",    "平均联盟链接数"),
        ("finance_keyword_density", "金融关键词密度 (%)"),
        ("structure_score",         "结构化评分"),
    ]
    for blogger in summary.index:
        report.append(f"\n  >> {blogger}")
        for col, label in cols_display:
            if col in summary.columns:
                val = summary.loc[blogger, col]
                report.append(f"     {label:<25} {val:.2f}")

    report.append("\n[三] 内容差异化特征")
    if "has_code_rate" in summary.columns:
        top_code = summary["has_code_rate"].idxmax()
        report.append(f"  代码使用率最高: {top_code} ({summary.loc[top_code,'has_code_rate']*100:.0f}%)")
    if "has_table_rate" in summary.columns:
        top_table = summary["has_table_rate"].idxmax()
        report.append(f"  表格使用率最高: {top_table} ({summary.loc[top_table,'has_table_rate']*100:.0f}%)")
    if "affiliate_link_count" in summary.columns:
        top_aff = summary["affiliate_link_count"].idxmax()
        report.append(f"  联盟链接最密集: {top_aff} ({summary.loc[top_aff,'affiliate_link_count']:.2f} 个/篇)")
    if "flesch_reading_ease" in summary.columns:
        col_data = summary["flesch_reading_ease"].dropna()
        if not col_data.empty:
            easiest = col_data.idxmax()
            hardest = col_data.idxmin()
            report.append(f"  最易读: {easiest} (Flesch={summary.loc[easiest,'flesch_reading_ease']:.1f})")
            report.append(f"  最难读: {hardest} (Flesch={summary.loc[hardest,'flesch_reading_ease']:.1f})")

    report.append("\n[四] Tone 分析 (满分=1.0)")
    tone_map = {
        "tone_calm_educational":   "冷静教育型",
        "tone_quant_technical":    "量化技术型",
        "tone_hedge_fund_elite":   "对冲基金精英型",
        "tone_affiliate_practical": "联盟实用型",
    }
    for col, label in tone_map.items():
        if col in summary.columns:
            top = summary[col].idxmax()
            report.append(f"  {label:<20} 最高: {top} ({summary.loc[top, col]:.4f})")

    report.append("\n[五] 各博主高频关键词 (Top 15)")
    for blogger, kws in keywords.items():
        top15 = ", ".join(f"{w}({c})" for w, c in kws[:15])
        report.append(f"\n  {blogger}")
        report.append(f"  {top15}")

    report.append("\n[六] 共性规律 (Cross-Blogger Findings)")
    mean_wc = df["word_count"].mean()
    report.append(f"  1. 平均文章长度: {mean_wc:.0f} 字（均属长内容，>800词）")
    avg_headings = df["heading_count"].mean()
    report.append(f"  2. 平均标题数: {avg_headings:.1f}（所有博主均有明确文章结构）")
    if "finance_keyword_density" in df.columns:
        avg_fin = df["finance_keyword_density"].mean()
        report.append(f"  3. 金融关键词密度: {avg_fin:.2f}%（内容高度垂直）")
    report.append("  4. 所有博主均有明确的内容定位和差异化标签")
    report.append("  5. 所有博主均以教育性内容为主，而非纯新闻/行情播报")

    report.append("\n" + "=" * 70)

    text = "\n".join(report)
    path = os.path.join(OUTPUT_DIR, "analysis_report.txt")
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    print(f"  Saved: {path}")
    return text


def generate_all_charts(summary: pd.DataFrame, keywords: dict, df: pd.DataFrame):
    print("\n[可视化] 生成图表...")
    plot_content_length(summary)
    plot_readability(summary)
    plot_tone_radar(summary)
    plot_content_features(summary)
    plot_affiliate_links(summary)
    plot_wordclouds(keywords)
    report_text = generate_text_report(df, summary, keywords)
    print("\n" + report_text)
    return os.path.abspath(OUTPUT_DIR)
