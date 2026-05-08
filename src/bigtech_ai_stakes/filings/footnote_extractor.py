"""Extract structured fields from ASC 321 / ASC 323 footnote text.

Regex-only for v0.1 — deterministic and unit-testable. A Claude-API fallback
for ambiguous footnotes is planned for v0.2 (see docs/methodology.md).
"""

from __future__ import annotations

import re
from typing import Final

from pydantic import BaseModel, Field

# Investee names we look for explicitly. Order matters for greedy matching:
# longer / more specific first, so "OpenAI Group PBC" is preferred over "OpenAI".
INVESTEE_PATTERNS: Final[list[str]] = [
    r"OpenAI Group PBC",
    r"OpenAI Global,?\s*LLC",
    r"OpenAI Group",
    r"OpenAI",
    r"Anthropic\s+PBC",
    r"Anthropic",
]

VALUATION_METHOD_PATTERNS: Final[list[tuple[str, str]]] = [
    ("option_pricing", r"option[-\s]?pricing models?"),
    ("market_comparable", r"market[-\s]?comparable approach"),
    ("common_stock_equivalent", r"common[-\s]?stock equivalent method"),
    ("equity_method", r"equity method of accounting"),
    ("backsolve", r"backsolve method"),
]


_NUM = r"([\d,]+(?:\.\d+)?)"
_UNIT = r"(billion|million|trillion)"
_DOLLAR_AMT = rf"\$\s*{_NUM}\s*{_UNIT}?"


class FootnoteExtraction(BaseModel):
    """Structured fields extracted from a single ASC 321 / 323 footnote."""

    investees: list[str] = Field(default_factory=list)
    carrying_value_billion: float | None = None
    cumulative_gains_billion: float | None = None
    cumulative_losses_billion: float | None = None
    funding_commitment_billion: float | None = None
    funded_to_date_billion: float | None = None
    pretax_gain_quarter_billion: float | None = None
    stake_pct: float | None = None
    valuation_methods: list[str] = Field(default_factory=list)
    excerpt: str = ""

    @property
    def has_data(self) -> bool:
        return any(
            (
                self.investees,
                self.carrying_value_billion is not None,
                self.cumulative_gains_billion is not None,
                self.funding_commitment_billion is not None,
                self.pretax_gain_quarter_billion is not None,
                self.stake_pct is not None,
            )
        )


def _to_billion(num_str: str, unit: str | None) -> float:
    """Normalize a "$X.Y billion / million / trillion" string to USD billions."""
    n = float(num_str.replace(",", ""))
    u = (unit or "billion").lower()
    if u == "billion":
        return n
    if u == "million":
        return n / 1_000.0
    if u == "trillion":
        return n * 1_000.0
    raise ValueError(f"unknown unit: {unit}")


def _first_match_to_billion(pattern: str, text: str) -> float | None:
    m = re.search(pattern, text, flags=re.IGNORECASE | re.DOTALL)
    if not m:
        return None
    return _to_billion(m.group(1), m.group(2) if m.lastindex and m.lastindex >= 2 else None)


def extract_investees(text: str) -> list[str]:
    """Return unique investee names mentioned in the text, normalized."""
    seen: list[str] = []
    for pat in INVESTEE_PATTERNS:
        if re.search(rf"\b{pat}\b", text, flags=re.IGNORECASE):
            normalized = _normalize_investee(pat)
            if normalized not in seen:
                seen.append(normalized)
    return seen


def _normalize_investee(raw: str) -> str:
    raw_lower = raw.lower()
    if "openai" in raw_lower:
        return "OpenAI"
    if "anthropic" in raw_lower:
        return "Anthropic"
    return raw


def extract_carrying_value(text: str) -> float | None:
    """Find phrases like 'the carrying value... was $33.7 billion'."""
    pat = (
        rf"carrying value\s+of\s+(?:our\s+)?non[-\s]?marketable equity securities"
        rf"[^.]{{0,80}}?(?:was|of|is)\s+{_DOLLAR_AMT}"
    )
    return _first_match_to_billion(pat, text)


def extract_cumulative_gains(text: str) -> float | None:
    """Find 'comprised of $35.4 billion of gains'."""
    pat = rf"{_DOLLAR_AMT}\s+of\s+gains"
    return _first_match_to_billion(pat, text)


def extract_cumulative_losses(text: str) -> float | None:
    """Find 'and $2.5 billion of losses'."""
    pat = rf"{_DOLLAR_AMT}\s+of\s+losses"
    return _first_match_to_billion(pat, text)


def extract_funding_commitment(text: str) -> float | None:
    """Find 'total funding commitments of $13 billion'."""
    pat = rf"total funding commitments?\s+of\s+{_DOLLAR_AMT}"
    return _first_match_to_billion(pat, text)


def extract_funded_to_date(text: str) -> float | None:
    """Find 'of which $11.8 billion has been funded'."""
    pat = rf"of which\s+{_DOLLAR_AMT}\s+has been funded"
    return _first_match_to_billion(pat, text)


def extract_pretax_gain_quarter(text: str) -> float | None:
    """Find 'pre-tax gains of $16.8 billion ... from our investments in <lab>'."""
    pat = rf"pre[-\s]?tax gains?\s+of\s+{_DOLLAR_AMT}"
    return _first_match_to_billion(pat, text)


def extract_stake_pct(text: str) -> float | None:
    """Find 'as-converted ownership interest is approximately 26.79%'."""
    pat = r"(?:ownership interest|stake)[^.]{0,80}?(?:is|of)\s+approximately\s+([\d.]+)\s*%"
    m = re.search(pat, text, flags=re.IGNORECASE | re.DOTALL)
    if not m:
        return None
    return float(m.group(1))


def extract_valuation_methods(text: str) -> list[str]:
    """Return the canonical names of valuation methods found."""
    found: list[str] = []
    for label, pat in VALUATION_METHOD_PATTERNS:
        if re.search(pat, text, flags=re.IGNORECASE) and label not in found:
            found.append(label)
    return found


def extract_all(text: str, *, excerpt_chars: int = 500) -> FootnoteExtraction:
    """Run every extractor and bundle results into a typed result."""
    return FootnoteExtraction(
        investees=extract_investees(text),
        carrying_value_billion=extract_carrying_value(text),
        cumulative_gains_billion=extract_cumulative_gains(text),
        cumulative_losses_billion=extract_cumulative_losses(text),
        funding_commitment_billion=extract_funding_commitment(text),
        funded_to_date_billion=extract_funded_to_date(text),
        pretax_gain_quarter_billion=extract_pretax_gain_quarter(text),
        stake_pct=extract_stake_pct(text),
        valuation_methods=extract_valuation_methods(text),
        excerpt=text[:excerpt_chars].strip(),
    )
