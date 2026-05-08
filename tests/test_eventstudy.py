"""Tests for the event-study harness using synthetic data.

Synthetic returns follow a known FF3 data-generating process so we can
inject a known abnormal return and verify it is recovered by the harness.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from bigtech_ai_stakes.eventstudy.core import (
    Event,
    EventStudyConfig,
    caar,
    fit_ff3_model,
    fit_market_model,
    run_event_study,
)
from bigtech_ai_stakes.eventstudy.factors import (
    load_ff3_from_csv,
    market_return_from_factors,
    synthetic_asset_returns,
    synthetic_factors,
)

FIXTURES = Path(__file__).parent / "fixtures"


def _inject_ar(panel: pd.DataFrame, event_idx: int, ar: float) -> None:
    """Add ``ar`` to the 'asset' column at row ``event_idx`` (mypy-clean)."""
    event_date = panel.index[event_idx]
    current = float(panel.loc[event_date, "asset"])
    panel.loc[event_date, "asset"] = current + ar


def _make_clean_panel(
    n_days: int = 300,
    *,
    alpha: float = 0.0,
    beta_mkt: float = 1.2,
    beta_smb: float = 0.3,
    beta_hml: float = 0.0,
    seed: int = 7,
) -> pd.DataFrame:
    """Generate a panel of synthetic returns + factors, no abnormal injection."""
    dates = pd.bdate_range("2024-01-02", periods=n_days)
    factors = synthetic_factors(dates, seed=seed)
    asset = synthetic_asset_returns(
        factors,
        alpha=alpha,
        beta_mkt=beta_mkt,
        beta_smb=beta_smb,
        beta_hml=beta_hml,
        seed=seed + 100,
    )
    market = market_return_from_factors(factors)
    return pd.DataFrame(
        {
            "asset": asset,
            "market": market,
            "mkt_rf": factors["mkt_rf"],
            "smb": factors["smb"],
            "hml": factors["hml"],
            "rf": factors["rf"],
        },
        index=dates,
    )


class TestMarketModelFit:
    def test_recovers_known_beta(self) -> None:
        panel = _make_clean_panel(n_days=500, beta_mkt=1.5, beta_smb=0.0, beta_hml=0.0)
        fitted = fit_market_model(panel["asset"], panel["market"])
        assert fitted.coefficients["market"] == pytest.approx(1.5, abs=0.1)
        assert fitted.n_obs == 500

    def test_unit_beta_returns_around_one(self) -> None:
        panel = _make_clean_panel(beta_mkt=1.0, beta_smb=0.0, beta_hml=0.0)
        fitted = fit_market_model(panel["asset"], panel["market"])
        assert abs(fitted.coefficients["market"] - 1.0) < 0.15


class TestFF3Fit:
    def test_recovers_three_betas(self) -> None:
        panel = _make_clean_panel(n_days=500, beta_mkt=1.4, beta_smb=0.5, beta_hml=-0.2)
        excess = panel["asset"] - panel["rf"]
        fitted = fit_ff3_model(excess, panel[["mkt_rf", "smb", "hml"]])
        assert fitted.coefficients["mkt_rf"] == pytest.approx(1.4, abs=0.15)
        assert fitted.coefficients["smb"] == pytest.approx(0.5, abs=0.15)
        assert fitted.coefficients["hml"] == pytest.approx(-0.2, abs=0.15)


class TestRunEventStudyMarketModel:
    def test_recovers_injected_abnormal_return(self) -> None:
        panel = _make_clean_panel(n_days=300, beta_mkt=1.2)
        injected_ar = 0.025
        event_idx = 260
        _inject_ar(panel, event_idx, injected_ar)

        event = Event(event_id="T1", ticker="TST", event_date=panel.index[event_idx].date())
        cfg = EventStudyConfig(
            estimation_start=-250,
            estimation_end=-11,
            event_start=0,
            event_end=0,
            model="market",
        )
        result = run_event_study(event, panel, cfg)
        assert result.daily["abnormal"].iloc[0] == pytest.approx(injected_ar, abs=0.005)
        assert result.car == pytest.approx(injected_ar, abs=0.005)

    def test_three_day_window_sums_correctly(self) -> None:
        panel = _make_clean_panel(n_days=300, beta_mkt=1.0)
        event_idx = 260
        # inject AR on day 0 only
        _inject_ar(panel, event_idx, 0.01)

        event = Event(event_id="T2", ticker="TST", event_date=panel.index[event_idx].date())
        cfg = EventStudyConfig(event_start=-1, event_end=1)
        result = run_event_study(event, panel, cfg)
        assert len(result.daily) == 3
        # CAR should be approximately the day-0 AR (other days are noise around 0)
        assert abs(result.car) < 0.04

    def test_window_out_of_range_raises(self) -> None:
        panel = _make_clean_panel(n_days=100)  # too short for default est window
        event = Event(event_id="T3", ticker="TST", event_date=panel.index[50].date())
        cfg = EventStudyConfig(estimation_start=-250, estimation_end=-11)
        with pytest.raises(ValueError):
            run_event_study(event, panel, cfg)

    def test_event_date_not_in_index_raises(self) -> None:
        panel = _make_clean_panel(n_days=300)
        event = Event(event_id="T4", ticker="TST", event_date=date(1900, 1, 1))
        with pytest.raises(ValueError):
            run_event_study(event, panel)


class TestRunEventStudyFF3:
    def test_recovers_injected_abnormal_return_ff3(self) -> None:
        panel = _make_clean_panel(n_days=300, beta_mkt=1.3, beta_smb=0.4, beta_hml=-0.1)
        injected_ar = 0.018
        event_idx = 270
        _inject_ar(panel, event_idx, injected_ar)

        event = Event(event_id="T5", ticker="TST", event_date=panel.index[event_idx].date())
        cfg = EventStudyConfig(event_start=0, event_end=0, model="ff3")
        result = run_event_study(event, panel, cfg)
        assert result.daily["abnormal"].iloc[0] == pytest.approx(injected_ar, abs=0.006)


class TestCAAR:
    def test_caar_aggregates_multiple_events(self) -> None:
        panels = [_make_clean_panel(n_days=300, seed=s) for s in (1, 2, 3, 4, 5)]
        injected = 0.02
        results = []
        for i, panel in enumerate(panels):
            event_idx = 260
            _inject_ar(panel, event_idx, injected)
            event = Event(event_id=f"E{i}", ticker="TST", event_date=panel.index[event_idx].date())
            cfg = EventStudyConfig(event_start=0, event_end=0)
            results.append(run_event_study(event, panel, cfg))
        agg = caar(results)
        assert agg["n"] == 5
        assert agg["caar"] == pytest.approx(injected, abs=0.005)

    def test_caar_empty(self) -> None:
        agg = caar([])
        assert agg["n"] == 0
        assert agg["caar"] == 0.0


class TestFactorLoaders:
    def test_synthetic_factors_shape(self) -> None:
        dates = pd.bdate_range("2024-01-02", periods=50)
        df = synthetic_factors(dates, seed=42)
        assert list(df.columns) == ["mkt_rf", "smb", "hml", "rf"]
        assert len(df) == 50
        assert (df["rf"] > 0).all()

    def test_synthetic_asset_returns_match_length(self) -> None:
        dates = pd.bdate_range("2024-01-02", periods=50)
        f = synthetic_factors(dates, seed=42)
        a = synthetic_asset_returns(f, alpha=0, beta_mkt=1.0, seed=42)
        assert len(a) == 50

    def test_market_return_from_factors(self) -> None:
        dates = pd.bdate_range("2024-01-02", periods=10)
        f = synthetic_factors(dates, seed=42)
        m = market_return_from_factors(f)
        np.testing.assert_array_almost_equal(m.to_numpy(), (f["mkt_rf"] + f["rf"]).to_numpy())

    def test_load_ff3_csv_fixture(self) -> None:
        df = load_ff3_from_csv(FIXTURES / "ff3_sample.csv")
        assert list(df.columns) == ["mkt_rf", "smb", "hml", "rf"]
        assert len(df) == 5
        # values converted from percent to decimal
        assert df["mkt_rf"].iloc[0] == pytest.approx(0.005)
        assert df["rf"].iloc[0] == pytest.approx(0.0002)
