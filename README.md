# bigtech-ai-stakes

A data tracker for U.S. public-company equity stakes in **Anthropic** and **OpenAI**, built from primary SEC filings (10-K / 10-Q / 8-K), public press releases, and court records.

> Information aggregation, not investment advice. The repo collects what's publicly disclosed; readers should not interpret it as a recommendation.

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

## Why this exists

Stake disclosures are inconsistent across issuers:

- **Microsoft** names OpenAI and discloses the percentage.
- **Amazon** names Anthropic in its 8-K and discloses dollar gains, but **not** the percentage.
- **Alphabet** does not name Anthropic in its financial-statement notes, using "primarily one investee" language.
- **NVIDIA** mentions OpenAI / Anthropic only in vague partnership prose, with no dollar or percentage figure.

So if you want a single place where these stakes are collected, sourced, and confidence-tagged, that is what this repo is.

## What's in this repo

| File | What it contains |
|---|---|
| [`data/ownership_summary.md`](data/ownership_summary.md) | Headline table above with full source links and confidence rationale |
| [`data/stakes/stakes.csv`](data/stakes/stakes.csv) | Curated point-in-time ownership snapshots per (investor, lab, date) |
| [`data/stakes_extracted.csv`](data/stakes_extracted.csv) | Auto-generated panel from 55 real SEC 10-K / 10-Q filings (22 with extractable data) |
| [`data/events/events.csv`](data/events/events.csv) | 17 primary funding rounds and Big Tech follow-on commitments (Anthropic Series C–G, OpenAI 2019–2026) |
| [`data/README.md`](data/README.md) | Schema dictionary for the CSV files |

Every row is tagged with a confidence flag: `V` (verified by primary source), `P` (probable, multi-source secondary), or `S` (speculative, single source).

## How the data is collected

1. **Curated rows** in `events.csv` and `stakes.csv` are entered by hand from primary sources (SEC filings, court records, company press releases).
2. **Machine-extracted rows** in `stakes_extracted.csv` come from `scripts/run_live_extraction.py`, which pulls 10-K / 10-Q filings via [`edgartools`](https://github.com/dgunning/edgartools) and applies regex extractors to the financial-statement footnotes.
3. **Confidence flags** are assigned conservatively. We only label a row `V` when the issuer themselves disclosed the figure in a primary document.

## How to browse the data

```bash
git clone https://github.com/YichengYang-Ethan/bigtech-ai-stakes
cd bigtech-ai-stakes
uv sync --all-extras

# Show the curated ownership snapshots
uv run bigtech-ai-stakes stakes

# Show recorded funding events for one lab
uv run bigtech-ai-stakes events --lab anthropic

# Pull fresh SEC filings and re-extract
uv run python scripts/run_live_extraction.py \
    --tickers GOOGL,AMZN,MSFT,NVDA --since 2023-01-01

# Streamlit dashboard for viewing the data interactively
uv run bigtech-ai-stakes dashboard
```

Requires Python 3.14+. Uses [uv](https://docs.astral.sh/uv/) for dependency management.

## Methodology

See [`docs/methodology.md`](docs/methodology.md) for how ownership percentages are inferred when the issuer doesn't disclose them directly (formula: `stake_q = (stake_{q-1} · V_pre + ΔC) / V_post`).

See [`docs/disclosure-rubric.md`](docs/disclosure-rubric.md) for how each issuer's footnote is scored against a 7-criterion disclosure-quality rubric.

## License & compliance

- **Code** — MIT (see [`LICENSE`](LICENSE))
- **Data** — CC-BY-4.0 (see [`LICENSE-DATA`](LICENSE-DATA))
- All data is derived from public SEC filings, court records, and company press releases. No scraping of secondary-market venues. PitchBook / Capital IQ / FactSet / Bloomberg derived data is not redistributed.
- This repo provides public information; it is **not** investment advice and contains no MNPI.

## Contributing

Issues and corrections welcome — especially:

- Misattributed source URLs
- Stale stake percentages where a more recent filing supersedes
- Errors in ownership-inference math

See [`.github/ISSUE_TEMPLATE/data-correction.md`](.github/ISSUE_TEMPLATE/data-correction.md).

## Author

Built by [Yicheng (Ethan) Yang](https://github.com/YichengYang-Ethan) — UIUC CS + Stats + Econ.
