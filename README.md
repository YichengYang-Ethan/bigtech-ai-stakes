# bigtech-ai-stakes

Open-source tracker for U.S. public-company equity stakes in **Anthropic** and **OpenAI**, derived from primary SEC filings (10-K / 10-Q / 8-K), public press releases, and court records.

> **Status:** v0.1 (May 2026) — actively developed.

## Headline: who owns what (2026-05-08)

| Issuer | Lab | Stake % | Source | Confidence |
|---|---|---:|---|:-:|
| **Microsoft** | OpenAI | **27.0%** | MSFT 10-Q (Apr 2026) | ✅ V |
| **Alphabet** | Anthropic | **~14%** (Mar 2025) → **~12–17%** today | Court filing + dilution math | 🟡 V → P |
| **Amazon** | Anthropic | **~7–8%** | Inferred from cost basis vs fair value | 🟡 P |
| **NVIDIA** | OpenAI | **~3.47%** | Leaked cap table (Mar 2026) | 🟡 P |
| **NVIDIA** | Anthropic | **~2.6%** | Inferred from Nov 2025 $10B commitment | 🟡 P |
| **Salesforce** | Anthropic | **~1%** | Benioff X post | 🔴 S |

**Only the MSFT figure is directly disclosed by the issuer in a SEC filing.**
Alphabet's 14% came from a March 2025 court filing and is now stale (Anthropic
has had two rounds since). Amazon and NVIDIA do not disclose their stake
percentages at all — those are inferred from disclosed cost basis vs. fair
value, or sourced from leaked / secondary documents.

Full source links and confidence rationale: [`data/ownership_summary.md`](data/ownership_summary.md).
Per-filing extraction: [`data/stakes_extracted.csv`](data/stakes_extracted.csv).
Curated snapshot: [`data/stakes/stakes.csv`](data/stakes/stakes.csv).

## Why this exists

In Q1 2026, Alphabet booked ~$28.7B of "net gains on equity securities" tied primarily to its Anthropic stake; Amazon disclosed $16.8B of pre-tax gains "from our investments in Anthropic"; Microsoft recognized ~$5.9B of cumulative gain related to the OpenAI October 2025 restructure. These marks now drive a meaningful share of Mag-7 reported earnings — yet **no public dataset reconstructs the underlying ownership economics**.

This project does that, transparently, from primary sources only:

1. **First open quarterly panel (2023–2026)** of disclosed fair-value adjustments, carrying values, and inferred ownership percentages for GOOGL, AMZN, MSFT, NVDA (plus a "small holders" tab for CRM, QCOM, ZM) in Anthropic and OpenAI.
2. **Ownership inference** from ASC 321 / ASC 323 footnote disclosures, anchored on known post-money valuations from primary press releases.
3. **Event-study harness** for primary-round announcements, with a cross-wrapper arbitrage check (does GOOGL move proportionally to AMZN around Anthropic events?).
4. **Look-through EPS** that strips AI-stake markups from reported earnings — a Buffett-style "core operating EPS" for Mag-7.
5. **Disclosure-quality scorecard** scoring each issuer's footnote against a 7-criterion rubric (named investee? stake disclosed? method? sensitivity? related-party?).

## Scope (v0.1)

**Labs covered:** Anthropic, OpenAI.
**Issuers covered:** GOOGL, AMZN, MSFT, NVDA, plus a "small holders" tab for CRM, QCOM, ZM.
**Period:** 2023-Q1 → present.

**Out of scope (v0.1):** xAI, Mistral, Cohere, Perplexity, DeepSeek; private-only investors (SoftBank, GIC, etc.); secondary-market price scraping (Forge / Hiive ToS prohibit it).

## Status

