# Anxiety validation checklist (MYR → USD / IBKR)

Fill after running search-volume tools + Reddit fetch + Google Suggest.

| Hypothesis | Source | Result (volume / evidence) | Supported? |
|------------|--------|----------------------------|------------|
| Users search "hidden spread" (MYR/IBKR context) | Reddit keyword_frequency | "hidden" 37, "spread" 33 in discussion; bigrams like "those hidden", "hidden requirement" | Partially — "hidden" + "spread" both present; exact phrase not measurable from Reddit alone |
| Users search "SWIFT intermediary fees Malaysia" | Reddit keyword_frequency | "swift" 30, "fees" 214, "fee" 116, "malaysia" 185; "intermediary" 6 | Partially — SWIFT + fees + Malaysia strong; "intermediary" rare (use as subhead or body) |
| Users search "real cost funding Interactive Brokers" | Reddit keyword_frequency | "cost" in FOCUS not in top; "ibkr" 543, "deposit" 110, "transfer" 118, "fees"/"fee" 330 combined | Partially — cost/fees language strong; "real cost" phrasing add via Google Suggest later |
| Discussion focus: fees/spread vs steps/tutorial | Reddit keyword_frequency | High: ibkr 543, fees 214, account 278, fee 116, malaysia 185, usd 182, bank 161, wise 126, transfer 118, deposit 110, myr 91. Focus: rate 41, hidden 37, exchange 35, spread 33, swift 30, wire 21 | Supported — mix of both; cost terms (fees, spread, rate, wire, swift) material. Lead with cost, support with steps where relevant. |
| Users care about true cost = fees + spread + intermediary + time | Reddit / PAA phrasing | "fees/fee" 330, "spread" 33, "rate/rates" 57, "wire" 21, "swift" 30; "intermediary" 6; "time" 100 (generic) | Supported for fees + spread + wire/SWIFT; "intermediary" and "time decay" better as your framing (formula) than as user-search terms. |

**Conclusion:** Lead with: real cost, fees, spread, wire/SWIFT, Malaysia–IBKR, MYR–USD. Keep "hidden" and "real rate" in title/H2. Soften or move to subheads/body: "intermediary" (low frequency), "time decay" (introduce via your formula). Article should position as performance benchmark / cost audit, not step-by-step tutorial, to match the mix (cost + route clarity).

---

## Relevance over time (is this still a live concern?)

**Source:** `python time_distribution.py` on fetched `data/reddit_*.json` (275 posts).

| Year | All posts | Posts mentioning fee/spread/wire/swift/cost/transfer/… |
|------|-----------|--------------------------------------------------------|
| 2015–2020 | 1–3/yr | Same (very few) |
| 2021 | 15 | 13 |
| 2022 | 21 | 20 |
| 2023 | 20 | 20 |
| 2024 | 72 | 68 |
| 2025 | 109 | 107 |
| 2026 (partial) | 30 | 30 |

**Conclusion:** Discussion is **ongoing and growing**, not an old topic. Volume jumps in 2024–2025; 2026 partial year already has 30 posts. Almost all recent posts contain cost/transfer/route language. Safe to treat these anxieties as **current and relevant** for the article.
