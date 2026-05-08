"""Look-through EPS tests with golden Q1 2026 numbers.

Inputs are drawn from the research report:
- Alphabet Q1 2026 GAAP NI ~$62.6B, ~$28.7B "net gains on equity securities"
  primarily attributable to Anthropic markups.
- Anthropic post-money valuation jumped from $183B (Series F, Sep 2025) to
  $380B (Series G, Feb 2026) → delta_V_post ~ $197B.
- Estimated GOOGL stake at start of Q1 2026: ~12% (post Series F dilution
  before Series G dilution; rough; refined in Stage 2 inference).
- Amazon Q1 2026 GAAP NI ~$17.1B, disclosed pre-tax gain $16.8B from Anthropic.
"""

from __future__ import annotations

import pytest

from bigtech_ai_stakes.lookthrough.core import (
    LookThroughInputs,
    Scenario,
    default_scenarios,
    evaluate_scenarios,
    look_through,
    look_through_bottom_up,
    look_through_top_down,
)


class TestBottomUpFormula:
    def test_zero_stake_no_change(self) -> None:
        inputs = LookThroughInputs(
            issuer_ticker="X",
            quarter="2026Q1",
            gaap_net_income_billion=10.0,
            shares_outstanding_billion=1.0,
            stake_pct=0.0,
            delta_v_post_billion=100.0,
        )
        r = look_through_bottom_up(inputs)
        assert r.look_through_net_income_billion == pytest.approx(10.0)
        assert r.look_through_eps == pytest.approx(10.0)

    def test_googl_q1_2026_bottom_up(self) -> None:
        # 12% * 197 = 23.64B markup share; with -3B Anthropic NI: 12% * -3 = -0.36B
        # LT_NI = 62.6 - 23.64 + (-0.36) = 38.6B
        # LT_EPS = 38.6 / 12.5 = ~3.088
        inputs = LookThroughInputs(
            issuer_ticker="GOOGL",
            quarter="2026Q1",
            gaap_net_income_billion=62.6,
            shares_outstanding_billion=12.5,
            stake_pct=12.0,
            delta_v_post_billion=197.0,
            investee_net_income_billion=-3.0,
        )
        r = look_through_bottom_up(inputs)
        assert r.look_through_net_income_billion == pytest.approx(38.6, abs=0.05)
        assert r.look_through_eps == pytest.approx(3.088, abs=0.005)
        assert r.gaap_eps == pytest.approx(5.008, abs=0.005)
        assert r.method == "bottom_up"

    def test_pro_rata_at_zero_change_is_identity(self) -> None:
        inputs = LookThroughInputs(
            issuer_ticker="X",
            quarter="2026Q1",
            gaap_net_income_billion=50.0,
            shares_outstanding_billion=10.0,
            stake_pct=20.0,
            delta_v_post_billion=0.0,
            investee_net_income_billion=0.0,
        )
        r = look_through_bottom_up(inputs)
        assert r.look_through_net_income_billion == pytest.approx(50.0)


class TestTopDownFormula:
    def test_amzn_q1_2026_top_down(self) -> None:
        # Amazon disclosed $16.8B pre-tax gain in Q1 2026
        # After-tax (21%): 16.8 * 0.79 = 13.272
        # Assume Q1 GAAP NI ~17.1B (illustrative)
        # LT_NI = 17.1 - 13.272 + 0.078 * -3 = 17.1 - 13.272 - 0.234 = 3.594B
        inputs = LookThroughInputs(
            issuer_ticker="AMZN",
            quarter="2026Q1",
            gaap_net_income_billion=17.1,
            shares_outstanding_billion=10.5,
            stake_pct=7.8,
            disclosed_pretax_gain_billion=16.8,
            investee_net_income_billion=-3.0,
            tax_rate=0.21,
        )
        r = look_through_top_down(inputs)
        # 16.8 * 0.79 = 13.272; investee_share = 0.078 * -3 = -0.234
        # lt_ni = 17.1 - 13.272 + (-0.234) = 3.594
        assert r.look_through_net_income_billion == pytest.approx(3.594, abs=0.05)
        assert r.method == "top_down"
        # GAAP EPS ~ 17.1 / 10.5 ~= 1.629
        assert r.gaap_eps == pytest.approx(1.629, abs=0.005)
        # LT EPS ~ 3.594 / 10.5 ~= 0.342
        assert r.look_through_eps == pytest.approx(0.342, abs=0.005)

    def test_top_down_requires_disclosed_gain(self) -> None:
        inputs = LookThroughInputs(
            issuer_ticker="X",
            quarter="2026Q1",
            gaap_net_income_billion=10.0,
            shares_outstanding_billion=1.0,
            stake_pct=10.0,
            delta_v_post_billion=100.0,  # bottom-up data only
        )
        with pytest.raises(ValueError):
            look_through_top_down(inputs)


