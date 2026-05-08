"""Tests for the 7-criterion disclosure-quality rubric.

Scores the three Stage-1 fixtures (GOOGL Q3 2024, MSFT Q3 FY26, AMZN Q1 2026)
and verifies the relative ordering matches the manual baseline in
docs/disclosure-rubric.md.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from bigtech_ai_stakes.disclosure.core import (
    CriterionResult,
    DisclosureScore,
    compare_issuers,
    score_disclosure,
)
from bigtech_ai_stakes.disclosure.rubric import CRITERIA, MAX_SCORE

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def googl_text() -> str:
    return (FIXTURES / "footnote_googl_q3_2024.txt").read_text(encoding="utf-8")


@pytest.fixture
def msft_text() -> str:
    return (FIXTURES / "footnote_msft_q3_fy26.txt").read_text(encoding="utf-8")


@pytest.fixture
def amzn_text() -> str:
    return (FIXTURES / "footnote_amzn_q1_2026.txt").read_text(encoding="utf-8")


class TestRubricStructure:
    def test_seven_criteria(self) -> None:
        assert len(CRITERIA) == 7
        assert MAX_SCORE == 7.0

    def test_criterion_names_unique(self) -> None:
        names = [name for name, _ in CRITERIA]
        assert len(set(names)) == 7


class TestScoreShape:
    def test_score_returns_seven_results(self, msft_text: str) -> None:
        result = score_disclosure(msft_text, issuer="MSFT", accession="X")
        assert isinstance(result, DisclosureScore)
        assert len(result.criteria) == 7
        for c in result.criteria:
            assert isinstance(c, CriterionResult)
            assert c.score in (0.0, 0.5, 1.0)
            assert c.evidence

    def test_total_in_range(self, msft_text: str) -> None:
        r = score_disclosure(msft_text)
        assert 0.0 <= r.total <= MAX_SCORE

    def test_to_dict_has_all_criterion_columns(self, msft_text: str) -> None:
        r = score_disclosure(msft_text, issuer="MSFT")
        d = r.to_dict()
        for name, _ in CRITERIA:
            assert name in d
        assert d["issuer"] == "MSFT"
        assert "total" in d


class TestPerIssuerScores:
    def test_msft_names_openai_and_discloses_stake(self, msft_text: str) -> None:
        r = score_disclosure(msft_text, issuer="MSFT")
        scores_by_name = {c.name: c.score for c in r.criteria}
        assert scores_by_name["investee_named"] == 1.0
        assert scores_by_name["stake_disclosed"] == 1.0
        # MSFT mentions only "equity method" — single method, partial credit
        assert scores_by_name["method_disclosed"] == 0.5

    def test_amzn_names_anthropic_no_stake(self, amzn_text: str) -> None:
        r = score_disclosure(amzn_text, issuer="AMZN")
        scores_by_name = {c.name: c.score for c in r.criteria}
        assert scores_by_name["investee_named"] == 1.0
        assert scores_by_name["stake_disclosed"] == 0.0

    def test_googl_no_investee_named_but_methods_disclosed(self, googl_text: str) -> None:
        r = score_disclosure(googl_text, issuer="GOOGL")
        scores_by_name = {c.name: c.score for c in r.criteria}
        # Alphabet uses "primarily one investee" — does NOT name Anthropic
        assert scores_by_name["investee_named"] == 0.0
        # 3 valuation methods named → full credit
        assert scores_by_name["method_disclosed"] == 1.0
        # Quarterly gain/loss breakout: $35.4B of gains and $2.5B of losses
        assert scores_by_name["quarterly_breakout"] == 1.0
        # "primarily one investee" → concentration
        assert scores_by_name["concentration"] == 1.0


class TestNoIssuerScoresPerfect:
    """Universal weakness check: no issuer in v0.1 should score 7/7.

    In particular, criterion 4 (sensitivity to V_post) is currently zero for
    all issuers, which is the main publishable finding from this rubric.
    """

    def test_no_issuer_scores_full(self, googl_text: str, msft_text: str, amzn_text: str) -> None:
        for text in (googl_text, msft_text, amzn_text):
            r = score_disclosure(text)
            assert r.total < MAX_SCORE

    def test_sensitivity_is_universally_zero(
        self, googl_text: str, msft_text: str, amzn_text: str
    ) -> None:
        for text in (googl_text, msft_text, amzn_text):
            r = score_disclosure(text)
            scores_by_name = {c.name: c.score for c in r.criteria}
            assert scores_by_name["sensitivity_to_v_post"] == 0.0


class TestRelativeOrdering:
    """Ordering predicted in docs/disclosure-rubric.md baseline."""

    def test_googl_total_ge_2(self, googl_text: str, msft_text: str, amzn_text: str) -> None:
        # GOOGL: methods (1.0) + quarterly breakout (1.0) + concentration (1.0) = 3.0
        # AMZN: only investee_named (1.0)
        googl = score_disclosure(googl_text).total
        amzn = score_disclosure(amzn_text).total
        msft = score_disclosure(msft_text).total
        assert googl >= 2.0
        # Both MSFT and GOOGL should beat AMZN in v0.1
        assert msft >= amzn
        assert googl >= amzn


class TestCompareIssuers:
    def test_compare_returns_sorted_frame(
        self, googl_text: str, msft_text: str, amzn_text: str
    ) -> None:
        df = compare_issuers({"GOOGL": googl_text, "MSFT": msft_text, "AMZN": amzn_text})
        assert len(df) == 3
        # frame is sorted descending by total
        assert df["total"].is_monotonic_decreasing
        # all 7 criterion columns present
        for name, _ in CRITERIA:
            assert name in df.columns

    def test_total_pct_is_fraction(self, msft_text: str) -> None:
        r = score_disclosure(msft_text)
        assert 0.0 <= r.total_pct <= 1.0
        assert r.total_pct == pytest.approx(r.total / MAX_SCORE)
