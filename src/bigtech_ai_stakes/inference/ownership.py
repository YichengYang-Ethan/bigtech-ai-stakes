"""Ownership inference under ASC 321 measurement-alternative accounting.

Implements the canonical stake formula

    stake_q = (stake_{q-1} * V_pre + dC_q) / V_post

and a time-series builder that walks an investor's events forward from a
disclosed anchor (court filing, voluntary disclosure, or 10-Q figure).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Final

import pandas as pd
from pydantic import BaseModel

# Events that change the per-investor stake percentage on the announcement date.
DILUTIVE_EVENT_TYPES: Final[set[str]] = {
    "primary_round",
    "tender",  # tender offers can shift cap-table when net new primary issued
    "convertible_note",  # converts later, but record date for traceability
    "extension",  # extra capital injection
    "restructure",  # OpenAI Oct 2025 PBC re-org
}


class StakeInferenceError(ValueError):
    """Raised when stake inference inputs are invalid."""


@dataclass
class StakeAnchor:
    """A directly-disclosed stake snapshot used to seed inference."""

    investor_ticker: str
    lab: str
    snapshot_date: date
    stake_pct: float  # in percent (e.g., 14.0 for 14%)
    source: str  # short tag like "court_filing", "10-Q"
    notes: str = ""


@dataclass
class StakeStep:
    """A single forward-walked step in the inferred series."""

    investor_ticker: str
    lab: str
    snapshot_date: date
    stake_pct: float
    method: str  # "anchor", "diluted_no_participation", "participated", ...
    event_id: str | None = None
    notes: str = ""


class StakeSeries(BaseModel):
    """A walked-forward time series of an investor's stake in one lab."""

    investor_ticker: str
    lab: str
    steps: list[dict] = []  # list of StakeStep dicts for serialization

    def to_frame(self) -> pd.DataFrame:
        return pd.DataFrame(self.steps)


def infer_stake_after_round(
    stake_prev_pct: float,
    v_pre_billion: float,
    delta_c_billion: float,
    v_post_billion: float,
) -> float:
    """Apply stake = (stake_prev * V_pre + dC) / V_post and return new pct.

    All valuations in USD billions. `stake_prev_pct` is in percent (0-100).
    """
    if v_post_billion <= 0:
        raise StakeInferenceError(f"V_post must be positive, got {v_post_billion}")
    if v_pre_billion < 0:
        raise StakeInferenceError(f"V_pre must be non-negative, got {v_pre_billion}")
    if delta_c_billion < 0:
        raise StakeInferenceError(f"delta_C must be non-negative, got {delta_c_billion}")
    stake_prev_frac = stake_prev_pct / 100.0
    new_frac = (stake_prev_frac * v_pre_billion + delta_c_billion) / v_post_billion
    return new_frac * 100.0


def estimate_pro_rata_contribution(
    stake_prev_pct: float,
    v_pre_billion: float,
    v_post_billion: float,
) -> float:
    """Return the dC required to maintain stake_prev exactly through a round."""
    stake_frac = stake_prev_pct / 100.0
    raised = max(v_post_billion - v_pre_billion, 0.0)
    return stake_frac * raised


@dataclass
class _EventTriple:
    """Internal: an event normalized for the walker."""

    event_id: str
    lab: str
    announcement_date: date
    event_type: str
    v_pre: float | None
    v_post: float | None
    raise_amount: float | None
    delta_c_for_investor: float = 0.0
    notes: str = ""
    raw_row: dict = field(default_factory=dict)


def walk_forward(
    anchor: StakeAnchor,
    events: pd.DataFrame,
    *,
    investor_contributions: dict[str, float] | None = None,
) -> list[StakeStep]:
    """Walk an anchor stake forward through the given events.

    Parameters
    ----------
    anchor
        Disclosed stake at a known date.
    events
        DataFrame with columns matching `data/events/events.csv`. Rows where
        announcement_date <= anchor.snapshot_date are ignored.
    investor_contributions
        Optional mapping of `event_id` -> dC (USD billions) contributed by
        this investor at that event. Events not in this mapping are treated
        as zero contribution (pure dilution).
    """
    contributions = investor_contributions or {}
    relevant = (
        events[events["lab"].str.lower() == anchor.lab.lower()]
        .sort_values("announcement_date")
        .reset_index(drop=True)
    )
    relevant = relevant[
        pd.to_datetime(relevant["announcement_date"]) > pd.Timestamp(anchor.snapshot_date)
    ].reset_index(drop=True)

    steps: list[StakeStep] = [
        StakeStep(
            investor_ticker=anchor.investor_ticker,
            lab=anchor.lab,
            snapshot_date=anchor.snapshot_date,
            stake_pct=anchor.stake_pct,
            method="anchor",
            notes=f"source={anchor.source}; {anchor.notes}".strip(),
        )
    ]

    current_pct = anchor.stake_pct
    for _, row in relevant.iterrows():
        if row["event_type"] not in DILUTIVE_EVENT_TYPES:
            continue
        v_pre = _opt_float(row["v_pre_billion"])
        v_post = _opt_float(row["v_post_billion"])
        if v_pre is None or v_post is None or v_post <= 0:
            continue
        delta_c = float(contributions.get(row["event_id"], 0.0))
        new_pct = infer_stake_after_round(current_pct, v_pre, delta_c, v_post)
        method = "participated" if delta_c > 0 else "diluted_no_participation"
        evt_date = pd.Timestamp(row["announcement_date"]).date()
        steps.append(
            StakeStep(
                investor_ticker=anchor.investor_ticker,
                lab=anchor.lab,
                snapshot_date=evt_date,
                stake_pct=new_pct,
                method=method,
                event_id=str(row["event_id"]),
                notes=f"delta_c={delta_c} V_pre={v_pre} V_post={v_post}",
            )
        )
        current_pct = new_pct
    return steps


def steps_to_frame(steps: list[StakeStep]) -> pd.DataFrame:
    """Convert a list of StakeStep into a long-format DataFrame."""
    return pd.DataFrame(
        {
            "investor_ticker": [s.investor_ticker for s in steps],
            "lab": [s.lab for s in steps],
            "snapshot_date": [s.snapshot_date for s in steps],
            "stake_pct": [s.stake_pct for s in steps],
            "method": [s.method for s in steps],
            "event_id": [s.event_id for s in steps],
            "notes": [s.notes for s in steps],
        }
    )


def _opt_float(v: object) -> float | None:
    """Best-effort coercion to float, returning None for null / unparseable inputs."""
    if v is None:
        return None
    if isinstance(v, float) and pd.isna(v):
        return None
    if isinstance(v, int | float):
        return float(v)
    if isinstance(v, str):
        try:
            return float(v.strip())
        except ValueError:
            return None
    return None
