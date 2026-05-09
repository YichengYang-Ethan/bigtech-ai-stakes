"""Data loaders and presets for the Streamlit dashboard.

These helpers are deliberately Streamlit-free so they can be unit-tested
without invoking the Streamlit runtime.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from bigtech_ai_stakes.data import REPO_ROOT

EXTRACTED_CSV: Path = REPO_ROOT / "data" / "stakes_extracted.csv"
FIXTURES_DIR: Path = REPO_ROOT / "tests" / "fixtures"


def load_extracted() -> pd.DataFrame:
    """Load the machine-extracted stake panel.

    Returns an empty DataFrame if ``data/stakes_extracted.csv`` is missing
    (e.g., on a fresh clone before ``scripts/run_live_extraction.py`` has run).
    """
    if not EXTRACTED_CSV.exists():
        return pd.DataFrame()
    return pd.read_csv(EXTRACTED_CSV, parse_dates=["filing_date"])


def load_fixture(filename: str) -> str:
    """Read a footnote text fixture from ``tests/fixtures/``."""
    return (FIXTURES_DIR / filename).read_text(encoding="utf-8")


FIXTURES_CATALOG: dict[str, str] = {
    "GOOGL Q3 2024": "footnote_googl_q3_2024.txt",
    "MSFT Q3 FY26 (Oct 2025 transition)": "footnote_msft_q3_fy26.txt",
    "AMZN Q1 2026": "footnote_amzn_q1_2026.txt",
}


@dataclass(frozen=True)
class LookthroughPreset:
    """Pre-filled inputs for the look-through EPS calculator UI."""

    label: str
    ticker: str
    quarter: str
    gaap_ni: float
    shares: float
    stake_pct: float
    delta_v_post: float = 0.0
    investee_ni: float = 0.0
    pretax_gain: float | None = None


LOOKTHROUGH_PRESETS: list[LookthroughPreset] = [
    LookthroughPreset(
        label="Q1 2026 GOOGL / Anthropic (bottom-up)",
        ticker="GOOGL",
        quarter="2026Q1",
        gaap_ni=62.6,
        shares=12.5,
        stake_pct=12.0,
        delta_v_post=197.0,
        investee_ni=-3.0,
    ),
    LookthroughPreset(
        label="Q1 2026 AMZN / Anthropic (top-down)",
        ticker="AMZN",
        quarter="2026Q1",
        gaap_ni=17.1,
        shares=10.5,
        stake_pct=7.8,
        investee_ni=-3.0,
        pretax_gain=16.8,
    ),
]
