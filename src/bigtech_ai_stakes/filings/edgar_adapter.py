"""SEC EDGAR filing retrieval via edgartools.

Thin, typed wrapper that returns plain dataclasses so the rest of the package
does not depend on edgartools internals. Network access is gated behind explicit
function calls; tests should mock or skip live fetches.
"""

from __future__ import annotations

import os
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

from bigtech_ai_stakes.data import REPO_ROOT

DEFAULT_IDENTITY = "Yicheng Yang yy85@illinois.edu"

# Big Tech issuers with material AI-lab equity stakes (v0.1 coverage).
COVERED_ISSUERS: dict[str, dict[str, str]] = {
    "GOOGL": {"name": "Alphabet", "cik": "0001652044"},
    "AMZN": {"name": "Amazon", "cik": "0001018724"},
    "MSFT": {"name": "Microsoft", "cik": "0000789019"},
    "NVDA": {"name": "NVIDIA", "cik": "0001045810"},
    "CRM": {"name": "Salesforce", "cik": "0001108524"},
    "QCOM": {"name": "Qualcomm", "cik": "0000804328"},
    "ZM": {"name": "Zoom", "cik": "0001585521"},
}

DEFAULT_FORMS: tuple[str, ...] = ("10-K", "10-Q", "8-K")
CACHE_DIR = REPO_ROOT / "data" / "filings"


def configure_identity(identity: str | None = None) -> str:
    """Set the EDGAR User-Agent identity. SEC requires `<name> <email>` format.

    Resolution order: explicit argument > EDGAR_IDENTITY env var > package default.
    """
    actual = identity or os.environ.get("EDGAR_IDENTITY") or DEFAULT_IDENTITY
    from edgar import set_identity

    set_identity(actual)
    return actual


@dataclass
class FilingRef:
    """Lightweight reference to an SEC filing.

    The `_raw` field stashes the underlying edgartools `Filing` object for lazy
    text retrieval; it is excluded from equality, hash, and repr so FilingRef
    behaves as a plain value object for the rest of the package.
    """

    ticker: str
    form: str
    filing_date: date
    accession: str
    period_of_report: date | None = None
    primary_document: str | None = None
    _raw: Any = field(default=None, compare=False, hash=False, repr=False)

    @property
    def cache_path(self) -> Path:
        safe_form = self.form.replace("/", "-")
        return CACHE_DIR / self.ticker.upper() / safe_form / f"{self.accession}.txt"


def list_filings(
    ticker: str,
    forms: Iterable[str] = DEFAULT_FORMS,
    since: date | None = None,
    until: date | None = None,
    *,
    identity: str | None = None,
) -> list[FilingRef]:
    """List filings for a covered issuer.

    Returns FilingRef objects without downloading filing bodies. Body text is
    fetched lazily via :func:`fetch_filing_text`.
    """
    if ticker.upper() not in COVERED_ISSUERS:
        raise ValueError(f"ticker not in COVERED_ISSUERS: {ticker}")
    configure_identity(identity)

    from edgar import Company

    company = Company(ticker.upper())
    filings = company.get_filings(form=list(forms))
    if since or until:
        s = since.isoformat() if since else ""
        u = until.isoformat() if until else ""
        filings = filings.filter(date=f"{s}:{u}")

    refs: list[FilingRef] = []
    for f in filings:
        fd = _to_date(f.filing_date)
        if fd is None:
            continue  # SEC filings always have a date; skip if missing for safety
        refs.append(
            FilingRef(
                ticker=ticker.upper(),
                form=f.form,
                filing_date=fd,
                accession=str(getattr(f, "accession_no", getattr(f, "accession", ""))),
                period_of_report=_to_date(getattr(f, "period_of_report", None)),
                primary_document=getattr(f, "primary_document", None),
                _raw=f,
            )
        )
    return refs


def fetch_filing_text(ref: FilingRef, *, use_cache: bool = True) -> str:
    """Fetch the plain-text content of a filing's primary document.

    Caches the result under data/filings/<TICKER>/<FORM>/<ACCESSION>.txt
    (gitignored). On cache miss, requires the FilingRef to carry an underlying
    edgartools `Filing` object via `_raw` (i.e., it must have come from
    :func:`list_filings`).
    """
    cache = ref.cache_path
    if use_cache and cache.exists():
        return cache.read_text(encoding="utf-8")

    if ref._raw is None:
        raise ValueError(
            "FilingRef has no underlying Filing; call list_filings() to materialize one"
        )

    text: str = ref._raw.text() or ""
    if use_cache:
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(text, encoding="utf-8")
    return text


def cik_for(ticker: str) -> str:
    """Return the zero-padded CIK string for a covered issuer."""
    t = ticker.upper()
    if t not in COVERED_ISSUERS:
        raise ValueError(f"ticker not in COVERED_ISSUERS: {t}")
    return COVERED_ISSUERS[t]["cik"]


def _to_date(v: Any) -> date | None:
    if v is None:
        return None
    if isinstance(v, date):
        return v
    return date.fromisoformat(str(v))
