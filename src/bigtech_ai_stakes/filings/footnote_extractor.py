"""Extract structured fields from ASC 321 / ASC 323 footnote text.

Regex-only for v0.1 — deterministic and unit-testable. A Claude-API fallback
for ambiguous footnotes is planned for v0.2 (see docs/methodology.md).
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from typing import Final

from pydantic import BaseModel, Field

# Phrases that mark the start of an ASC 321 / 323 footnote in a 10-K / 10-Q.
# Order matters: more financial-statement-specific phrases first so we land in
# the right section if the issuer mentions the lab in multiple places.
DEFAULT_ANCHOR_PHRASES: Final[list[str]] = [
    "non-marketable equity securities",
    "investment of approximately",  # MSFT post Oct 2025 restructure
    "as-converted basis",  # MSFT equity-method language
    "from our investments in Anthropic",  # AMZN earnings-release prefix
    "from investments in OpenAI",  # MSFT gains/losses footnote
    "investments in Anthropic",
    "investment in Anthropic",
    "investment in OpenAI",
    "OpenAI Global",
    "OpenAI Group",
]

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
    """Find quarterly gain disclosures.

    Matches multiple phrasings:
      - 'pre-tax gains of $16.8 billion ... from our investments in Anthropic' (AMZN)
      - '$5.9 billion of net gains ... from investments in OpenAI'             (MSFT)
    """
    patterns = [
        rf"pre[-\s]?tax gains?\s+of\s+{_DOLLAR_AMT}",
        rf"{_DOLLAR_AMT}\s+of\s+net\s+gains?",
        rf"net\s+gains?\s+of\s+{_DOLLAR_AMT}",
    ]
    for pat in patterns:
        n = _first_match_to_billion(pat, text)
        if n is not None:
            return n
    return None


def extract_stake_pct(text: str) -> float | None:
    """Find phrases describing an ownership percentage.

    Handles multiple phrasings:
      - 'as-converted ownership interest is approximately 26.79%'  (fixture-style)
      - 'investment of approximately27 percent of OpenAI'           (MSFT Apr 2026 10-Q)
      - 'stake of approximately 14.0 percent'                       (court filing style)
    """
    patterns = [
        r"(?:ownership interest|stake|investment)"
        r"[^.]{0,80}?"
        r"approximately\s*([\d.]+)\s*(?:%|percent)",
        # Fallback: "approximately X% of <Lab>"
        r"approximately\s*([\d.]+)\s*(?:%|percent)\s+of\s+(?:OpenAI|Anthropic)",
    ]
    for pat in patterns:
        m = re.search(pat, text, flags=re.IGNORECASE | re.DOTALL)
        if m:
            return float(m.group(1))
    return None


def extract_valuation_methods(text: str) -> list[str]:
    """Return the canonical names of valuation methods found."""
    found: list[str] = []
    for label, pat in VALUATION_METHOD_PATTERNS:
        if re.search(pat, text, flags=re.IGNORECASE) and label not in found:
            found.append(label)
    return found


def find_relevant_section(
    text: str,
    anchors: Sequence[str] | None = None,
    *,
    window_before: int = 500,
    window_after: int = 2500,
    max_chars: int = 12000,
) -> str:
    """Return a window of text covering all matching anchor phrases.

    A 10-K / 10-Q is too large for direct regex; this isolates the ASC 321 /
    323 disclosure region. When multiple anchor phrases match the same filing
    (typical: stake percentage paragraph + gains/losses paragraph + commitment
    paragraph), we span from the earliest match to the latest, padded by
    ``window_before`` / ``window_after``. ``max_chars`` caps the output.

    Returns an empty string if no anchor phrase is found.
    """
    if anchors is None:
        anchors = DEFAULT_ANCHOR_PHRASES
    text_lower = text.lower()
    positions: list[int] = []
    for phrase in anchors:
        idx = text_lower.find(phrase.lower())
        if idx >= 0:
            positions.append(idx)
    if not positions:
        return ""
    earliest = min(positions)
    latest = max(positions)
    start = max(0, earliest - window_before)
    end = min(len(text), latest + window_after)
    if end - start > max_chars:
        end = start + max_chars
    return text[start:end]


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
