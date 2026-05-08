"""Schema and integrity checks on data/stakes/stakes.csv."""

from __future__ import annotations

import pandas as pd
import pytest

from bigtech_ai_stakes.data import load_stakes

EXPECTED_COLUMNS = [
    "investor_ticker",
    "investor_name",
    "lab",
    "snapshot_date",
    "stake_pct",
    "stake_pct_method",
    "fair_value_billion",
    "cumulative_cost_basis_billion",
    "source_urls",
    "confidence",
    "notes",
]
ALLOWED_LABS = {"anthropic", "openai"}
ALLOWED_CONFIDENCE = {"V", "P", "S"}


@pytest.fixture
def stakes() -> pd.DataFrame:
    return load_stakes()


def test_expected_columns(stakes: pd.DataFrame) -> None:
    assert list(stakes.columns) == EXPECTED_COLUMNS


def test_min_row_count(stakes: pd.DataFrame) -> None:
    assert len(stakes) >= 5


def test_lab_values(stakes: pd.DataFrame) -> None:
    bad = set(stakes["lab"].str.lower()) - ALLOWED_LABS
    assert not bad


def test_confidence_values(stakes: pd.DataFrame) -> None:
    bad = set(stakes["confidence"]) - ALLOWED_CONFIDENCE
    assert not bad


def test_stake_pct_in_range(stakes: pd.DataFrame) -> None:
    populated = stakes.dropna(subset=["stake_pct"])
    assert ((populated["stake_pct"] > 0) & (populated["stake_pct"] < 100)).all()


def test_v_rows_have_source_urls(stakes: pd.DataFrame) -> None:
    v_rows = stakes[stakes["confidence"] == "V"]
    missing = v_rows[
        v_rows["source_urls"].isna() | (v_rows["source_urls"].astype(str).str.strip() == "")
    ]
    assert len(missing) == 0
