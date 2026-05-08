# Methodology

## Ownership inference

Most issuers use the **measurement alternative** under ASC 321 / ASU 2016-01 for non-marketable equity securities. They are required to disclose carrying value, cumulative upward and downward fair-value adjustments, and the valuation method, but **not** the actual stake percentage. To recover the stake we apply, conditional on an observable transaction in quarter q:

```
stake_q = (stake_{q-1} · V_pre  +  ΔC_q) / V_post
```

where:

- `stake_{q-1}` is the prior-quarter stake (anchored at the most recent court filing or voluntary disclosure)
- `V_pre`  is the pre-money valuation of the most recent observable transaction in quarter q
- `V_post` is the corresponding post-money valuation
- `ΔC_q`  is the new capital contributed by the issuer during quarter q (zero if it did not participate)

When no new round closes in the quarter, the stake percentage is unchanged and the disclosed gain is purely a markup:

```
FV_q = stake · V_post
```

The Microsoft / OpenAI relationship is the lone exception in scope: Microsoft uses the **equity method** under ASC 323, names the investee, and discloses the stake percentage directly. We carry MSFT figures as `disclosed`.

### Caveats

1. **Tranche timing** — the "14% Alphabet" figure (US v. Google, March 2025) includes commitments not yet drawn; convertible notes (e.g., Alphabet $750M Sep 2025 court filing) are valued differently until conversion.
2. **Liquidation preferences** — Series F / G are typically 1x non-participating preferred; this affects downside but not the up-round mark.
3. **Anti-dilution** — broad-based weighted-average is standard and rarely binds at up-rounds.
4. **Multiple-investee aggregation** — Alphabet's "primarily one investee" footnote masks SpaceX and other holdings; gain attribution to a specific lab is itself an estimate.
5. **Round timing vs. mark timing** — issuers typically recognize a markup at the next reporting period after an "observable transaction"; e.g., Amazon recognized the Anthropic Series G mark in Q1 2026 even though the round closed Feb 12 2026.

## Look-through EPS

Adapted from Buffett's framework (Berkshire shareholder letters, 1991 and 1999):

```
LookThrough_EPS = (GAAP_NetIncome  −  stake · ΔV_postmoney  +  stake · Investee_NetIncome_Q) / shares
```

Anthropic and OpenAI are unprofitable through 2027–2028 per public guidance, so the third term is generally negative, partially offsetting the second.

We publish three scenarios per investee:

- **Bear** — slow revenue growth, no profitability inflection through 2030
- **Base** — consensus path to profitability ~2028
- **Bull** — accelerated AGI revenue ramp

Inputs are toggleable in the Stage 3 dashboard.

## Event-study harness

Standard methodology (cf. Kurter & Bhatti 2024, SSRN 4912234, for AI-investment events):

- **Event windows** — `[-1, +1]` primary; `[-5, +5]` and `[-10, +10]` for robustness.
- **Estimation window** — `[-250, -11]`.
- **Asset-pricing model** — Fama-French 3-factor (FF5 robustness check).
- **Cross-wrapper test** — measure whether GOOGL CAR and AMZN CAR move proportionally to their estimated `(stake · ΔV_postmoney) / market_cap` exposure on Anthropic primary-round announcement days. Hypothesis: the announcement-day reaction underprices the markup channel because the gain hits *next* quarter's earnings, generating 10–60 day post-announcement drift in the under-priced wrapper.

We control for: same-day Big Tech earnings calls, capex guidance, model-release announcements, and FTC / SEC AI-cloud regulatory actions.

## Disclosure-quality scorer

See [`disclosure-rubric.md`](disclosure-rubric.md). Stage 2 will replace manual baseline scores with NLP-assisted automated scoring over the trailing 8 quarters per issuer, scored against a rubric of 7 ASC 321 / ASC 323 / ASC 820 disclosure dimensions.

## Data hygiene

- Cite a primary URL whenever feasible.
- When a permalink is unavailable, cite the news index and flag the row in `notes` for v0.2 sweep.
- Confidence flags (V / P / S) are applied conservatively.
- Tests in `tests/` enforce schema and minimum integrity (V rows must have `source_urls`, etc.).
