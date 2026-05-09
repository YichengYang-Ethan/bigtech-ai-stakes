"""yfinance loader for backtests, with on-disk parquet cache.

Separated from :mod:`backtest.core` so that core unit tests do not import
yfinance and CI runs without network access. The cache is gitignored under
``data/returns_cache.parquet``.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

from bigtech_ai_stakes.data import REPO_ROOT

DEFAULT_CACHE_PATH: Path = REPO_ROOT / "data" / "returns_cache.parquet"


def load_returns(
    tickers: Sequence[str],
    start: date,
    end: date,
    *,
    cache_path: Path | None = None,
    use_cache: bool = True,
    force_refresh: bool = False,
) -> pd.DataFrame:
    """Return daily simple returns indexed by trading date.

    Columns are the input tickers. Uses adjusted close (yfinance ``auto_adjust=True``)
    so dividends and splits are handled. Caches to parquet on first fetch.

    Parameters
    ----------
    tickers
        Equity symbols recognized by yfinance (e.g., ``["GOOGL", "AMZN", "SPY"]``).
    start, end
        Inclusive date range.
    cache_path
        Override the default ``data/returns_cache.parquet`` location.
    use_cache
        If True (default), load from cache when it covers the requested range.
    force_refresh
        Force a fresh yfinance fetch even if the cache covers the range.
    """
    cache = cache_path or DEFAULT_CACHE_PATH
    if use_cache and not force_refresh and cache.exists():
        cached = pd.read_parquet(cache)
        if _cache_covers(cached, tickers, start, end):
            return _slice_returns(cached, tickers, start, end)

    import yfinance as yf

    raw = yf.download(
        list(tickers),
        start=start.isoformat(),
        end=(end + timedelta(days=1)).isoformat(),
        auto_adjust=True,
        progress=False,
    )
    closes = raw["Close"] if isinstance(raw.columns, pd.MultiIndex) else raw[["Close"]]
    if isinstance(closes, pd.Series):
        closes = closes.to_frame(name=tickers[0])
    closes = closes.dropna(how="all").sort_index()
    returns = closes.pct_change().dropna(how="all")

    if use_cache:
        cache.parent.mkdir(parents=True, exist_ok=True)
        # Merge with any existing cache so we accumulate coverage across runs.
        if cache.exists() and not force_refresh:
            try:
                old = pd.read_parquet(cache)
                merged = old.combine_first(returns).sort_index()
            except Exception:
                merged = returns
        else:
            merged = returns
        merged.to_parquet(cache)
    return _slice_returns(returns, tickers, start, end)


def _cache_covers(cached: pd.DataFrame, tickers: Sequence[str], start: date, end: date) -> bool:
    if not all(t in cached.columns for t in tickers):
        return False
    if cached.empty:
        return False
    first, last = cached.index.min(), cached.index.max()
    return first.date() <= start and last.date() >= end


def _slice_returns(
    df: pd.DataFrame, tickers: Sequence[str], start: date, end: date
) -> pd.DataFrame:
    cols = [t for t in tickers if t in df.columns]
    sliced = df.loc[
        (df.index >= pd.Timestamp(start)) & (df.index <= pd.Timestamp(end)),
        cols,
    ]
    return sliced.copy()
