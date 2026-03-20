"""
utils.py
────────
各模块共用的工具函数。
- fetch_mid_rate()     : 从 Frankfurter 获取 MYR/USD 中间价
- append_jsonl()       : 原子追加一行到 .jsonl 文件
- load_jsonl()         : 加载 .jsonl 文件为 list[dict]
- save_chart()         : 统一保存图表到 charts/ 目录
- SESSION_FOR()        : 根据 UTC 小时判断交易时段
"""

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

# ── 路径配置 ────────────────────────────────────────────────────────────────
ROOT = Path(__file__).parent.parent          # my_to_usd/
CHARTS_DIR = ROOT / "charts"
DATA_DIR = ROOT / "data"
CHARTS_DIR.mkdir(exist_ok=True)


# ── 交易时段判断 ─────────────────────────────────────────────────────────────
def session_for(dt: datetime) -> str:
    """返回 UTC 时间对应的主要交易时段名称。"""
    h = dt.utctimetuple().tm_hour
    if 0 <= h < 8:
        return "Asia"
    elif 8 <= h < 16:
        return "Europe"
    else:
        return "US"


# ── Mid-market 汇率 ──────────────────────────────────────────────────────────
def fetch_mid_rate(
    base: str = "MYR",
    target: str = "USD",
    retries: int = 3,
    backoff: float = 2.0,
) -> dict:
    """
    从 Frankfurter API 获取 base→target 的中间价。
    返回:
        {
          "timestamp": "2026-03-20T06:30:00Z",
          "base": "MYR",
          "target": "USD",
          "mid_rate": 0.2247,     # 1 MYR = X USD
          "source": "frankfurter"
        }
    """
    url = f"https://api.frankfurter.app/latest?from={base}&to={target}"
    for attempt in range(retries):
        try:
            resp = requests.get(url, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            mid_rate = data["rates"][target]
            ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            return {
                "timestamp": ts,
                "base": base,
                "target": target,
                "mid_rate": mid_rate,
                "source": "frankfurter",
            }
        except Exception as exc:
            if attempt < retries - 1:
                time.sleep(backoff * (attempt + 1))
            else:
                raise RuntimeError(f"fetch_mid_rate failed after {retries} attempts: {exc}")


# ── JSONL I/O ────────────────────────────────────────────────────────────────
def append_jsonl(path: Path, record: dict) -> None:
    """将一个 dict 以 JSON 格式追加到 .jsonl 文件（每行一条记录）。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def load_jsonl(path: Path) -> list:
    """加载 .jsonl 文件，返回 list[dict]。文件不存在则返回空列表。"""
    if not path.exists():
        return []
    records = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    return records


# ── CSV I/O ──────────────────────────────────────────────────────────────────
def load_csv(path: Path):
    """加载 CSV 文件（使用 pandas）。"""
    import pandas as pd
    return pd.read_csv(path, parse_dates=["timestamp"] if "timestamp" in
                       pd.read_csv(path, nrows=0).columns else [])


# ── 图表保存 ──────────────────────────────────────────────────────────────────
def save_chart(fig, name: str) -> Path:
    """
    统一保存 matplotlib figure 到 charts/ 目录。
    name: 文件名（不含扩展名），如 'm1_wise_spread_over_time'
    """
    import matplotlib
    out = CHARTS_DIR / f"{name}.png"
    fig.savefig(out, dpi=150, bbox_inches="tight")
    matplotlib.pyplot.close(fig)
    print(f"Chart saved: {out}")
    return out


# ── 打印工具 ──────────────────────────────────────────────────────────────────
def section(title: str) -> None:
    print(f"\n{'='*60}\n{title}\n{'='*60}")
