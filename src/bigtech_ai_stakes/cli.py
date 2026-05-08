"""Command-line interface."""

from __future__ import annotations

import typer
from rich.console import Console
from rich.table import Table

from bigtech_ai_stakes import __version__
from bigtech_ai_stakes.data import load_events, load_stakes

app = typer.Typer(
    name="bigtech-ai-stakes",
    help="Quarterly panel and analytics for U.S. public-company stakes in Anthropic and OpenAI.",
    no_args_is_help=True,
)
console = Console()


@app.command()
def version() -> None:
    """Print the package version."""
    console.print(f"bigtech-ai-stakes {__version__}")


@app.command()
def events(
    lab: str | None = typer.Option(None, help="Filter by lab: anthropic / openai."),
) -> None:
    """List recorded primary-round and Big Tech commitment events."""
    df = load_events()
    if lab:
        df = df[df["lab"].str.lower() == lab.lower()]
    cols = [
        "event_id",
        "lab",
        "event_type",
        "announcement_date",
        "v_post_billion",
        "raise_amount_billion",
        "lead_investors",
        "confidence",
    ]
    table = Table(title=f"Events ({len(df)} rows)")
    for col in cols:
        table.add_column(col)
    for _, row in df.iterrows():
        table.add_row(*[str(row[c]) for c in cols])
    console.print(table)


@app.command()
def stakes(
    investor: str | None = typer.Option(
        None, help="Filter by investor ticker (GOOGL, AMZN, MSFT, NVDA, ...)."
    ),
    lab: str | None = typer.Option(None, help="Filter by lab: anthropic / openai."),
) -> None:
    """List point-in-time ownership snapshots."""
    df = load_stakes()
    if investor:
        df = df[df["investor_ticker"].str.upper() == investor.upper()]
    if lab:
        df = df[df["lab"].str.lower() == lab.lower()]
    cols = [
        "investor_ticker",
        "lab",
        "snapshot_date",
        "stake_pct",
        "fair_value_billion",
        "stake_pct_method",
        "confidence",
    ]
    table = Table(title=f"Stakes ({len(df)} rows)")
    for col in cols:
        table.add_column(col)
    for _, row in df.iterrows():
        table.add_row(*[str(row[c]) for c in cols])
    console.print(table)


if __name__ == "__main__":
    app()
