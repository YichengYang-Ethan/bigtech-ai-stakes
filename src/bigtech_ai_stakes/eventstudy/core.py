"""Event-study harness: market-model and Fama-French 3-factor abnormal returns.

Standard methodology (cf. Kurter & Bhatti 2024, SSRN 4912234):
- Estimation window default ``[-250, -11]`` trading days
- Event window default ``[-1, +1]``; ``[-5, +5]`` and ``[-10, +10]`` for robustness
- Asset-pricing model: market model or FF3
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Literal

import numpy as np
import pandas as pd
import statsmodels.api as sm

ModelType = Literal["market", "ff3"]


@dataclass(frozen=True)
class Event:
    """A single corporate event under study."""

    event_id: str
    ticker: str
    event_date: date
    event_type: str = ""
    label: str = ""


@dataclass(frozen=True)
class EventStudyConfig:
    """Estimation- and event-window configuration in trading-day offsets."""

    estimation_start: int = -250
    estimation_end: int = -11
    event_start: int = -1
    event_end: int = 1
    model: ModelType = "market"

    @property
    def estimation_length(self) -> int:
        return self.estimation_end - self.estimation_start + 1

    @property
    def event_length(self) -> int:
        return self.event_end - self.event_start + 1


@dataclass
class FittedModel:
    """Output of the estimation-window regression."""

    alpha: float
    coefficients: dict[str, float]
    rsquared: float
    n_obs: int
    residual_std: float


@dataclass
class EventStudyResult:
    """Per-event AR / CAR table and summary."""

    event: Event
    config: EventStudyConfig
    fitted: FittedModel
    daily: pd.DataFrame  # day_offset, date, actual, expected, abnormal
    car: float

    @property
    def car_t_stat(self) -> float:
        """t-statistic for CAR using estimation-window residual std."""
        if self.fitted.residual_std == 0.0:
            return 0.0
        denom = self.fitted.residual_std * np.sqrt(self.config.event_length)
        return float(self.car / denom)


def fit_market_model(asset: pd.Series, market: pd.Series) -> FittedModel:
    """OLS: ``asset_return = alpha + beta * market_return``."""
    df = pd.DataFrame({"asset": asset, "market": market}).dropna()
    x = sm.add_constant(df["market"].astype(float))
    y = df["asset"].astype(float)
    fit = sm.OLS(y, x).fit()
    return FittedModel(
        alpha=float(fit.params.iloc[0]),
        coefficients={"market": float(fit.params.iloc[1])},
        rsquared=float(fit.rsquared),
        n_obs=int(fit.nobs),
        residual_std=float(np.sqrt(fit.mse_resid)),
    )


def fit_ff3_model(asset_excess: pd.Series, factors: pd.DataFrame) -> FittedModel:
    """OLS: ``asset_excess = alpha + b1*MktRF + b2*SMB + b3*HML``."""
    df = factors[["mkt_rf", "smb", "hml"]].copy()
    df["y"] = asset_excess
    df = df.dropna()
    x = sm.add_constant(df[["mkt_rf", "smb", "hml"]].astype(float))
    y = df["y"].astype(float)
    fit = sm.OLS(y, x).fit()
    return FittedModel(
        alpha=float(fit.params.iloc[0]),
        coefficients={
            "mkt_rf": float(fit.params.iloc[1]),
            "smb": float(fit.params.iloc[2]),
            "hml": float(fit.params.iloc[3]),
        },
        rsquared=float(fit.rsquared),
        n_obs=int(fit.nobs),
        residual_std=float(np.sqrt(fit.mse_resid)),
    )


def _slice_offsets(returns: pd.DataFrame, event_idx: int, start: int, end: int) -> pd.DataFrame:
    lo = event_idx + start
    hi = event_idx + end + 1
    if lo < 0 or hi > len(returns):
        raise ValueError(
            f"window [{start}, {end}] out of range: event_idx={event_idx}, len={len(returns)}"
        )
    return returns.iloc[lo:hi].copy()


def _event_index(returns: pd.DataFrame, event_date: date) -> int:
    ts = pd.Timestamp(event_date)
    if ts not in returns.index:
        raise ValueError(f"event_date {event_date} not in returns index")
    loc = returns.index.get_loc(ts)
    if isinstance(loc, slice | np.ndarray):
        raise ValueError(f"event_date {event_date} matches multiple rows in returns index")
    return int(loc)


def run_event_study(
    event: Event,
    returns: pd.DataFrame,
    config: EventStudyConfig | None = None,
) -> EventStudyResult:
    """Run an event study for a single event.

    `returns` must be a DataFrame indexed by trading dates with columns:
      - ``asset`` — asset return series
      - For ``model='market'``: ``market``
      - For ``model='ff3'``: ``mkt_rf``, ``smb``, ``hml``, ``rf``
    """
    cfg = config or EventStudyConfig()
    event_idx = _event_index(returns, event.event_date)
    estimation = _slice_offsets(returns, event_idx, cfg.estimation_start, cfg.estimation_end)
    event_window = _slice_offsets(returns, event_idx, cfg.event_start, cfg.event_end)

    if cfg.model == "market":
        fitted = fit_market_model(estimation["asset"], estimation["market"])
        beta = fitted.coefficients["market"]
        expected = fitted.alpha + beta * event_window["market"]
    elif cfg.model == "ff3":
        excess = estimation["asset"] - estimation["rf"]
        fitted = fit_ff3_model(excess, estimation[["mkt_rf", "smb", "hml"]])
        b = fitted.coefficients
        expected_excess = (
            fitted.alpha
            + b["mkt_rf"] * event_window["mkt_rf"]
            + b["smb"] * event_window["smb"]
            + b["hml"] * event_window["hml"]
        )
        expected = expected_excess + event_window["rf"]
    else:
        raise ValueError(f"unknown model: {cfg.model}")

    abnormal = event_window["asset"] - expected
    daily = pd.DataFrame(
        {
            "day_offset": list(range(cfg.event_start, cfg.event_end + 1)),
            "date": event_window.index,
            "actual": event_window["asset"].to_numpy(),
            "expected": expected.to_numpy(),
            "abnormal": abnormal.to_numpy(),
        }
    )
    return EventStudyResult(
        event=event,
        config=cfg,
        fitted=fitted,
        daily=daily,
        car=float(abnormal.sum()),
    )


def caar(results: list[EventStudyResult]) -> dict[str, float]:
    """Cumulative average abnormal return across multiple events.

    Returns a dict with keys ``caar``, ``std``, ``n``, ``t_stat``.
    """
    if not results:
        return {"caar": 0.0, "std": 0.0, "n": 0.0, "t_stat": 0.0}
    cars = np.array([r.car for r in results])
    n = len(cars)
    mean = float(cars.mean())
    if n < 2:
        return {"caar": mean, "std": 0.0, "n": float(n), "t_stat": 0.0}
    std = float(cars.std(ddof=1))
    t_stat = mean / (std / np.sqrt(n)) if std > 0 else 0.0
    return {"caar": mean, "std": std, "n": float(n), "t_stat": float(t_stat)}
