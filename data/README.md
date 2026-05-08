# Data dictionary

All curated data is licensed under [CC-BY-4.0](../LICENSE-DATA). Cached SEC filings under `filings/` are not redistributed (they remain available directly from SEC EDGAR).

## `events/events.csv`

Primary funding rounds, tenders, convertible notes, and structural events for Anthropic and OpenAI. One row per *announced* event.

| Column | Type | Description |
|---|---|---|
| `event_id` | str | Stable identifier, format `<lab_initial>_<YYYYQq>_<round_or_party>_<seq>` (e.g., `A_2026Q1_G_001`). |
| `lab` | str | `anthropic` or `openai`. |
| `event_type` | str | One of: `primary_round`, `convertible_note`, `tender`, `commitment`, `restructure`, `extension`. |
| `announcement_date` | date | YYYY-MM-DD. |
| `v_pre_billion` | float? | Pre-money valuation (USD bn). May be empty for convertibles, commitments, or restructures. |
| `v_post_billion` | float? | Post-money valuation (USD bn). For `extension` rows this is the *reference valuation* at the announcement, not a fresh markup. |
| `raise_amount_billion` | float? | Total round size (USD bn) including secondary if applicable. Empty if not disclosed. |
| `lead_investors` | str | Comma-separated. |
| `key_strategic_investors` | str | Big Tech / public-co names that participated. Comma-separated. |
| `source_urls` | str | Pipe-separated `\|` list of URLs. Primary > secondary. Where the URL is a news index rather than a permalink, this is noted in `notes` and the row is flagged for `[v0.2 verify]`. |
| `confidence` | str | `V` / `P` / `S`. |
| `notes` | str | Free text. |

## `stakes/stakes.csv`

Point-in-time ownership snapshots per (investor, lab, date).

| Column | Type | Description |
|---|---|---|
| `investor_ticker` | str | Issuer ticker (`GOOGL`, `AMZN`, `MSFT`, `NVDA`, `CRM`, ...). |
| `investor_name` | str | Full name. |
| `lab` | str | `anthropic` or `openai`. |
| `snapshot_date` | date | Date the figure represents. |
| `stake_pct` | float? | Percentage stake. |
| `stake_pct_method` | str | How derived: `disclosed`, `court_filing`, `inferred_from_FV`, `analyst_estimate`, `leaked_cap_table`. |
| `fair_value_billion` | float? | Estimated mark-to-market value (USD bn). |
| `cumulative_cost_basis_billion` | float? | Total disclosed contributions to date (USD bn). |
| `source_urls` | str | Pipe-separated. |
| `confidence` | str | `V` / `P` / `S`. |
| `notes` | str | Free text including any caveats. |

## Confidence flags

- **V — Verified.** Sourced from a primary document (SEC filing, court record, or company press release).
- **P — Probable.** Multiple independent secondary sources concur but the primary document has not been independently verified by us.
- **S — Speculative.** Single source (typically social media or unattributed analyst) — included for completeness, treated as a hypothesis pending corroboration.

## Update process

1. New event announced → add row to `events.csv` with appropriate `confidence`.
2. Quarterly 10-Q / 10-K release for each issuer (within 2 weeks of filing) → add `stakes.csv` snapshot row.
3. Court-filing disclosure → add fresh `stakes.csv` row with the higher-confidence figure; retain old row for time-series integrity.
4. Tests in `tests/test_events_data.py` and `tests/test_stakes_data.py` enforce schema and integrity on every PR.

## Two unresolved factual conflicts to flag

1. **NVIDIA OpenAI total** — $30B (per leaked cap table, March 2026) vs. originally announced "up to $100B" headline (Sep 2025). We carry $30B with flag `P` until NVDA discloses in 10-K/10-Q.
2. **OpenAI March 2026 round size** — reports range $110B to $122B at $852B post-money. We carry $40B as the SoftBank extension only; total round size flagged in notes.
3. **Salesforce Anthropic ~1% stake** — single source (Benioff X post). Flag `S` until corroborated in CRM 10-Q.
