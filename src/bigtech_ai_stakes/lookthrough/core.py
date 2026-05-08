"""Look-through earnings calculator.

Adapts Buffett's "look-through" framework (Berkshire 1991, 1999 letters) to
strip Mag-7 GAAP earnings of AI-stake markups. Two equivalent formulations:

**Bottom-up** (from inferred stake and observed valuation jump):

    LookThrough_NI = GAAP_NI - stake * delta_V_post + stake * Investee_NI

**Top-down** (from disclosed pre-tax markup, post-tax adjusted):

    LookThrough_NI = GAAP_NI - disclosed_pretax_gain * (1 - tax_rate) + stake * Investee_NI

The top-down form is preferred when the issuer discloses the gain explicitly
(Amazon Q1 2026 8-K does; Alphabet's "primarily one investee" language does
not name the lab so we estimate).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

ScenarioName = Literal["bear", "base", "bull"]


@dataclass(frozen=True)
class LookThroughInputs:
    """Inputs to the look-through EPS calculation for a single quarter."""

    issuer_ticker: str
    quarter: str  # e.g., "2026Q1"
    gaap_net_income_billion: float
    shares_outstanding_billion: float
    stake_pct: float  # 0-100 scale
    delta_v_post_billion: float = 0.0
    investee_net_income_billion: float = 0.0
    disclosed_pretax_gain_billion: float | None = None
    tax_rate: float = 0.21  # US statutory federal rate; override per company


@dataclass
class LookThroughResult:
    """Output of the look-through calculation."""

    issuer_ticker: str
    quarter: str
    gaap_net_income_billion: float
    look_through_net_income_billion: float
    look_through_eps: float
    gaap_eps: float
    eps_drag_billion: float
    method: Literal["bottom_up", "top_down"]
    notes: str = ""

    @property
    def look_through_eps_pct_of_gaap(self) -> float:
        if self.gaap_eps == 0.0:
            return 0.0
        return self.look_through_eps / self.gaap_eps


@dataclass(frozen=True)
class Scenario:
    """A scenario assumption for the investee's quarterly net income."""

    name: ScenarioName
    investee_net_income_billion: float
    notes: str = ""


def _eps(net_income: float, shares: float) -> float:
    if shares <= 0:
        return 0.0
    return net_income / shares


def look_through_bottom_up(inputs: LookThroughInputs) -> LookThroughResult:
    """Bottom-up: subtract stake * delta_V_post, add stake * investee NI."""
    stake = inputs.stake_pct / 100.0
    markup_share = stake * inputs.delta_v_post_billion
    investee_share = stake * inputs.investee_net_income_billion
    lt_ni = inputs.gaap_net_income_billion - markup_share + investee_share
    return LookThroughResult(
        issuer_ticker=inputs.issuer_ticker,
        quarter=inputs.quarter,
        gaap_net_income_billion=inputs.gaap_net_income_billion,
        look_through_net_income_billion=lt_ni,
        look_through_eps=_eps(lt_ni, inputs.shares_outstanding_billion),
        gaap_eps=_eps(inputs.gaap_net_income_billion, inputs.shares_outstanding_billion),
        eps_drag_billion=markup_share - investee_share,
        method="bottom_up",
        notes=f"stake={inputs.stake_pct}%; dV_post={inputs.delta_v_post_billion}B",
    )


def look_through_top_down(inputs: LookThroughInputs) -> LookThroughResult:
    """Top-down: subtract disclosed pre-tax gain * (1-tax_rate); add stake * NI."""
    if inputs.disclosed_pretax_gain_billion is None:
        raise ValueError(
            "look_through_top_down requires `disclosed_pretax_gain_billion`; "
            "use look_through_bottom_up if only delta_V_post is known."
        )
    stake = inputs.stake_pct / 100.0
    after_tax_markup = inputs.disclosed_pretax_gain_billion * (1.0 - inputs.tax_rate)
    investee_share = stake * inputs.investee_net_income_billion
    lt_ni = inputs.gaap_net_income_billion - after_tax_markup + investee_share
    return LookThroughResult(
        issuer_ticker=inputs.issuer_ticker,
        quarter=inputs.quarter,
        gaap_net_income_billion=inputs.gaap_net_income_billion,
        look_through_net_income_billion=lt_ni,
        look_through_eps=_eps(lt_ni, inputs.shares_outstanding_billion),
        gaap_eps=_eps(inputs.gaap_net_income_billion, inputs.shares_outstanding_billion),
        eps_drag_billion=after_tax_markup - investee_share,
        method="top_down",
        notes=(
            f"pretax={inputs.disclosed_pretax_gain_billion}B; "
            f"tax_rate={inputs.tax_rate}; stake={inputs.stake_pct}%"
        ),
    )


def look_through(
    inputs: LookThroughInputs,
    *,
    method: Literal["auto", "bottom_up", "top_down"] = "auto",
) -> LookThroughResult:
    """Dispatch to bottom-up or top-down based on available inputs.

    ``method='auto'`` picks top-down when disclosed_pretax_gain_billion is set,
    bottom-up otherwise.
    """
    if method == "top_down":
        return look_through_top_down(inputs)
    if method == "bottom_up":
        return look_through_bottom_up(inputs)
    if inputs.disclosed_pretax_gain_billion is not None:
        return look_through_top_down(inputs)
    return look_through_bottom_up(inputs)


def evaluate_scenarios(
    base_inputs: LookThroughInputs,
    scenarios: list[Scenario],
    *,
    method: Literal["auto", "bottom_up", "top_down"] = "auto",
) -> list[LookThroughResult]:
    """Run multiple investee-NI scenarios on the same base inputs."""
    results: list[LookThroughResult] = []
    for s in scenarios:
        scenario_inputs = LookThroughInputs(
            issuer_ticker=base_inputs.issuer_ticker,
            quarter=base_inputs.quarter,
            gaap_net_income_billion=base_inputs.gaap_net_income_billion,
            shares_outstanding_billion=base_inputs.shares_outstanding_billion,
            stake_pct=base_inputs.stake_pct,
            delta_v_post_billion=base_inputs.delta_v_post_billion,
            investee_net_income_billion=s.investee_net_income_billion,
            disclosed_pretax_gain_billion=base_inputs.disclosed_pretax_gain_billion,
            tax_rate=base_inputs.tax_rate,
        )
        result = look_through(scenario_inputs, method=method)
        result.notes = f"scenario={s.name}; {s.notes}; {result.notes}".strip()
        results.append(result)
    return results


def default_scenarios(
    *,
    bear_ni_billion: float = -5.0,
    base_ni_billion: float = -2.0,
    bull_ni_billion: float = 1.0,
) -> list[Scenario]:
    """Return a standard set of bear/base/bull scenarios for the investee NI.

    Defaults assume a still-unprofitable AI lab where:
      - **bear**: heavy losses, no profitability through 2030
      - **base**: moderate losses on path to 2028 profitability
      - **bull**: small positive NI as scale economics kick in
    """
    return [
        Scenario(name="bear", investee_net_income_billion=bear_ni_billion, notes="slow ramp"),
        Scenario(name="base", investee_net_income_billion=base_ni_billion, notes="consensus"),
        Scenario(name="bull", investee_net_income_billion=bull_ni_billion, notes="accelerated"),
    ]
