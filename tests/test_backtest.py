"""Tests for backtest math, strategies, and aggregate metrics.

All tests use synthetic returns generated inline — no yfinance, no network.
"""

from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd
import pytest

from bigtech_ai_stakes.backtest.core import (
    APPROXIMATE_EXPOSURES,
    TradeRecord,
    aggregate_metrics,
    announcement_day_return,
    compute_expected_return,
    cumulative_return,
    event_to_trading_day,
    holding_window_returns,
    lookup_market_cap,
    run_cross_wrapper_strategy,
    run_event_drift_strategy,
    stakes_for,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _bdate_index(start: str, n: int) -> pd.DatetimeIndex:
    return pd.bdate_range(start, periods=n)


def _flat_returns(idx: pd.DatetimeIndex, value: float = 0.0) -> pd.Series:
    return pd.Series(np.full(len(idx), value), index=idx)


def _synthetic_panel(
    start: str = "2023-01-02",
    n: int = 800,
    *,
    googl_drift: float = 0.0,
    amzn_drift: float = 0.0,
    spy_drift: float = 0.0,
) -> pd.DataFrame:
    """Build a synthetic returns panel with optional per-ticker constant drift."""
    idx = _bdate_index(start, n)
    return pd.DataFrame(
        {
            "GOOGL": _flat_returns(idx, googl_drift),
            "AMZN": _flat_returns(idx, amzn_drift),
            "MSFT": _flat_returns(idx, 0.0),
            "NVDA": _flat_returns(idx, 0.0),
            "SPY": _flat_returns(idx, spy_drift),
        }
    )


# ---------------------------------------------------------------------------
# Math primitives
# ---------------------------------------------------------------------------
class TestComputeExpectedReturn:
    def test_googl_anthropic_series_g(self) -> None:
        # 14% stake * 197B markup * 0.79 (after-tax) / 2200B mcap = 0.99%
        r = compute_expected_return(14.0, 197.0, 2200.0)
        assert r == pytest.approx(0.00990, abs=1e-4)

    def test_zero_market_cap(self) -> None:
        assert compute_expected_return(14.0, 197.0, 0.0) == 0.0

    def test_zero_stake(self) -> None:
        assert compute_expected_return(0.0, 197.0, 2200.0) == 0.0

    def test_negative_delta_v_clipped(self) -> None:
        assert compute_expected_return(14.0, -10.0, 2200.0) == 0.0


class TestEventToTradingDay:
    def test_trading_day_passes_through(self) -> None:
        idx = pd.bdate_range("2024-01-01", periods=10)
        ts = event_to_trading_day(idx, idx[5].date())
        assert ts == idx[5]

    def test_weekend_maps_to_next_monday(self) -> None:
        idx = pd.bdate_range("2024-01-01", periods=10)
        # 2024-01-06 is a Saturday; next trading day is Monday 2024-01-08
        ts = event_to_trading_day(idx, date(2024, 1, 6))
        assert ts.weekday() == 0  # Monday

    def test_past_end_raises(self) -> None:
        idx = pd.bdate_range("2024-01-01", periods=10)
        with pytest.raises(ValueError):
            event_to_trading_day(idx, date(2099, 1, 1))


class TestHoldingWindowReturns:
    def test_window_length_matches_offsets(self) -> None:
        idx = pd.bdate_range("2024-01-01", periods=60)
        s = pd.Series(np.arange(len(idx), dtype=float) / 1000, index=idx)
        out = holding_window_returns(s, idx[20].date(), window_start=1, window_end=30)
        assert len(out) == 30

    def test_out_of_range_raises(self) -> None:
        idx = pd.bdate_range("2024-01-01", periods=10)
        s = pd.Series(np.zeros(len(idx)), index=idx)
        with pytest.raises(ValueError):
            holding_window_returns(s, idx[5].date(), window_start=1, window_end=100)


class TestCumulativeReturn:
    def test_zeros_give_zero(self) -> None:
        idx = pd.bdate_range("2024-01-01", periods=20)
        assert cumulative_return(_flat_returns(idx, 0.0)) == 0.0

    def test_one_pct_daily_for_5_days(self) -> None:
        idx = pd.bdate_range("2024-01-01", periods=5)
        r = pd.Series(np.full(5, 0.01), index=idx)
        # (1.01)^5 - 1 ~= 0.05101
        assert cumulative_return(r) == pytest.approx(0.05101, abs=1e-4)

    def test_empty_series(self) -> None:
        assert cumulative_return(pd.Series(dtype=float)) == 0.0


class TestAnnouncementDayReturn:
    def test_returns_value_at_event(self) -> None:
        idx = pd.bdate_range("2024-01-01", periods=10)
        s = pd.Series(np.arange(len(idx)) * 0.001, index=idx)
        assert announcement_day_return(s, idx[3].date()) == pytest.approx(0.003)


# ---------------------------------------------------------------------------
# Aggregate metrics
# ---------------------------------------------------------------------------
class TestAggregateMetrics:
    def test_empty_returns_zero(self) -> None:
        m = aggregate_metrics([])
        assert m["n_trades"] == 0
        assert m["mean_abnormal_return"] == 0.0
        assert m["sharpe_annualized"] == 0.0

    def test_perfect_winner_metrics(self) -> None:
        trades = [
            TradeRecord(
                event_id=f"E{i}",
                event_date=date(2024, 1, 1),
                lab="anthropic",
                wrapper="GOOGL",
                direction="long",
                expected_return_announce=0.01,
                actual_return_announce=0.005,
                holding_period_return=0.02,
                benchmark_return=0.0,
                abnormal_return=0.02,
                stake_pct=14.0,
                market_cap_billion=2200.0,
            )
            for i in range(5)
        ]
        m = aggregate_metrics(trades, holding_days=30)
        assert m["n_trades"] == 5
        assert m["win_rate"] == 1.0
        assert m["mean_abnormal_return"] == pytest.approx(0.02)
        # std=0 across identical trades, sharpe falls to 0 by formula
        assert m["sharpe_annualized"] == 0.0

    def test_mixed_winners_losers(self) -> None:
        rng = np.random.default_rng(0)
        ar = rng.normal(0.01, 0.03, 30)
        trades = [
            TradeRecord(
                event_id=f"E{i}",
                event_date=date(2024, 1, 1),
                lab="anthropic",
                wrapper="GOOGL",
                direction="long",
                expected_return_announce=0.01,
                actual_return_announce=0.005,
                holding_period_return=float(ar[i]),
                benchmark_return=0.0,
                abnormal_return=float(ar[i]),
                stake_pct=14.0,
                market_cap_billion=2200.0,
            )
            for i in range(30)
        ]
        m = aggregate_metrics(trades, holding_days=30)
        assert 0.0 < m["win_rate"] < 1.0
        # sharpe should be roughly mean / std * sqrt(252/30)
        assert m["sharpe_annualized"] != 0.0


# ---------------------------------------------------------------------------
# End-to-end strategies
# ---------------------------------------------------------------------------
def _events_df_one_anthropic_round(event_date: date) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "event_id": "TEST_A1",
                "lab": "anthropic",
                "event_type": "primary_round",
                "announcement_date": pd.Timestamp(event_date),
                "v_pre_billion": 350.0,
                "v_post_billion": 380.0,
                "raise_amount_billion": 30.0,
                "lead_investors": "",
                "key_strategic_investors": "",
                "source_urls": "",
                "confidence": "V",
                "notes": "",
            }
        ]
    )


