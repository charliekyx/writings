# MYR → USD / IBKR Research

Plan, data-mining scripts, and deliverables for validating user anxiety and keyword frequency.

## Contents

| Item | Description |
|------|-------------|
| [PLAN.md](PLAN.md) | Full research plan (audience, sources, execution order). |
| [reddit_fetch_public.py](reddit_fetch_public.py) | **Default.** Fetch Reddit via public JSON (no API app) → `data/reddit_*.json`. |
| [reddit_fetch.py](reddit_fetch.py) | Optional: fetch via PRAW (requires Reddit API app) → same JSON format. |
| [keyword_frequency.py](keyword_frequency.py) | Word/phrase frequency from fetched text → `data/keyword_frequency_*.csv`. |
| [time_distribution.py](time_distribution.py) | Post count by year/month + anxiety-term posts by year (relevance over time). |
| [requirements.txt](requirements.txt) | Python deps for scripts. |
| [anxiety_checklist.md](anxiety_checklist.md) | Deliverable: which anxiety assumptions are supported. |
| [keyword_table.md](keyword_table.md) | Deliverable: keyword list + volume/frequency + source. |
| [article_angle.md](article_angle.md) | Deliverable: title/H2 and must-cover keywords. |
| [on-style/README.md](on-style/README.md) | **Style research:** fetch reference URLs → heuristic profile (`style_brief.md`) for voice/trust patterns. |

## Setup

```bash
cd porject_1_corridor/my_to_usd/research
python -m venv .venv
source .venv/bin/activate   # or .venv\Scripts\activate on Windows
pip install -r requirements.txt
```

### Reddit (choose one)

- **Public JSON (recommended):** No signup. Use `reddit_fetch_public.py`; only `requests` is needed.
- **PRAW (optional):** If you have an approved Reddit API app, set `REDDIT_CLIENT_ID`, `REDDIT_CLIENT_SECRET`, and optionally `REDDIT_USER_AGENT`, then run `reddit_fetch.py`.

## Running scripts

- **Fetch Reddit data (public JSON, no API key)**
  ```bash
  python reddit_fetch_public.py
  ```
  Writes `data/reddit_<subreddit>_<query_slug>.json`. Edit `SUBREDDITS` and `SEARCH_TERMS` in the script to change targets. Uses a short delay between requests to avoid rate limits.

- **Optional: fetch via Reddit API (PRAW)** — only if you have an approved app:
  ```bash
  export REDDIT_CLIENT_ID=... REDDIT_CLIENT_SECRET=...
  python reddit_fetch.py
  ```

- **Keyword frequency**
  ```bash
  python keyword_frequency.py
  ```
  Reads all `data/reddit_*.json` (or a CSV path via `--input`) and writes `data/keyword_frequency_<date>.csv`.

- **Reference author style (on-style)** — copy `on-style/urls.example.yaml` to `on-style/urls.yaml`, add URLs, then:
  ```bash
  python on-style/fetch_corpus.py --urls on-style/urls.yaml --out-dir on-style/corpus
  python on-style/extract_style_profile.py --corpus-dir on-style/corpus --out-dir on-style/output
  ```
  See [on-style/README.md](on-style/README.md).

## Data layout

- `data/` — created by scripts; holds `reddit_*.json` and `keyword_frequency_*.csv`. Add to `.gitignore` if you don’t want raw data in repo.