| Stage | Status |
|---|---|
| 0 — Scaffold + initial events.csv + stakes.csv | ✅ |
| 1 — EDGAR adapter + footnote extractor + ownership inference | ✅ |
| 2 — Event study + look-through EPS + disclosure scorer | ✅ |
| 2 v0.2 — Live SEC extraction (55 filings, 22 with extracted data) | ✅ |
| 3.1 — Streamlit dashboard | ✅ |
| 3.2 — Cross-wrapper arbitrage backtest | ✅ |
| 3.3 — Live monitor + Telegram alerts (optional) | ⏳ |
| 3.4 — Portfolio polish (screenshots, demo, deploy badge) | ⏳ |

## Headline backtest result

> **Long Big Tech wrappers (GOOGL / AMZN / NVDA) on Anthropic primary-round
> announcements, hold 10 trading days, exit. Sharpe 2.27, win rate 66.7%,
> mean +3.4% abnormal vs SPY** (N = 12 trades across Series C / E / F / G).
> Cross-wrapper pairs-trade variant (long underreactor / short overreactor)
> empirically *fails*: Sharpe -1.04 to -1.58 across every tested holding
> period. The simpler long-only captures the markup channel; the more
> sophisticated version overcomplicates and loses money.

See [`docs/backtest_findings.md`](docs/backtest_findings.md) for full results
and `data/backtest_results.csv` for per-trade detail.

## Quickstart

```bash
git clone https://github.com/YichengYang-Ethan/bigtech-ai-stakes
cd bigtech-ai-stakes
uv sync --all-extras
uv run pytest
uv run bigtech-ai-stakes --help
uv run bigtech-ai-stakes events --lab anthropic
uv run bigtech-ai-stakes stakes --investor MSFT
```

Requires Python 3.14+. Uses [uv](https://docs.astral.sh/uv/) for dependency management.

### Live SEC extraction

```bash
uv run python scripts/run_live_extraction.py \
    --tickers GOOGL,AMZN,MSFT,NVDA --since 2023-01-01
# writes data/stakes_extracted.csv
```

### Streamlit dashboard

```bash
uv run bigtech-ai-stakes dashboard
# or directly:
uv run --extra dashboard --extra analysis streamlit run streamlit_app.py
```

## Data

Two flat CSVs, schema documented in [`data/README.md`](data/README.md):

- **`data/events/events.csv`** — primary funding rounds, convertible notes, tenders, and Big Tech follow-on commitments.
- **`data/stakes/stakes.csv`** — point-in-time ownership and fair-value snapshots per (investor, lab, date).

Every row is tagged with confidence: `V` (verified by primary source), `P` (probable, multi-source secondary), `S` (speculative, single source).

## Methodology

See [`docs/methodology.md`](docs/methodology.md) for the ownership-inference math (`stake_q = (stake_{q-1}·V_pre + ΔC) / V_post`) and look-through EPS formula.

See [`docs/disclosure-rubric.md`](docs/disclosure-rubric.md) for the 7-criterion disclosure-quality rubric.

## Citing

Pre-1.0: cite as a working repository. Post-1.0: SSRN working paper and Zenodo DOI to follow.

## License & compliance

- **Code** — MIT (see [`LICENSE`](LICENSE))
- **Data** — CC-BY-4.0 (see [`LICENSE-DATA`](LICENSE-DATA))
- All data is derived from public SEC filings, court records, and company press releases. **No scraping** of secondary-market venues — Forge / Hiive ToS prohibit it. PitchBook / Capital IQ / FactSet / Bloomberg derived data is not redistributed.
- This is research output, **not** investment advice, and contains no MNPI.

## Contributing

Issues and corrections welcome — especially:

- Misattributed source URLs
- Stale stake percentages where a more recent filing supersedes
- Errors in ownership-inference math

See [`.github/ISSUE_TEMPLATE/data-correction.md`](.github/ISSUE_TEMPLATE/data-correction.md).

## Author

Built by [Yicheng (Ethan) Yang](https://github.com/YichengYang-Ethan) — UIUC CS + Stats + Econ.