class TestRunEventDriftStrategy:
    def test_long_only_records_one_trade_per_wrapper(self) -> None:
        idx = _bdate_index("2025-01-02", 200)
        panel = _synthetic_panel(start="2025-01-02", n=200, googl_drift=0.001, amzn_drift=0.001)
        events = _events_df_one_anthropic_round(idx[100].date())
        result = run_event_drift_strategy(events, panel, lab_filter="anthropic")
        # GOOGL, AMZN, NVDA all hold Anthropic in APPROXIMATE_EXPOSURES
        assert {t.wrapper for t in result.trades} == {"GOOGL", "AMZN", "NVDA"}
        assert all(t.direction == "long" for t in result.trades)
        # GOOGL/AMZN have +0.1% daily drift -> positive holding returns
        for t in result.trades:
            if t.wrapper in {"GOOGL", "AMZN"}:
                assert t.holding_period_return > 0


class TestRunCrossWrapperStrategy:
    def test_pairs_long_short_one_each(self) -> None:
        idx = _bdate_index("2025-01-02", 200)
        # GOOGL drifts up post-event, AMZN flat -> GOOGL is the underreactor
        # only if its announce-day return is below expected
        panel = _synthetic_panel(start="2025-01-02", n=200, googl_drift=0.002, amzn_drift=0.0)
        events = _events_df_one_anthropic_round(idx[100].date())
        result = run_cross_wrapper_strategy(events, panel)
        # exactly one long and one short in the pair
        directions = {t.direction for t in result.trades}
        assert directions == {"long", "short"}
        wrappers = {t.wrapper for t in result.trades}
        assert wrappers == {"GOOGL", "AMZN"}

    def test_no_trades_when_no_events(self) -> None:
        panel = _synthetic_panel(start="2025-01-02", n=200)
        result = run_cross_wrapper_strategy(
            pd.DataFrame(
                columns=[
                    "event_id",
                    "lab",
                    "event_type",
                    "announcement_date",
                    "v_pre_billion",
                    "v_post_billion",
                    "raise_amount_billion",
                    "lead_investors",
                    "key_strategic_investors",
                    "source_urls",
                    "confidence",
                    "notes",
                ]
            ),
            panel,
        )
        assert result.n_trades == 0


# ---------------------------------------------------------------------------
# Exposures table
# ---------------------------------------------------------------------------
class TestExposuresTable:
    def test_googl_anthropic_present(self) -> None:
        assert "GOOGL" in APPROXIMATE_EXPOSURES
        assert "anthropic" in APPROXIMATE_EXPOSURES["GOOGL"]

    def test_lookup_market_cap_returns_int(self) -> None:
        cap = lookup_market_cap("GOOGL", 2026)
        assert isinstance(cap, float)
        assert cap > 0

    def test_unknown_wrapper_returns_zero_mcap(self) -> None:
        assert lookup_market_cap("AAPL", 2026) == 0.0

    def test_stakes_for_googl_anthropic(self) -> None:
        assert stakes_for("GOOGL", "anthropic") == 14.0

    def test_stakes_for_unknown_pair_zero(self) -> None:
        assert stakes_for("GOOGL", "openai") == 0.0
