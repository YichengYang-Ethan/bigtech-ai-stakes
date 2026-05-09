"""Pull live SEC filings and run the footnote extractor on each.

Usage::

    uv run python scripts/run_live_extraction.py
    uv run python scripts/run_live_extraction.py --tickers MSFT --max-per-ticker 5

Output is written to ``data/stakes_extracted.csv``. Filing text is cached
under ``data/filings/`` (gitignored).
"""

from __future__ import annotations

import csv
import sys
from datetime import date
from pathlib import Path

import typer
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

from bigtech_ai_stakes.filings.edgar_adapter import (  # noqa: E402
    fetch_filing_text,
    list_filings,
)
from bigtech_ai_stakes.filings.footnote_extractor import (  # noqa: E402
    extract_all,
    find_relevant_section,
)

console = Console()


def main(
    tickers: str = typer.Option("GOOGL,AMZN,MSFT,NVDA", help="Comma-separated tickers."),
    since: str = typer.Option("2023-01-01", help="Filter filings on or after YYYY-MM-DD."),
    forms: str = typer.Option("10-K,10-Q", help="Comma-separated form types."),
    out: Path = typer.Option(  # noqa: B008
        Path("data/stakes_extracted.csv"), help="Output CSV path."
    ),
    max_per_ticker: int = typer.Option(20, help="Max filings per ticker (cap network usage)."),
) -> None:
    """Run live SEC extraction across covered issuers."""
    ticker_list = [t.strip().upper() for t in tickers.split(",") if t.strip()]
    form_list = [f.strip() for f in forms.split(",") if f.strip()]
    since_date = date.fromisoformat(since)

    console.print(f"[bold]Live SEC extraction[/bold]: {ticker_list} x {form_list} since {since}")

    all_rows: list[dict[str, object]] = []
    for ticker in ticker_list:
        console.print(f"\n[cyan]{ticker}[/cyan]")
        try:
            refs = list_filings(ticker, forms=form_list, since=since_date)
        except Exception as e:
            console.print(f"  [red]list_filings failed: {e}[/red]")
            continue
        refs = refs[:max_per_ticker]
        console.print(f"  found {len(refs)} filings (capped at {max_per_ticker})")

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
            transient=True,
        ) as progress:
            t = progress.add_task(f"extracting {ticker}", total=len(refs))
            for ref in refs:
                progress.update(t, description=f"{ticker} {ref.form} {ref.filing_date}")
                try:
                    text = fetch_filing_text(ref)
                except Exception as e:
                    console.print(f"  [red]fetch failed {ref.accession}: {e}[/red]")
                    progress.advance(t)
                    continue
                section = find_relevant_section(text)
                if not section:
                    all_rows.append(_row_no_hit(ticker, ref))
                else:
                    r = extract_all(section)
                    all_rows.append(_row_with_hit(ticker, ref, r, len(section)))
                progress.advance(t)

    out.parent.mkdir(parents=True, exist_ok=True)
    if not all_rows:
        console.print("[yellow]no rows to write[/yellow]")
        return

    with out.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(all_rows[0].keys()))
        writer.writeheader()
        writer.writerows(all_rows)
    console.print(f"\n[green]wrote {len(all_rows)} rows to {out}[/green]")

    data_fields = (
        "investees",
        "carrying_value_billion",
        "cumulative_gains_billion",
        "cumulative_losses_billion",
        "funding_commitment_billion",
        "funded_to_date_billion",
        "pretax_gain_quarter_billion",
        "stake_pct",
        "valuation_methods",
    )

    def _has_data(row: dict[str, object]) -> bool:
        return bool(row["anchor_hit"]) and any(row[f] for f in data_fields)

    hits = sum(1 for row in all_rows if row["anchor_hit"])
    with_data = sum(1 for row in all_rows if _has_data(row))
    console.print(f"  anchor_hits        : {hits}/{len(all_rows)}")
    console.print(f"  rows with data     : {with_data}/{len(all_rows)}")
    by_ticker: dict[str, dict[str, int]] = {}
    for row in all_rows:
        d = by_ticker.setdefault(str(row["ticker"]), {"total": 0, "hit": 0, "data": 0})
        d["total"] += 1
        if row["anchor_hit"]:
            d["hit"] += 1
            if _has_data(row):
                d["data"] += 1
    for ticker, d in by_ticker.items():
        console.print(f"  {ticker:<6} hit={d['hit']}/{d['total']}, with_data={d['data']}")


def _row_no_hit(ticker: str, ref: object) -> dict[str, object]:
    return {
        "ticker": ticker,
        "form": ref.form,  # type: ignore[attr-defined]
        "filing_date": ref.filing_date,  # type: ignore[attr-defined]
        "accession": ref.accession,  # type: ignore[attr-defined]
        "anchor_hit": False,
        "section_chars": 0,
        "investees": "",
        "carrying_value_billion": "",
        "cumulative_gains_billion": "",
        "cumulative_losses_billion": "",
        "funding_commitment_billion": "",
        "funded_to_date_billion": "",
        "pretax_gain_quarter_billion": "",
        "stake_pct": "",
        "valuation_methods": "",
    }


def _row_with_hit(ticker: str, ref: object, r: object, n_chars: int) -> dict[str, object]:
    return {
        "ticker": ticker,
        "form": ref.form,  # type: ignore[attr-defined]
        "filing_date": ref.filing_date,  # type: ignore[attr-defined]
        "accession": ref.accession,  # type: ignore[attr-defined]
        "anchor_hit": True,
        "section_chars": n_chars,
        "investees": "|".join(r.investees),  # type: ignore[attr-defined]
        "carrying_value_billion": r.carrying_value_billion or "",  # type: ignore[attr-defined]
        "cumulative_gains_billion": r.cumulative_gains_billion or "",  # type: ignore[attr-defined]
        "cumulative_losses_billion": r.cumulative_losses_billion or "",  # type: ignore[attr-defined]
        "funding_commitment_billion": r.funding_commitment_billion or "",  # type: ignore[attr-defined]
        "funded_to_date_billion": r.funded_to_date_billion or "",  # type: ignore[attr-defined]
        "pretax_gain_quarter_billion": r.pretax_gain_quarter_billion or "",  # type: ignore[attr-defined]
        "stake_pct": r.stake_pct or "",  # type: ignore[attr-defined]
        "valuation_methods": "|".join(r.valuation_methods),  # type: ignore[attr-defined]
    }


if __name__ == "__main__":
    typer.run(main)
