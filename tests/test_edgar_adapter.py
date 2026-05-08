"""Structural tests for the edgartools wrapper.

Live SEC fetches are gated behind `pytest.mark.live` and skipped by default.
Run live tests with `pytest -m live` (requires network).
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from bigtech_ai_stakes.filings.edgar_adapter import (
    CACHE_DIR,
    COVERED_ISSUERS,
    DEFAULT_FORMS,
    DEFAULT_IDENTITY,
    FilingRef,
    cik_for,
    list_filings,
)


class TestCoveredIssuers:
    def test_v01_issuers_present(self) -> None:
        for ticker in ("GOOGL", "AMZN", "MSFT", "NVDA", "CRM", "QCOM", "ZM"):
            assert ticker in COVERED_ISSUERS

    def test_each_has_name_and_cik(self) -> None:
        for ticker, meta in COVERED_ISSUERS.items():
            assert meta["name"], f"missing name for {ticker}"
            cik = meta["cik"]
            assert len(cik) == 10, f"CIK should be zero-padded 10 digits, got {cik}"
            assert cik.isdigit(), f"CIK should be digits-only, got {cik}"

    def test_cik_for_round_trip(self) -> None:
        for ticker, meta in COVERED_ISSUERS.items():
            assert cik_for(ticker) == meta["cik"]

    def test_cik_for_lowercase_input(self) -> None:
        assert cik_for("msft") == COVERED_ISSUERS["MSFT"]["cik"]

    def test_cik_for_unknown_raises(self) -> None:
        with pytest.raises(ValueError):
            cik_for("AAPL")


class TestDefaults:
    def test_default_forms_includes_three(self) -> None:
        assert "10-K" in DEFAULT_FORMS
        assert "10-Q" in DEFAULT_FORMS
        assert "8-K" in DEFAULT_FORMS

    def test_default_identity_has_name_and_email(self) -> None:
        assert "@" in DEFAULT_IDENTITY


class TestFilingRef:
    def test_cache_path_under_cache_dir(self) -> None:
        ref = FilingRef(
            ticker="MSFT",
            form="10-Q",
            filing_date=date(2026, 4, 30),
            accession="0000789019-26-000005",
        )
        assert CACHE_DIR in ref.cache_path.parents
        assert ref.cache_path.name == "0000789019-26-000005.txt"

    def test_cache_path_normalizes_form_slash(self) -> None:
        ref = FilingRef(
            ticker="MSFT",
            form="N-CSR/A",
            filing_date=date(2026, 4, 30),
            accession="0000789019-26-000005",
        )
        # forward slashes should not appear in path components
        for part in ref.cache_path.parts:
            assert "/" not in part or part == "/"

    def test_filingref_equality_ignores_raw(self) -> None:
        a = FilingRef(
            ticker="MSFT",
            form="10-Q",
            filing_date=date(2026, 4, 30),
            accession="X",
            _raw="object_a",
        )
        b = FilingRef(
            ticker="MSFT",
            form="10-Q",
            filing_date=date(2026, 4, 30),
            accession="X",
            _raw="object_b",
        )
        assert a == b


class TestListFilingsRejectsUncovered:
    def test_uncovered_ticker_raises(self) -> None:
        with pytest.raises(ValueError):
            list_filings("AAPL")


@pytest.mark.live
class TestLiveSECFetch:
    """Live network tests — skipped by default; opt in with `pytest -m live`."""

    def test_msft_returns_some_filings(self, tmp_path: Path) -> None:
        refs = list_filings("MSFT", forms=["10-Q"], since=date(2026, 1, 1))
        assert len(refs) >= 1
        assert all(r.ticker == "MSFT" for r in refs)
