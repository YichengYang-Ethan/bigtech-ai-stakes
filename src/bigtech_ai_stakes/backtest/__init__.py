"""Stage 3.2 — Cross-wrapper arbitrage backtest.

Tests the hypothesis that when a private AI lab announces a primary funding
round, the public-equity wrappers (GOOGL holding Anthropic, AMZN holding
Anthropic, MSFT holding OpenAI, ...) underreact on announcement day relative
to the implied markup, generating 30-day drift the cross-wrapper strategy
captures.
"""

from bigtech_ai_stakes.backtest.core import (
    APPROXIMATE_EXPOSURES,
    BacktestSummary,
    TradeRecord,
    aggregate_metrics,
    compute_expected_return,
    cumulative_return,
    event_to_trading_day,
    holding_window_returns,
    run_cross_wrapper_strategy,
    run_event_drift_strategy,
)

__all__ = [
    "APPROXIMATE_EXPOSURES",
    "BacktestSummary",
    "TradeRecord",
    "aggregate_metrics",
    "compute_expected_return",
    "cumulative_return",
    "event_to_trading_day",
    "holding_window_returns",
    "run_cross_wrapper_strategy",
    "run_event_drift_strategy",
]
