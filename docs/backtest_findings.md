# Backtest findings (v0.1)

We test two strategies on Anthropic primary funding rounds (Series C, E, F, G;
N = 4 events) to see whether public-equity wrappers capture the implied
markup as a tradable signal.

## Strategies

**A — Long-only event drift.** At each Anthropic primary-round announcement,
buy GOOGL, AMZN, NVDA at the next trading-day close, hold for H trading days,
sell. Abnormal return = wrapper return − SPY return over the same window.

**B — Cross-wrapper pairs underreaction.** Compute expected announcement-day
return per wrapper using `stake × ΔV_post × (1 − tax) / market_cap`. Long the
wrapper with the largest positive `(expected − actual)` surprise (most
underreacting); short the smallest (most overreacting). Hold H days.
P&L = long_drift − short_drift.

## Results (real yfinance data, 2023-Q1 → 2026-Q1)

| Holding period | Strategy A Sharpe | Strategy A WR | Strategy A mean AR | Strategy B Sharpe | Strategy B WR |
|---:|---:|---:|---:|---:|---:|
| 10 trading days | **2.27** | 66.7% | +3.4% | -1.58 | 37.5% |
| 30 trading days | 0.83 | 58.3% | +3.2% | -1.22 | 25.0% |
| 60 trading days | 1.28 | 55.6% | +11.6% | -1.04 | 33.3% |

Per-trade rows are in `data/backtest_results.csv`.

## Findings

1. **Naive long-only works at every tested holding period.** Mean abnormal
   return per trade is +3.4% to +11.6%, win rate consistently above 55%, and
   max drawdown ≤ -10%. The 10-day Sharpe of 2.27 is the headline.
2. **The cross-wrapper underreaction hypothesis is empirically falsified
   in this sample.** The pairs trade loses money at every holding period
   (Sharpe -1.04 to -1.58). The wrapper that did *not* react on announcement
   day subsequently *underperformed* rather than catching up.
3. **Strategy A is partly driven by NVDA's general AI-sector rally.**
   Single biggest contribution: NVDA + 32% abnormal return in the 30 days
   after the May 2023 Anthropic Series C — but Anthropic exposure was only
   ~2.6% × small markup, so the "expected" return was tiny. The trade
   captured the broader sector rally, not the markup channel specifically.

## Caveats

- **Small N.** 4 events for pairs, 12 trades for long-only. Sharpe confidence
  intervals are wide; the headline numbers are point estimates only.
- **Stake / market-cap approximations.** v0.1 uses calendar-year-rounded
  market caps and one stake percentage per (wrapper, lab). Stage 1 ownership
  inference output (per-event-date stakes) is not yet wired in.
- **No transaction costs / borrow / slippage.** Live deployment would
  require these adjustments.
- **Selection bias.** Anthropic primary rounds happen in bull-market windows;
  same-window SPY does not fully control for sector exposure.

## What would change the picture

- More events: broaden to OpenAI rounds, include extension events with
  alternative ΔV_post handling.
- Per-event-date stakes from Stage 1 `inference.walk_forward`.
- Sector-neutral benchmark (MAGS / Big Tech basket) instead of SPY.
- Out-of-sample test on Anthropic rounds from May 2026 onward.

## Reproduction

```bash
uv run bigtech-ai-stakes backtest run --holding-days 30 --lab anthropic
```

The output goes to `data/backtest_results.csv` and the summary tables
print to stdout. Filings price cache at `data/returns_cache.parquet`
(gitignored).
