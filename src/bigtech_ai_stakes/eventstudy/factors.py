"""Fama-French 3-factor data sources.

For real-data analysis, download the daily factors from Ken French's data
library (https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/) and load
via :func:`load_ff3_from_csv`. For unit tests, use :func:`synthetic_factors`
together with :func:`synthetic_asset_returns`.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd


def load_ff3_from_csv(
    path: Path | str,
    *,
    skip_header_lines: int = 0,
    skip_footer_lines: int = 0,
    date_format: str = "%Y%m%d",
) -> pd.DataFrame:
    """Load Fama-French 3-factor daily returns from a CSV.

    Defaults assume a clean CSV with columns ``Date,Mkt-RF,SMB,HML,RF`` and
    one header line. For Ken French's raw daily factor file pass
    ``skip_header_lines=4`` (and possibly a non-zero ``skip_footer_lines``
    if the file bundles the annual section).

    Returns a DataFrame indexed by date with columns ``mkt_rf, smb, hml, rf``,
    in DECIMAL form (Ken French publishes in percent; we divide by 100).
    """
    df = pd.read_csv(
        path,
        skiprows=skip_header_lines,
        skipfooter=skip_footer_lines,
        engine="python" if skip_footer_lines else "c",
    )
    df.columns = [c.strip() for c in df.columns]
    if df.columns[0] not in {"Date", "date"}:
        df = df.rename(columns={df.columns[0]: "Date"})
    df = df[df["Date"].astype(str).str.match(r"^\d{8}$|^\d{4}-\d{2}-\d{2}$")]
    df["Date"] = pd.to_datetime(df["Date"].astype(str), format=date_format, errors="coerce")
    df = df.dropna(subset=["Date"]).set_index("Date")
    rename = {"Mkt-RF": "mkt_rf", "SMB": "smb", "HML": "hml", "RF": "rf"}
    df = df.rename(columns=rename)
    cols = ["mkt_rf", "smb", "hml", "rf"]
    for c in cols:
        df[c] = df[c].astype(float) / 100.0
    return df[cols]


def synthetic_factors(dates: pd.DatetimeIndex, *, seed: int = 0) -> pd.DataFrame:
    """Generate plausible synthetic FF3 factor returns for testing.

    Distributions roughly match observed daily moments (RF ~3.75% annual flat).
    """
    rng = np.random.default_rng(seed)
    n = len(dates)
    return pd.DataFrame(
        {
            "mkt_rf": rng.normal(0.0004, 0.010, n),
            "smb": rng.normal(0.0001, 0.005, n),
            "hml": rng.normal(0.00005, 0.005, n),
            "rf": np.full(n, 0.00015),
        },
        index=dates,
    )


def synthetic_asset_returns(
    factors: pd.DataFrame,
    *,
    alpha: float = 0.0,
    beta_mkt: float = 1.0,
    beta_smb: float = 0.0,
    beta_hml: float = 0.0,
    sigma: float = 0.005,
    seed: int = 1,
) -> pd.Series:
    """Generate asset returns following a known FF3 data-generating process.

    ``asset_return = rf + alpha + beta_mkt*mkt_rf + beta_smb*smb + beta_hml*hml + N(0, sigma)``.
    """
    rng = np.random.default_rng(seed)
    eps = rng.normal(0.0, sigma, len(factors))
    return (
        factors["rf"]
        + alpha
        + beta_mkt * factors["mkt_rf"]
        + beta_smb * factors["smb"]
        + beta_hml * factors["hml"]
        + eps
    ).rename("asset")


def market_return_from_factors(factors: pd.DataFrame) -> pd.Series:
    """Compose the gross market return from FF3 components: ``mkt_rf + rf``."""
    return (factors["mkt_rf"] + factors["rf"]).rename("market")
