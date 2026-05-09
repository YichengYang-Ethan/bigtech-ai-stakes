"""Smoke tests for dashboard data helpers (Streamlit UI not exercised here)."""

from __future__ import annotations

from pathlib import Path

import pytest

from bigtech_ai_stakes.dashboard import (
    EXTRACTED_CSV,
    FIXTURES_CATALOG,
    FIXTURES_DIR,
    LOOKTHROUGH_PRESETS,
    LookthroughPreset,
    load_extracted,
    load_fixture,
)


class TestPaths:
    def test_extracted_csv_path_under_repo(self) -> None:
        assert isinstance(EXTRACTED_CSV, Path)
        assert EXTRACTED_CSV.name == "stakes_extracted.csv"

    def test_fixtures_dir_exists(self) -> None:
        assert FIXTURES_DIR.exists()


class TestLoadExtracted:
    def test_returns_dataframe(self) -> None:
        df = load_extracted()
        if not df.empty:
            for col in ("ticker", "form", "filing_date", "anchor_hit"):
                assert col in df.columns

    def test_filing_date_parsed_as_datetime(self) -> None:
        df = load_extracted()
        if df.empty:
            pytest.skip("stakes_extracted.csv missing on this machine")
        import pandas as pd

        assert pd.api.types.is_datetime64_any_dtype(df["filing_date"])


class TestLoadFixture:
    def test_each_catalog_entry_resolves(self) -> None:
        for filename in FIXTURES_CATALOG.values():
            text = load_fixture(filename)
            assert len(text) > 100
            # All fixtures contain at least one of the expected investee names
            assert any(name in text for name in ("OpenAI", "Anthropic", "non-marketable"))

    def test_missing_fixture_raises(self) -> None:
        with pytest.raises(FileNotFoundError):
            load_fixture("does_not_exist.txt")


class TestLookthroughPresets:
    def test_at_least_two_presets(self) -> None:
        assert len(LOOKTHROUGH_PRESETS) >= 2

    def test_each_preset_has_required_fields(self) -> None:
        for p in LOOKTHROUGH_PRESETS:
            assert isinstance(p, LookthroughPreset)
            assert p.label
            assert p.ticker
            assert p.quarter
            assert p.shares > 0

    def test_amzn_preset_has_pretax_gain(self) -> None:
        amzn = next((p for p in LOOKTHROUGH_PRESETS if p.ticker == "AMZN"), None)
        assert amzn is not None
        assert amzn.pretax_gain is not None
        assert amzn.pretax_gain > 0

    def test_googl_preset_uses_bottom_up(self) -> None:
        googl = next((p for p in LOOKTHROUGH_PRESETS if p.ticker == "GOOGL"), None)
        assert googl is not None
        assert googl.delta_v_post > 0