class TestDispatch:
    def test_auto_picks_top_down_when_gain_present(self) -> None:
        inputs = LookThroughInputs(
            issuer_ticker="AMZN",
            quarter="2026Q1",
            gaap_net_income_billion=17.1,
            shares_outstanding_billion=10.5,
            stake_pct=7.8,
            disclosed_pretax_gain_billion=16.8,
            investee_net_income_billion=-3.0,
        )
        r = look_through(inputs)
        assert r.method == "top_down"

    def test_auto_picks_bottom_up_when_only_delta_v(self) -> None:
        inputs = LookThroughInputs(
            issuer_ticker="GOOGL",
            quarter="2026Q1",
            gaap_net_income_billion=62.6,
            shares_outstanding_billion=12.5,
            stake_pct=12.0,
            delta_v_post_billion=197.0,
        )
        r = look_through(inputs)
        assert r.method == "bottom_up"


class TestScenarios:
    def test_default_scenarios_have_three(self) -> None:
        scenarios = default_scenarios()
        names = [s.name for s in scenarios]
        assert names == ["bear", "base", "bull"]

    def test_evaluate_scenarios_returns_three_results(self) -> None:
        base = LookThroughInputs(
            issuer_ticker="GOOGL",
            quarter="2026Q1",
            gaap_net_income_billion=62.6,
            shares_outstanding_billion=12.5,
            stake_pct=12.0,
            delta_v_post_billion=197.0,
        )
        results = evaluate_scenarios(base, default_scenarios())
        assert len(results) == 3
        # bear NI < base NI < bull NI in look-through (because investee NI flows through stake)
        bear, base_r, bull = results
        assert bear.look_through_net_income_billion < base_r.look_through_net_income_billion
        assert base_r.look_through_net_income_billion < bull.look_through_net_income_billion

    def test_custom_scenario(self) -> None:
        base = LookThroughInputs(
            issuer_ticker="X",
            quarter="2026Q1",
            gaap_net_income_billion=10.0,
            shares_outstanding_billion=1.0,
            stake_pct=10.0,
            delta_v_post_billion=0.0,
        )
        s = [Scenario(name="base", investee_net_income_billion=5.0)]
        results = evaluate_scenarios(base, s)
        # 10 + 0.10 * 5 = 10.5
        assert results[0].look_through_net_income_billion == pytest.approx(10.5)


class TestResultProperties:
    def test_eps_drag_is_positive_for_typical_markup(self) -> None:
        inputs = LookThroughInputs(
            issuer_ticker="GOOGL",
            quarter="2026Q1",
            gaap_net_income_billion=62.6,
            shares_outstanding_billion=12.5,
            stake_pct=12.0,
            delta_v_post_billion=197.0,
            investee_net_income_billion=-3.0,
        )
        r = look_through_bottom_up(inputs)
        # 0.12 * 197 - 0.12 * -3 = 23.64 + 0.36 = 24.0
        assert r.eps_drag_billion == pytest.approx(24.0, abs=0.05)
