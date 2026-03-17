# Corridor Article: Data Capture & Keyword Validation Plan

**Scope:** MYR → USD via IBKR. Validate user-anxiety assumptions and get real keywords + frequency. No component development.

---

## Target Audience (anchor all data)

- **Who:** Malaysia (and nearby) users with meaningful capital, pre-transfer information anxiety; HNW traders, quant/geek users.
- **They care about:** True cost, hidden spread, intermediary fees, exact received amount; dislike black boxes; trust reproducible data and formulas.
- **Not serving:** Generic “best cross-border transfer tool” seekers; pure “click next” tutorial demand.

Data sources and keyword scope should align with **high-intent, cost-transparency, MYR→USD/IBKR**.

---

## 1. Validate “User Anxiety” from the Guides

### 1.1 Hypotheses to validate

- Do people actually search: **hidden spread**, **SWIFT intermediary fees**, **real cost funding IBKR**?
- Do they care about a **true cost = nominal fees + FX spread + intermediary leaks + time decay** breakdown?
- For **MYR → USD**, is the real focus “fees/spread” or “steps/deposit tutorial”?

### 1.2 Data sources

| Goal | Source | Use |
|------|--------|-----|
| Search volume for anxiety | Google Keyword Planner / Ahrefs / SEMrush | Check volume for MYR IBKR, SWIFT Malaysia, Malaysia to IBKR, hidden fees. |
| What users actually ask | **Reddit:** r/Malaysia, r/MalaysianPF, r/interactivebrokers, r/ibkr | Search history for MYR, IBKR, wire, Wise, SWIFT, spread, fees; classify as fees vs steps vs timing. |
| Long-tail phrasing | Google Suggest / Related / People also ask | Seed: "MYR to IBKR", "Malaysia wire IBKR", "SWIFT fee Malaysia"; record suggestions. |
| Competitor targeting | Competitor articles + SEO tools | Wise, IBKR, local banks: which H1/title they use for MYR→USD. |

**Output:** [anxiety_checklist.md](anxiety_checklist.md) — which assumptions are supported.

---

## 2. Keywords + Frequency for MYR → USD / IBKR

### 2.1 Keyword scope

- **Route:** MYR → USD, Malaysia → IBKR, MYR deposit IBKR, etc.
- **Intent:** cost, fees, spread, hidden, real rate, 实际到账, 手续费, 中转行.
- **Out of scope:** Generic “best cross-border transfer” (per guide).

### 2.2 How to get volume and frequency

- **Search volume:** Keyword Planner, Ahrefs, SEMrush, or Google Trends (relative).
- **Real wording frequency:** Reddit/forum posts — word/phrase frequency on title+body (use scripts in this folder).
- **Local variants:** Malay / Chinese queries for multi-language or one section.

**Output:** [keyword_table.md](keyword_table.md) (terms + volume/frequency + source + date); short conclusion in [article_angle.md](article_angle.md).

---

## 3. Execution order

1. **Anxiety validation** — search volume + Reddit + Google suggest → anxiety_checklist.md.
2. **Keyword + frequency** — same tools + scripts → keyword_table.md.
3. **Article angle** — title, H2s, must-cover keywords → article_angle.md.

---

## 4. Scripts in this folder

- **reddit_fetch_public.py** — Fetch Reddit via public JSON (no API app); save to `data/reddit_*.json`. Use this by default.
- **reddit_fetch.py** — Optional: same via PRAW when you have an approved Reddit API app.
- **keyword_frequency.py** — Read fetched JSON (or CSV); compute word/phrase frequency; write `data/keyword_frequency_*.csv`.

Run from project root or from `research/`; see [README.md](README.md).
