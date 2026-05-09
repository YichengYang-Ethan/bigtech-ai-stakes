# Public-company ownership in Anthropic and OpenAI

> The literal answer to "who owns how much of these two AI labs."
> Last reviewed: **2026-05-08**.

| Issuer | Lab | Stake % | How we know | Confidence |
|---|---|---:|---|:-:|
| **Microsoft** | **OpenAI** | **27.0%** | Disclosed directly in MSFT 10-Q (Apr 2026) under post-Oct-2025 PBC restructure; equity-method accounting. | ✅ V |
| **Alphabet (GOOGL)** | **Anthropic** | **~14%** (Mar 2025) → **~12–17%** today | Court filing (US v. Google) revealed 14% in March 2025; subsequent Anthropic Series F (Sep 2025) and Series G (Feb 2026) dilution puts the current figure in a 12–17% band depending on whether GOOGL participated. | 🟡 V (stale) → P (now) |
| **Amazon** | **Anthropic** | **~7–8%** | AMZN does **not** disclose the percentage; we infer from cumulative cost basis (~$8B) and disclosed fair-value adjustments (FY 2025 $15.2B + Q1 2026 $16.8B pre-tax gain). | 🟡 P |
| **NVIDIA** | **OpenAI** | **~3.47%** | NVDA does not disclose. Figure from leaked OpenAI cap table circulated by Sheel Mohnot (March 2026). | 🟡 P |
| **NVIDIA** | **Anthropic** | **~2.6%** | Inferred from the $10B Nov 2025 commitment / $380B Series G post-money; rolled into Series G consolidation. | 🟡 P |
| **Salesforce** | **Anthropic** | **~1%** | Benioff X post (May 2026) stating "$330M cumulative across rounds at ~1%." Single-source. | 🔴 S |
| **Qualcomm** | **Anthropic** | undisclosed size | Confirmed Series D Jan 2024 participant; size not disclosed. | 🟡 P |
| **Zoom** | **Anthropic** | undisclosed size | Strategic investor in Series C May 2023 (~$51M line item in Zoom FQ2'24). | 🟡 P |

## What "confidence" means

- **✅ V — Verified.** Directly disclosed in a primary document (SEC 10-K /
  10-Q / 8-K, court record, or company press release with a specific
  number).
- **🟡 P — Probable.** Inferred from disclosed cost basis and fair-value
  data, or sourced from multiple secondary outlets. Mathematically defensible
  but not directly disclosed by the issuer.
- **🔴 S — Speculative.** Single source (typically a social-media post or
  unattributed analyst). Held in the dataset for completeness, treated as
  hypothesis until corroborated.

## What we have hard numbers on (and what we don't)

**Hard-disclosed today:**
- MSFT 27.0% in OpenAI (Q3 FY26 10-Q)
- MSFT funding: $13B committed, $11.8B funded
- MSFT recognized $5.9B nine-month gain (Q3 FY26) on the OpenAI restructure

**Hard-disclosed for Alphabet / Anthropic:**
- 14% as of March 2025 (court filing — stale)
- $101.3B carrying value of "non-marketable equity securities" (GOOGL Q1 2026
  10-Q; this is everything Alphabet holds privately, not just Anthropic)
- GOOGL pointedly *does not* name Anthropic in financial-statement notes,
  using "primarily one investee" language

**Disclosed dollar amounts but not stake % for AMZN:**
- $15.2B FY 2025 pre-tax gain "from our investments in Anthropic" (10-K)
- $16.8B Q1 2026 pre-tax gain (8-K earnings release)
- $25B total commitment after April 2026 announcement
- Stake % itself is *not* in any AMZN filing

**Vague / no disclosure for NVDA:**
- 10-Q mentions "letter of intent" / "strategic partnership" — no $ or %
- Stake figures rely on leaked / inferred sources

## Where these numbers come from in this repo

- The verified figures (MSFT 27%, GOOGL $101.3B, etc.) live in
  [`stakes_extracted.csv`](stakes_extracted.csv) — auto-generated from real
  SEC 10-Ks / 10-Qs by `scripts/run_live_extraction.py`.
- The curated and inferred figures (AMZN ~7-8%, NVDA cap-table numbers, etc.)
  live in [`stakes/stakes.csv`](stakes/stakes.csv).
- Each row in either CSV cites its `source_urls` and carries a confidence flag.

## When this gets refreshed

- **Each issuer's quarterly 10-Q** (typically within 4 weeks of quarter end)
  may add a new disclosure row; rerun `scripts/run_live_extraction.py`.
- **Court filings** (e.g., the next US v. Google round) can suddenly reveal
  Alphabet's current Anthropic stake.
- **Big Tech earnings calls / press releases** are the fastest signal for
  any new commitment or extension.
