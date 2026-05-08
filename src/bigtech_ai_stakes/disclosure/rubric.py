"""7-criterion disclosure-quality rubric for ASC 321 / 323 footnotes.

Each criterion is a `(text -> (score, evidence))` callable returning a score
in {0.0, 0.5, 1.0} with a short evidence string. See
`docs/disclosure-rubric.md` for the criteria definitions.

A Stage-3 / v0.2 enhancement will replace these rule-based scorers with a
Claude-API-rated rubric that handles paraphrased disclosure language.
"""

from __future__ import annotations

import re
from collections.abc import Callable

from bigtech_ai_stakes.filings.footnote_extractor import (
    extract_investees,
    extract_stake_pct,
    extract_valuation_methods,
)

CriterionFn = Callable[[str], tuple[float, str]]


def criterion_1_investee_named(text: str) -> tuple[float, str]:
    investees = extract_investees(text)
    if investees:
        return (1.0, f"named: {', '.join(investees)}")
    return (0.0, "no investee named")


def criterion_2_stake_disclosed(text: str) -> tuple[float, str]:
    stake = extract_stake_pct(text)
    if stake is not None:
        return (1.0, f"stake: {stake}%")
    return (0.0, "stake not disclosed")


def criterion_3_method_disclosed(text: str) -> tuple[float, str]:
    methods = extract_valuation_methods(text)
    if len(methods) >= 2:
        return (1.0, f"methods: {methods}")
    if len(methods) == 1:
        return (0.5, f"partial: {methods}")
    return (0.0, "method not disclosed")


def criterion_4_sensitivity_to_v_post(text: str) -> tuple[float, str]:
    if re.search(
        r"sensitivity\s+(?:analysis|disclosure)|"
        r"\b(?:10|5|hypothetical)\s*%?\s*(?:increase|decrease|change)\s+in\s+(?:fair\s+value|valuation)|"
        r"if\s+(?:the\s+)?(?:post[- ]?money|valuation)\s+(?:were|had)",
        text,
        re.IGNORECASE,
    ):
        return (1.0, "sensitivity discussed")
    return (0.0, "no sensitivity disclosure")


def criterion_5_related_party(text: str) -> tuple[float, str]:
    if re.search(r"related[\s-]*part(?:y|ies)|asc\s*850", text, re.IGNORECASE):
        return (1.0, "related-party noted")
    return (0.0, "no related-party note")


def criterion_6_quarterly_breakout(text: str) -> tuple[float, str]:
    if re.search(
        r"upward\s+adjustments?|downward\s+adjustments?|"
        r"\$[\d.]+\s*(?:billion|million)\s+of\s+gains?\s+and\s+\$[\d.]+\s*(?:billion|million)\s+of\s+losses?",
        text,
        re.IGNORECASE,
    ):
        return (1.0, "quarterly breakout / gain-loss split present")
    return (0.0, "no quarterly breakout")


def criterion_7_concentration(text: str) -> tuple[float, str]:
    if re.search(r"primarily\s+one\s+investee|concentration", text, re.IGNORECASE):
        return (1.0, "concentration disclosed")
    return (0.0, "no concentration note")


CRITERIA: list[tuple[str, CriterionFn]] = [
    ("investee_named", criterion_1_investee_named),
    ("stake_disclosed", criterion_2_stake_disclosed),
    ("method_disclosed", criterion_3_method_disclosed),
    ("sensitivity_to_v_post", criterion_4_sensitivity_to_v_post),
    ("related_party", criterion_5_related_party),
    ("quarterly_breakout", criterion_6_quarterly_breakout),
    ("concentration", criterion_7_concentration),
]
"""Ordered list of (criterion_name, scoring_function) pairs. Scores out of 7."""

MAX_SCORE: float = float(len(CRITERIA))
