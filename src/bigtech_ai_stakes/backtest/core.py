"""Backtest math: implied exposures, event windows, two strategies, metrics.

No yfinance dependency here — :mod:`bigtech_ai_stakes.backtest.prices` does the
network fetch. This module is fully unit-testable with synthetic returns.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Final

import numpy as np
import pandas as pd

# ----------------------------------------------------------------------------
# Approximate stakes and market caps for v0.1.
#
# These are best-public-estimates per (wrapper, lab) keyed by the calendar year
# of the event. They are deliberately rounded — Stage 4 will replace with
# precise event-date stakes from the inference module.
# ----------------------------------------------------------------------------
APPROXIMATE_EXPOSURES: Final[dict[str, dict[str, dict[str, dict[int, float] | float]]]] = {
    "GOOGL": {
        "anthropic": {
            "stake_pct": 14.0,
            "market_cap_billion": {2023: 1500, 2024: 1900, 2025: 2050, 2026: 2200},
        },
    },
    "AMZN": {
        "anthropic": {
            "stake_pct": 7.8,
            "market_cap_billion": {2023: 1100, 2024: 1750, 2025: 1900, 2026: 2050},
        },
    },
    "MSFT": {
        "openai": {
            "stake_pct": 27.0,
            "market_cap_billion": {2023: 2400, 2024: 3100, 2025: 3300, 2026: 3500},
        },
    },
    "NVDA": {
        "anthropic": {
            "stake_pct": 2.6,
            "market_cap_billion": {2023: 1100, 2024: 3300, 2025: 3700, 2026: 4000},
        },
        "openai": {
            "stake_pct": 3.47,
            "market_cap_billion": {2023: 1100, 2024: 3300, 2025: 3700, 2026: 4000},
        },
    },
}


def lookup_market_cap(wrapper: str, year: int) -> float:
    """Return the rough market cap in USD bn for ``wrapper`` in ``year``."""
    for lab_data in APPROXIMATE_EXPOSURES.get(wrapper, {}).values():
        cap_table = lab_data.get("market_cap_billion", {})
        if isinstance(cap_table, dict):
            return float(cap_table.get(year, list(cap_table.values())[-1]))
    return 0.0


def stakes_for(wrapper: str, lab: str) -> float:
    """Return stake percentage held by ``wrapper`` in ``lab``."""
    lab_data = APPROXIMATE_EXPOSURES.get(wrapper, {}).get(lab, {})
    stake = lab_data.get("stake_pct", 0.0)
    return float(stake) if isinstance(stake, int | float) else 0.0


# ----------------------------------------------------------------------------
# Math primitives
# ----------------------------------------------------------------------------
def compute_expected_return(
    stake_pct: float,
    delta_v_post_billion: float,
    market_cap_billion: float,
    *,
    tax_rate: float = 0.21,
) -> float:
    """Expected announcement-day return = stake * delta_V_post * (1-tax) / mcap.

    All valuations in USD billions; ``stake_pct`` in percent (0-100).
    """
    if market_cap_billion <= 0 or delta_v_post_billion < 0:
        return 0.0
    stake = stake_pct / 100.0
    return stake * delta_v_post_billion * (1 - tax_rate) / market_cap_billion


def event_to_trading_day(returns_index: pd.Index, event_date: date) -> pd.Timestamp:
    """Map an event_date to the next available trading day in the index.

    ``returns_index`` is expected to be a sorted DatetimeIndex at runtime; the
    relaxed static type lets callers pass `Series.index` directly without casts.
    """
    ts = pd.Timestamp(event_date)
    if ts in returns_index:
        return ts
    pos = int(returns_index.searchsorted(ts))
    if pos >= len(returns_index):
        raise ValueError(f"event_date {event_date} is past the end of the returns index")
    result = returns_index[pos]
    return pd.Timestamp(result)


def holding_window_returns(
    asset_returns: pd.Series,
    event_date: date,
    *,
    window_start: int = 1,
    window_end: int = 30,
) -> pd.Series:
    """Slice asset returns from event_date+window_start to event_date+window_end.

    Both bounds inclusive; offsets count trading days from the event-date row.
    """
    ts = event_to_trading_day(asset_returns.index, event_date)
    loc = asset_returns.index.get_loc(ts)
    if isinstance(loc, slice | np.ndarray):
        raise ValueError(f"event_date {event_date} matches multiple rows in returns index")
    event_idx = int(loc)
    lo = event_idx + window_start
    hi = event_idx + window_end + 1
    if lo < 0 or hi > len(asset_returns):
        raise ValueError(
            f"window [{window_start}, {window_end}] out of range: "
            f"event_idx={event_idx}, len={len(asset_returns)}"
        )
    return asset_returns.iloc[lo:hi].copy()


def cumulative_return(returns: pd.Series) -> float:
    """Geometric cumulative return of a daily-return series."""
    if returns.empty:
        return 0.0
    arr = returns.to_numpy(dtype=float)
    return float(np.prod(1.0 + arr) - 1.0)


def announcement_day_return(asset_returns: pd.Series, event_date: date) -> float:
    """Return on the announcement trading day (or the next trading day)."""
    ts = event_to_trading_day(asset_returns.index, event_date)
    return float(asset_returns.loc[ts])


# ----------------------------------------------------------------------------
# Trade records and strategy outputs
# ----------------------------------------------------------------------------
@dataclass
class TradeRecord:
    """A single backtest trade."""

    event_id: str
    event_date: date
    lab: str
    wrapper: str
    direction: str  # "long" or "short"
    expected_return_announce: float
    actual_return_announce: float
    holding_period_return: float
    benchmark_return: float
    abnormal_return: float  # holding period vs benchmark
    stake_pct: float
    market_cap_billion: float
    notes: str = ""


@dataclass
class BacktestSummary:
    """Aggregate metrics across a backtest run."""

    strategy: str
    n_trades: int
    mean_abnormal_return: float
    median_abnormal_return: float
    win_rate: float
    sharpe_annualized: float
    max_drawdown: float
    total_pnl: float
    trades: list[TradeRecord] = field(default_factory=list)


def _build_summary(strategy: str, trades: list[TradeRecord], holding_days: int) -> BacktestSummary:
    m = aggregate_metrics(trades, holding_days=holding_days)
    return BacktestSummary(
        strategy=strategy,
        n_trades=int(m["n_trades"]),
        mean_abnormal_return=m["mean_abnormal_return"],
        median_abnormal_return=m["median_abnormal_return"],
        win_rate=m["win_rate"],
        sharpe_annualized=m["sharpe_annualized"],
        max_drawdown=m["max_drawdown"],
        total_pnl=m["total_pnl"],
        trades=trades,
    )


# ----------------------------------------------------------------------------
# Strategies
# ----------------------------------------------------------------------------
def run_event_drift_strategy(
    events: pd.DataFrame,
    returns_panel: pd.DataFrame,
    *,
    benchmark: str = "SPY",
    holding_window: tuple[int, int] = (1, 30),
    lab_filter: str | None = None,
    event_types: tuple[str, ...] = ("primary_round",),
    exposures: dict[str, dict[str, dict[str, dict[int, float] | float]]] | None = None,
) -> BacktestSummary:
    """Long-only: buy each wrapper holding the lab on event date, hold ``window`` days.

    Records P&L and abnormal return relative to the benchmark over the same
    holding window. Skips events without V_pre / V_post.
    """
    expo = exposures or APPROXIMATE_EXPOSURES
    selected = events[events["v_post_billion"].notna() & events["v_pre_billion"].notna()].copy()
    if event_types:
        selected = selected[selected["event_type"].isin(event_types)]
    if lab_filter:
        selected = selected[selected["lab"].str.lower() == lab_filter.lower()]

    trades: list[TradeRecord] = []
    for _, evt in selected.iterrows():
        lab = str(evt["lab"]).lower()
        delta_v = float(evt["v_post_billion"]) - float(evt["v_pre_billion"])
        event_date = pd.Timestamp(evt["announcement_date"]).date()
        year = event_date.year
        for wrapper, lab_map in expo.items():
            lab_data = lab_map.get(lab)
            if not lab_data:
                continue
            stake_pct = lab_data["stake_pct"]
            cap_table = lab_data.get("market_cap_billion", {})
            mcap = (
                float(cap_table.get(year, list(cap_table.values())[-1]))
                if isinstance(cap_table, dict)
                else 0.0
            )
            if not isinstance(stake_pct, int | float) or mcap == 0:
                continue
            try:
                actual_announce = announcement_day_return(returns_panel[wrapper], event_date)
                asset_window = holding_window_returns(
                    returns_panel[wrapper],
                    event_date,
                    window_start=holding_window[0],
                    window_end=holding_window[1],
                )
                bench_window = holding_window_returns(
                    returns_panel[benchmark],
                    event_date,
                    window_start=holding_window[0],
                    window_end=holding_window[1],
                )
            except KeyError, ValueError:
                continue
            expected = compute_expected_return(float(stake_pct), delta_v, mcap)
            holding_ret = cumulative_return(asset_window)
            bench_ret = cumulative_return(bench_window)
            trades.append(
                TradeRecord(
                    event_id=str(evt["event_id"]),
                    event_date=event_date,
                    lab=lab,
                    wrapper=wrapper,
                    direction="long",
                    expected_return_announce=expected,
                    actual_return_announce=actual_announce,
                    holding_period_return=holding_ret,
                    benchmark_return=bench_ret,
                    abnormal_return=holding_ret - bench_ret,
                    stake_pct=float(stake_pct),
                    market_cap_billion=mcap,
                )
            )

    return _build_summary("event_drift_long", trades, holding_window[1] - holding_window[0] + 1)


def run_cross_wrapper_strategy(
    events: pd.DataFrame,
    returns_panel: pd.DataFrame,
    *,
    holding_window: tuple[int, int] = (1, 30),
    lab_filter: str = "anthropic",
    wrapper_pair: tuple[str, str] = ("GOOGL", "AMZN"),
    exposures: dict[str, dict[str, dict[str, dict[int, float] | float]]] | None = None,
) -> BacktestSummary:
    """Pairs strategy: long the under-reacting wrapper, short the over-reacting one.

    For each event in the chosen lab, compute (expected - actual) announcement-day
    surprise per wrapper. Long the one with larger positive surprise (most
    underreaction), short the one with larger negative surprise. Hold for
    ``holding_window`` days. P&L = long_drift - short_drift.
    """
    expo = exposures or APPROXIMATE_EXPOSURES
    w1, w2 = wrapper_pair
    selected = events[
        (events["lab"].str.lower() == lab_filter.lower())
        & events["v_post_billion"].notna()
        & events["v_pre_billion"].notna()
        & events["event_type"].isin(["primary_round"])
    ].copy()

    trades: list[TradeRecord] = []
    for _, evt in selected.iterrows():
        lab = lab_filter.lower()
        delta_v = float(evt["v_post_billion"]) - float(evt["v_pre_billion"])
        event_date = pd.Timestamp(evt["announcement_date"]).date()
        year = event_date.year

        surprises: dict[str, dict[str, float]] = {}
        for wrapper in (w1, w2):
            lab_data = expo.get(wrapper, {}).get(lab)
            if not lab_data:
                continue
            stake_pct = lab_data["stake_pct"]
            cap_table = lab_data.get("market_cap_billion", {})
            if not isinstance(cap_table, dict) or not isinstance(stake_pct, int | float):
                continue
            mcap = float(cap_table.get(year, list(cap_table.values())[-1]))
            if mcap == 0:
                continue
            expected = compute_expected_return(float(stake_pct), delta_v, mcap)
            try:
                actual_announce = announcement_day_return(returns_panel[wrapper], event_date)
                drift = cumulative_return(
                    holding_window_returns(
                        returns_panel[wrapper],
                        event_date,
                        window_start=holding_window[0],
                        window_end=holding_window[1],
                    )
                )
            except KeyError, ValueError:
                continue
            surprises[wrapper] = {
                "expected": expected,
                "actual": actual_announce,
                "surprise": expected - actual_announce,
                "drift": drift,
                "stake_pct": float(stake_pct),
                "market_cap_billion": mcap,
            }
        if len(surprises) < 2:
            continue
        ranked = sorted(surprises.items(), key=lambda kv: kv[1]["surprise"], reverse=True)
        long_wrapper, long_data = ranked[0]
        short_wrapper, short_data = ranked[-1]
        if long_wrapper == short_wrapper:
            continue
        pair_pnl = long_data["drift"] - short_data["drift"]
        for wrapper, side, payload in (
            (long_wrapper, "long", long_data),
            (short_wrapper, "short", short_data),
        ):
            sign = 1.0 if side == "long" else -1.0
            trades.append(
                TradeRecord(
                    event_id=str(evt["event_id"]),
                    event_date=event_date,
                    lab=lab,
                    wrapper=wrapper,
                    direction=side,
                    expected_return_announce=payload["expected"],
                    actual_return_announce=payload["actual"],
                    holding_period_return=payload["drift"],
                    benchmark_return=0.0,
                    abnormal_return=sign * payload["drift"],
                    stake_pct=payload["stake_pct"],
                    market_cap_billion=payload["market_cap_billion"],
                    notes=f"pair_pnl={pair_pnl:.4f}",
                )
            )

    return _build_summary("cross_wrapper_pairs", trades, holding_window[1] - holding_window[0] + 1)


# ----------------------------------------------------------------------------
# Aggregate metrics
# ----------------------------------------------------------------------------
def aggregate_metrics(trades: list[TradeRecord], *, holding_days: int = 30) -> dict[str, float]:
    """Compute Sharpe / win-rate / drawdown / total P&L from a list of trades."""
    if not trades:
        return {
            "n_trades": 0,
            "mean_abnormal_return": 0.0,
            "median_abnormal_return": 0.0,
            "win_rate": 0.0,
            "sharpe_annualized": 0.0,
            "max_drawdown": 0.0,
            "total_pnl": 0.0,
        }
    ar = np.array([t.abnormal_return for t in trades], dtype=float)
    n = len(ar)
    mean = float(ar.mean())
    median = float(np.median(ar))
    std = float(ar.std(ddof=1)) if n > 1 else 0.0
    periods_per_year = 252.0 / max(holding_days, 1)
    sharpe = (mean / std) * np.sqrt(periods_per_year) if std > 0 else 0.0
    win_rate = float((ar > 0).sum() / n)
    cumulative = np.cumprod(1.0 + ar) - 1.0
    peak = np.maximum.accumulate(cumulative)
    drawdown = (cumulative - peak) / (1.0 + peak)
    max_dd = float(drawdown.min()) if len(drawdown) else 0.0
    total_pnl = float(cumulative[-1])
    return {
        "n_trades": float(n),
        "mean_abnormal_return": mean,
        "median_abnormal_return": median,
        "win_rate": win_rate,
        "sharpe_annualized": float(sharpe),
        "max_drawdown": max_dd,
        "total_pnl": total_pnl,
    }
