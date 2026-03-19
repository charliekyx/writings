"""
main.py - 财经博主文章分析脚本入口
用法:
  python main.py                    # 完整爬取 + 分析（慢，约30分钟）
  python main.py --quick            # 每个博主只抓 5 篇（快速测试）
  python main.py --load cache.pkl   # 从缓存加载，跳过爬取
  python main.py --save cache.pkl   # 爬取后保存缓存

生成结果存放在 ./output/ 目录中：
  analysis_report.txt      文字分析报告
  01_content_length_structure.png
  02_readability.png
  03_tone_radar.png
  04_content_features.png
  05_affiliate_links.png
  06_wordclouds.png
"""

import argparse
import pickle
import sys
import os

from scraper import scrape_all
from analyzer import run_analysis
from visualizer import generate_all_charts


def parse_args():
    parser = argparse.ArgumentParser(
        description="财经博主文章内容分析工具"
    )
    parser.add_argument(
        "--quick", action="store_true",
        help="快速模式：每位博主只处理 5 篇文章"
    )
    parser.add_argument(
        "--load", metavar="FILE",
        help="从 .pkl 缓存文件加载文章数据，跳过爬取"
    )
    parser.add_argument(
        "--save", metavar="FILE",
        help="爬取完成后将数据保存到 .pkl 缓存文件"
    )
    parser.add_argument(
        "--delay", type=float, default=1.5,
        help="爬取请求间隔秒数（默认 1.5）"
    )
    return parser.parse_args()


def main():
    args = parse_args()

    # --- 步骤 1: 获取文章数据（爬取或从缓存加载）---
    if args.load:
        if not os.path.exists(args.load):
            print(f"[ERROR] 缓存文件不存在: {args.load}")
            sys.exit(1)
        print(f"[加载] 从缓存读取: {args.load}")
        with open(args.load, "rb") as f:
            articles = pickle.load(f)
        print(f"  加载了 {len(articles)} 篇文章")
    else:
        max_articles = 5 if args.quick else None
        print("[爬取] 开始抓取文章...")
        if args.quick:
            print("  (快速模式: 每博主最多 5 篇)")
        articles = scrape_all(delay=args.delay, max_articles=max_articles)

        if args.save:
            with open(args.save, "wb") as f:
                pickle.dump(articles, f)
            print(f"[保存] 已缓存到: {args.save}")

    if not articles:
        print("[ERROR] 未能获取任何文章，请检查网络或 RSS 配置。")
        sys.exit(1)

    # --- 步骤 2: 文本分析 ---
    df, summary, keywords = run_analysis(articles)

    if df.empty:
        print("[ERROR] 分析后无有效数据（文章字数过少？）")
        sys.exit(1)

    print("\n[汇总统计]")
    print(summary.to_string())

    # --- 步骤 3: 可视化 + 报告 ---
    output_dir = generate_all_charts(summary, keywords, df)

    print(f"\n[完成] 所有结果已保存至: {output_dir}")
    print("  打开 analysis_report.txt 阅读文字报告")
    print("  打开 01~06_*.png 查看各分析图表")


if __name__ == "__main__":
    main()
