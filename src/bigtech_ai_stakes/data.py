"""Loaders for curated CSV datasets shipped under data/."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = REPO_ROOT / "data"
EVENTS_CSV = DATA_DIR / "events" / "events.csv"
STAKES_CSV = DATA_DIR / "stakes" / "stakes.csv"


def load_events(path: Path | None = None) -> pd.DataFrame:
    """Load the curated events CSV (primary funding rounds + Big Tech commitments).

    Returns
    -------
    pd.DataFrame
        Columns: event_id, lab, event_type, announcement_date,
        v_pre_billion, v_post_billion, raise_amount_billion, lead_investors,
        key_strategic_investors, source_urls, confidence, notes.
    """
    p = path or EVENTS_CSV
    return pd.read_csv(p, parse_dates=["announcement_date"])


def load_stakes(path: Path | None = None) -> pd.DataFrame:
    """Load the curated stakes CSV (point-in-time ownership snapshots).

    Returns
    -------
    pd.DataFrame
        Columns: investor_ticker, investor_name, lab, snapshot_date, stake_pct,
        stake_pct_method, fair_value_billion, cumulative_cost_basis_billion,
        source_urls, confidence, notes.
    """
    p = path or STAKES_CSV
    return pd.read_csv(p, parse_dates=["snapshot_date"])
