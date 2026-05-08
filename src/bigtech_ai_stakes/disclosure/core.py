"""Disclosure-quality scoring against the 7-criterion rubric.

Use :func:`score_disclosure` on a footnote text. For an issuer-level
comparison run :func:`compare_issuers` over a dict of issuer -> footnote text.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from bigtech_ai_stakes.disclosure.rubric import CRITERIA, MAX_SCORE


@dataclass
class CriterionResult:
    criterion_id: int
    name: str
    score: float
    evidence: str


@dataclass
class DisclosureScore:
    """Aggregated disclosure-quality score for one footnote."""

    issuer: str
    accession: str
    criteria: list[CriterionResult]
    excerpt: str = ""

    @property
    def total(self) -> float:
        return sum(c.score for c in self.criteria)

    @property
    def total_pct(self) -> float:
        return self.total / MAX_SCORE if MAX_SCORE else 0.0

    def to_dict(self) -> dict[str, object]:
        return {
            "issuer": self.issuer,
            "accession": self.accession,
            "total": self.total,
            "total_pct": self.total_pct,
            **{c.name: c.score for c in self.criteria},
        }


def score_disclosure(
    text: str, *, issuer: str = "", accession: str = "", excerpt_chars: int = 300
) -> DisclosureScore:
    """Score a single footnote against all 7 criteria."""
    criteria_results: list[CriterionResult] = []
    for i, (name, fn) in enumerate(CRITERIA, start=1):
        score, evidence = fn(text)
        criteria_results.append(
            CriterionResult(criterion_id=i, name=name, score=score, evidence=evidence)
        )
    return DisclosureScore(
        issuer=issuer,
        accession=accession,
        criteria=criteria_results,
        excerpt=text[:excerpt_chars].strip(),
    )


def compare_issuers(footnotes: dict[str, str]) -> pd.DataFrame:
    """Score multiple issuers and return a long-format DataFrame for ranking.

    Columns: issuer, total, total_pct, plus one column per criterion name.
    """
    rows = [score_disclosure(text, issuer=name).to_dict() for name, text in footnotes.items()]
    df = pd.DataFrame(rows)
    return df.sort_values("total", ascending=False).reset_index(drop=True)
