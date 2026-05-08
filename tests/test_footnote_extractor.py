"""Tests for ASC 321 / 323 footnote field extraction.

Fixtures live in tests/fixtures/ and reproduce the disclosure language quoted
in the research report.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from bigtech_ai_stakes.filings.footnote_extractor import (
    FootnoteExtraction,
    extract_all,
    extract_carrying_value,
    extract_cumulative_gains,
    extract_cumulative_losses,
    extract_funded_to_date,
    extract_funding_commitment,
    extract_investees,
    extract_pretax_gain_quarter,
    extract_stake_pct,
    extract_valuation_methods,
)

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def googl_q3_2024() -> str:
    return (FIXTURES / "footnote_googl_q3_2024.txt").read_text(encoding="utf-8")


@pytest.fixture
def msft_q3_fy26() -> str:
    return (FIXTURES / "footnote_msft_q3_fy26.txt").read_text(encoding="utf-8")


@pytest.fixture
def amzn_q1_2026() -> str:
    return (FIXTURES / "footnote_amzn_q1_2026.txt").read_text(encoding="utf-8")


class TestGOOGLFootnote:
    def test_carrying_value_33_7_billion(self, googl_q3_2024: str) -> None:
        assert extract_carrying_value(googl_q3_2024) == pytest.approx(33.7)

    def test_cumulative_gains_35_4_billion(self, googl_q3_2024: str) -> None:
        assert extract_cumulative_gains(googl_q3_2024) == pytest.approx(35.4)

    def test_cumulative_losses_2_5_billion(self, googl_q3_2024: str) -> None:
        assert extract_cumulative_losses(googl_q3_2024) == pytest.approx(2.5)

    def test_googl_does_not_name_anthropic(self, googl_q3_2024: str) -> None:
        # Alphabet uses 'primarily one investee' rather than naming Anthropic
        assert extract_investees(googl_q3_2024) == []

    def test_googl_methods_disclosed(self, googl_q3_2024: str) -> None:
        methods = extract_valuation_methods(googl_q3_2024)
        assert "option_pricing" in methods
        assert "market_comparable" in methods
        assert "common_stock_equivalent" in methods


class TestMSFTFootnote:
    def test_msft_names_openai(self, msft_q3_fy26: str) -> None:
        assert "OpenAI" in extract_investees(msft_q3_fy26)

    def test_funding_commitment_13_billion(self, msft_q3_fy26: str) -> None:
        assert extract_funding_commitment(msft_q3_fy26) == pytest.approx(13.0)

    def test_funded_to_date_11_8_billion(self, msft_q3_fy26: str) -> None:
        assert extract_funded_to_date(msft_q3_fy26) == pytest.approx(11.8)

    def test_stake_26_79_pct(self, msft_q3_fy26: str) -> None:
        assert extract_stake_pct(msft_q3_fy26) == pytest.approx(26.79)

    def test_msft_uses_equity_method(self, msft_q3_fy26: str) -> None:
        methods = extract_valuation_methods(msft_q3_fy26)
        assert "equity_method" in methods


class TestAMZNFootnote:
    def test_amzn_names_anthropic(self, amzn_q1_2026: str) -> None:
        assert "Anthropic" in extract_investees(amzn_q1_2026)

    def test_pretax_gain_16_8_billion(self, amzn_q1_2026: str) -> None:
        assert extract_pretax_gain_quarter(amzn_q1_2026) == pytest.approx(16.8)


class TestExtractAll:
    def test_extract_all_returns_typed_result(self, msft_q3_fy26: str) -> None:
        result = extract_all(msft_q3_fy26)
        assert isinstance(result, FootnoteExtraction)
        assert result.has_data
        assert result.stake_pct == pytest.approx(26.79)
        assert "OpenAI" in result.investees
        assert result.funding_commitment_billion == pytest.approx(13.0)
        assert "equity_method" in result.valuation_methods
        assert len(result.excerpt) > 0

    def test_empty_text_returns_empty_extraction(self) -> None:
        result = extract_all("")
        assert not result.has_data
        assert result.investees == []
        assert result.carrying_value_billion is None

    def test_extract_all_googl_has_carrying_value_no_investees(self, googl_q3_2024: str) -> None:
        result = extract_all(googl_q3_2024)
        assert result.has_data
        assert result.carrying_value_billion == pytest.approx(33.7)
        assert result.investees == []  # GOOGL doesn't name them
