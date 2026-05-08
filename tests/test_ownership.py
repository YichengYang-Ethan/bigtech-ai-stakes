"""Worked-example tests for the ownership-inference formula and walker."""

from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from bigtech_ai_stakes.data import load_events
from bigtech_ai_stakes.inference.ownership import (
    StakeAnchor,
    StakeInferenceError,
    estimate_pro_rata_contribution,
    infer_stake_after_round,
    steps_to_frame,
    walk_forward,
)


class TestInferStakeFormula:
    """stake_q = (stake_{q-1} * V_pre + dC) / V_post"""

    def test_pure_dilution_no_participation(self) -> None:
        # GOOGL 14% before Anthropic Series F (V_pre=170, V_post=183), no participation
        result = infer_stake_after_round(
            stake_prev_pct=14.0, v_pre_billion=170.0, delta_c_billion=0.0, v_post_billion=183.0
        )
        # (0.14 * 170) / 183 = 23.8 / 183 = 13.0055%
        assert result == pytest.approx(13.0055, abs=1e-3)

    def test_pro_rata_maintains_stake(self) -> None:
        # If investor contributes their pro-rata share, stake is unchanged
        v_pre, v_post = 170.0, 183.0
        stake_prev = 14.0
        delta_c = estimate_pro_rata_contribution(stake_prev, v_pre, v_post)
        result = infer_stake_after_round(stake_prev, v_pre, delta_c, v_post)
        assert result == pytest.approx(stake_prev, abs=1e-6)

    def test_above_pro_rata_increases_stake(self) -> None:
        # 10% holder contributes $5B in a Series G ($350B pre, $380B post)
        # = (0.10 * 350 + 5) / 380 = (35 + 5) / 380 = 10.526%
        result = infer_stake_after_round(10.0, 350.0, 5.0, 380.0)
        assert result == pytest.approx(10.5263, abs=1e-3)

    def test_brand_new_investor(self) -> None:
        # No prior stake, contributes $10B at $110B post-money
        result = infer_stake_after_round(0.0, 100.0, 10.0, 110.0)
        # 10/110 = 9.0909%
        assert result == pytest.approx(9.0909, abs=1e-3)

    def test_googl_anthropic_apr_2026_extension(self) -> None:
        # Hypothetical: 14% holder contributes $10B at $360B post-money
        # = (0.14 * 350 + 10) / 360 = (49 + 10) / 360 = 16.389%
        result = infer_stake_after_round(14.0, 350.0, 10.0, 360.0)
        assert result == pytest.approx(16.389, abs=1e-2)

    def test_negative_delta_c_rejected(self) -> None:
        with pytest.raises(StakeInferenceError):
            infer_stake_after_round(10.0, 100.0, -1.0, 110.0)

    def test_zero_v_post_rejected(self) -> None:
        with pytest.raises(StakeInferenceError):
            infer_stake_after_round(10.0, 100.0, 0.0, 0.0)


class TestProRataContribution:
    def test_zero_round_size_means_zero_contribution(self) -> None:
        assert estimate_pro_rata_contribution(14.0, 100.0, 100.0) == 0.0

    def test_normal_case(self) -> None:
        # 14% holder, V_pre=170, V_post=183, raised=13B
        # pro_rata = 0.14 * 13 = 1.82
        assert estimate_pro_rata_contribution(14.0, 170.0, 183.0) == pytest.approx(1.82)

    def test_negative_raised_clipped_to_zero(self) -> None:
        # Down-round: V_post < V_pre. Pro-rata is 0.
        assert estimate_pro_rata_contribution(14.0, 200.0, 180.0) == 0.0


class TestWalkForward:
    """End-to-end walks anchored at a disclosed stake."""

    def test_walk_googl_anthropic_from_court_filing(self) -> None:
        events = load_events()
        anchor = StakeAnchor(
            investor_ticker="GOOGL",
            lab="anthropic",
            snapshot_date=date(2025, 3, 15),
            stake_pct=14.0,
            source="court_filing",
        )
        steps = walk_forward(anchor, events)
        df = steps_to_frame(steps)

        # First step is the anchor itself
        assert df.iloc[0]["method"] == "anchor"
        assert df.iloc[0]["stake_pct"] == 14.0

        # Subsequent steps are dilutive primary rounds: F, G, etc.
        assert len(df) > 1
        # Final stake should be lower than 14% if GOOGL didn't participate in Series F/G
        # (the anchored 14% will dilute through Series F at $170B->$183B and G at $350B->$380B)
        final = df.iloc[-1]["stake_pct"]
        assert final < 14.0
        # Sanity: should be in a reasonable range (not negative, not > 14)
        assert 0.0 < final < 14.0

    def test_walk_msft_openai_with_participation(self) -> None:
        events = load_events()
        anchor = StakeAnchor(
            investor_ticker="MSFT",
            lab="openai",
            snapshot_date=date(2024, 1, 1),
            stake_pct=49.0,  # pre-restructure capped-profit interest, simplified
            source="approximate",
        )
        # Suppose MSFT contributed $1B at the Thrive round
        contributions = {"O_2024Q4_THRIVE_001": 1.0}
        steps = walk_forward(anchor, events, investor_contributions=contributions)
        df = steps_to_frame(steps)
        assert len(df) >= 1
        # Methods should be a mix of anchor / participated / diluted
        methods = set(df["method"])
        assert "anchor" in methods

    def test_walk_skips_events_before_anchor(self) -> None:
        events = load_events()
        anchor = StakeAnchor(
            investor_ticker="GOOGL",
            lab="anthropic",
            snapshot_date=date(2026, 12, 31),  # after every recorded event
            stake_pct=15.0,
            source="hypothetical",
        )
        steps = walk_forward(anchor, events)
        # Only the anchor row, no forward events
        assert len(steps) == 1
        assert steps[0].method == "anchor"

    def test_walk_skips_non_dilutive_event_types(self) -> None:
        events = pd.DataFrame(
            [
                {
                    "event_id": "TEST_COMMIT",
                    "lab": "anthropic",
                    "event_type": "commitment",
                    "announcement_date": pd.Timestamp("2025-06-01"),
                    "v_pre_billion": None,
                    "v_post_billion": None,
                    "raise_amount_billion": 1.0,
                    "lead_investors": "Test",
                    "key_strategic_investors": "Test",
                    "source_urls": "https://example.com",
                    "confidence": "P",
                    "notes": "",
                },
            ]
        )
        anchor = StakeAnchor(
            investor_ticker="TEST",
            lab="anthropic",
            snapshot_date=date(2025, 1, 1),
            stake_pct=10.0,
            source="test",
        )
        steps = walk_forward(anchor, events)
        # commitment events have no V_pre/V_post and shouldn't move the stake
        assert len(steps) == 1
