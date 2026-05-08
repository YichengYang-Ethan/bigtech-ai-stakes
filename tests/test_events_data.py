"""Schema and integrity checks on data/events/events.csv."""

from __future__ import annotations

import pandas as pd
import pytest

from bigtech_ai_stakes.data import load_events

EXPECTED_COLUMNS = [
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
ALLOWED_LABS = {"anthropic", "openai"}
ALLOWED_CONFIDENCE = {"V", "P", "S"}
ALLOWED_EVENT_TYPES = {
    "primary_round",
    "convertible_note",
    "tender",
    "commitment",
    "restructure",
    "extension",
}


@pytest.fixture
def events() -> pd.DataFrame:
    return load_events()


def test_expected_columns(events: pd.DataFrame) -> None:
    assert list(events.columns) == EXPECTED_COLUMNS


def test_min_row_count(events: pd.DataFrame) -> None:
    assert len(events) >= 15, f"expected >=15 events at v0.1, got {len(events)}"


def test_event_id_unique(events: pd.DataFrame) -> None:
    assert events["event_id"].is_unique


def test_lab_values(events: pd.DataFrame) -> None:
    bad = set(events["lab"].str.lower()) - ALLOWED_LABS
    assert not bad, f"unknown lab values: {bad}"


def test_confidence_values(events: pd.DataFrame) -> None:
    bad = set(events["confidence"]) - ALLOWED_CONFIDENCE
    assert not bad, f"unknown confidence values: {bad}"


def test_event_type_values(events: pd.DataFrame) -> None:
    bad = set(events["event_type"]) - ALLOWED_EVENT_TYPES
    assert not bad, f"unknown event_type values: {bad}"


def test_v_post_positive_when_present(events: pd.DataFrame) -> None:
    populated = events.dropna(subset=["v_post_billion"])
    assert (populated["v_post_billion"] > 0).all()


def test_announcement_dates_are_dates(events: pd.DataFrame) -> None:
    assert pd.api.types.is_datetime64_any_dtype(events["announcement_date"])


def test_v_rows_have_source_urls(events: pd.DataFrame) -> None:
    """Every confidence=V row must cite at least one source URL."""
    v_rows = events[events["confidence"] == "V"]
    missing = v_rows[
        v_rows["source_urls"].isna() | (v_rows["source_urls"].astype(str).str.strip() == "")
    ]
    assert len(missing) == 0, f"V rows missing source_urls: {missing['event_id'].tolist()}"


def test_both_labs_represented(events: pd.DataFrame) -> None:
    labs = set(events["lab"].str.lower())
    assert ALLOWED_LABS.issubset(labs), f"missing labs: {ALLOWED_LABS - labs}"
