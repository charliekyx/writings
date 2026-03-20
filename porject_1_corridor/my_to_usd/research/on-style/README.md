# On-style: reference author → heuristic writing profile

Personal research only: fetch public HTML, extract main text locally, compute **structure/voice metrics** (not generative “rewrite in X’s style”). Do not paste others’ sentences into your article; use the **checklist** to tune your own MYR→USD / audit voice.

## Setup

**推荐：** 在上一级 `research` 里建虚拟环境（与 Reddit/keyword 脚本共用依赖）：

```bash
cd porject_1_corridor/my_to_usd/research   # 按你本机路径调整
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

若你当前 shell 已经在 `on-style/` 目录下，依赖文件在上一级，可任选其一：

```bash
pip install -r ../requirements.txt
# 或（本目录已提供转发文件）
pip install -r requirements.txt
```

注意：`python on-style/fetch_corpus.py` 等命令仍建议在 **`research` 目录**下执行（与 README 下文一致），这样相对路径 `on-style/...` 才正确。

## 1) Configure URLs

```bash
cp on-style/urls.example.yaml on-style/urls.yaml
# Edit urls.yaml: set user_agent, add URLs under `urls:` (strings or `{ url: ... }`)
```

Prefer a **short explicit list** (e.g. posts on [kalzumeus.com](https://www.kalzumeus.com)) instead of scraping entire sitemaps.

## 2) Fetch corpus

```bash
python on-style/fetch_corpus.py --urls on-style/urls.yaml --out-dir on-style/corpus --delay 1.5
```

- Checks `robots.txt` before each GET; disallowed URLs are **skipped** unless you pass `--force` (only when you have permission).
- Writes `corpus/<slug>.md` with YAML frontmatter (`source_url`, `fetched_at`, …).
- **`corpus/*.md` is gitignored** — do not commit full articles.

## 3) Build profile + brief

```bash
python on-style/extract_style_profile.py --corpus-dir on-style/corpus --out-dir on-style/output
```

Outputs:

- `output/style_profile.json` — per-doc metrics + aggregates + tag counts.
- `output/style_brief.md` — human-readable checklist tags (e.g. `early_numbers`, `disclosure_near_top`).

Optional: `--min-chars 500` (default) skips tiny extractions.

## Ethics & plagiarism

- Fetching for **private analysis** is different from **republishing** someone else’s work. Keep fetched files local; your published piece should use **your** data, disclosures, and wording.
- If a site disallows automated access, respect it or use **manual** save → drop cleaned `.md` into `corpus/` and run step 3 only.

## Files

| File | Role |
|------|------|
| `fetch_corpus.py` | URLs → `corpus/*.md` |
| `extract_style_profile.py` | `corpus/*.md` → `output/` |
| `style_heuristics.py` | Metrics (readability, pronouns, openings, disclaimers, …) |
