# Disclosure-quality rubric

Each issuer's most recent 10-K / 10-Q footnote on non-marketable equity securities is scored 0–10 across 7 criteria. Weights are equal. Higher = better disclosure.

| # | Criterion | Description |
|---|---|---|
| 1 | Investee named | Is the specific lab (Anthropic / OpenAI) identified by name in the financial-statement footnote? |
| 2 | Stake disclosed | Is the percentage ownership stated? |
| 3 | Method disclosed | Are the valuation methods (option pricing, market comparable, common-stock equivalent) named? |
| 4 | Sensitivity to V_post | Is the FV sensitivity to the underlying post-money assumption disclosed? |
| 5 | Related-party | Is the relationship treated under ASC 850 if material? |
| 6 | Quarterly breakout | Are the components of cumulative adjustment broken out by quarter (upward vs. downward)? |
| 7 | Concentration risk | Is the single-investee concentration disclosed at portfolio level? |

## Baseline scoring (May 2026, manual; Stage 2 replaces with NLP)

| Issuer | C1 (named) | C2 (stake) | C3 (method) | C4 (sensitivity) | C5 (related-party) | C6 (qtr breakout) | C7 (concentration) | Total |
|---|---|---|---|---|---|---|---|---|
| MSFT  | ✓ | ✓ | partial | – | partial | partial | partial | TBD |
| AMZN  | ✓ | – | partial | – | – | partial | – | TBD |
| GOOGL | – | – | ✓ | – | – | ✓ | partial | TBD |
| NVDA  | partial | – | – | – | – | – | – | TBD |

### Notes per issuer

- **Microsoft** — names OpenAI in the 10-Q; equity-method accounting requires fuller disclosure than ASC 321. Stake disclosed as a percentage. Methodology (equity method) is implicit.
- **Amazon** — names Anthropic in the earnings release ("from our investments in Anthropic"). Stake percentage is *not* disclosed; can only be inferred from cumulative cost basis vs. fair value.
- **Alphabet** — does *not* name Anthropic in financial-statement notes ("primarily one investee"). However, methodology language is more specific than peers ("option pricing models, market comparable approach, and common stock equivalent method"). Quarterly upward / downward gains are broken out cleanly.
- **NVIDIA** — names OpenAI and Anthropic in MD&A but not in financial-statement notes. Stake is buried in aggregate non-marketable equity total.

## Universal weakness

**No issuer currently discloses sensitivity** of the carrying value to a change in the underlying post-money valuation (criterion 4). This is the single most informative disclosure that does not currently exist; flagging it is a candidate finding for the Finance Research Letters note.

## Stage 2 implementation

- Pull the `Financial Instruments` / `Equity Securities` footnote from each 10-Q / 10-K via `edgartools`.
- Apply a Claude-rated rubric scoring each footnote 0/0.5/1 on each criterion; aggregate to a 0–7 total.
- Compare against a placebo rubric on a non-AI-investee issuer (e.g., a Berkshire-style holding company) for baseline noise.
- Time-series the score per issuer over 8 quarters to detect disclosure drift after each restructure / round.
