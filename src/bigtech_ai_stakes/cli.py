"""Command-line interface."""

from __future__ import annotations

import os
from datetime import date
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from bigtech_ai_stakes import __version__
from bigtech_ai_stakes.data import load_events, load_stakes
from bigtech_ai_stakes.disclosure.core import compare_issuers, score_disclosure
from bigtech_ai_stakes.filings.edgar_adapter import list_filings
from bigtech_ai_stakes.filings.footnote_extractor import extract_all
from bigtech_ai_stakes.inference.ownership import StakeAnchor, steps_to_frame, walk_forward
from bigtech_ai_stakes.lookthrough.core import (
    LookThroughInputs,
    default_scenarios,
    evaluate_scenarios,
    look_through,
)

app = typer.Typer(
    name="bigtech-ai-stakes",
    help="Quarterly panel and analytics for U.S. public-company stakes in Anthropic and OpenAI.",
    no_args_is_help=True,
)
filings_app = typer.Typer(
    name="filings", help="SEC EDGAR filing operations (list, extract).", no_args_is_help=True
)
inference_app = typer.Typer(
    name="inference",
    help="Ownership inference (forward-walk an anchor stake through events).",
    no_args_is_help=True,
)
lookthrough_app = typer.Typer(
    name="lookthrough",
    help="Look-through EPS calculator (strip AI-stake markups from reported earnings).",
    no_args_is_help=True,
)
disclosure_app = typer.Typer(
    name="disclosure",
    help="ASC 321 / 323 disclosure-quality 7-criterion scoring.",
    no_args_is_help=True,
)
backtest_app = typer.Typer(
    name="backtest",
    help="Cross-wrapper arbitrage backtest (event drift + pairs strategies).",
    no_args_is_help=True,
)
app.add_typer(filings_app)
app.add_typer(inference_app)
app.add_typer(lookthrough_app)
app.add_typer(disclosure_app)
app.add_typer(backtest_app)
console = Console()

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURES_DIR = REPO_ROOT / "tests" / "fixtures"


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


@filings_app.command("list")
def filings_list(
    ticker: str = typer.Option(..., help="Ticker (must be in COVERED_ISSUERS)."),
    form: list[str] = typer.Option(  # noqa: B008
        ["10-Q", "10-K"], help="Form types to include."
    ),
    since: str | None = typer.Option(None, help="Filter filings on or after YYYY-MM-DD."),
) -> None:
    """List SEC filings for a covered issuer (live network call)."""
    since_date = date.fromisoformat(since) if since else None
    refs = list_filings(ticker, forms=form, since=since_date)
    table = Table(title=f"{ticker.upper()} filings ({len(refs)} found)")
    for col in ("form", "filing_date", "accession", "period_of_report"):
        table.add_column(col)
    for r in refs:
        table.add_row(r.form, str(r.filing_date), r.accession, str(r.period_of_report or ""))
    console.print(table)


@filings_app.command("extract")
def filings_extract(
    from_file: Path = typer.Option(  # noqa: B008
        ..., "--from-file", help="Path to a footnote text file."
    ),
) -> None:
    """Extract ASC 321 / 323 fields from a footnote text file."""
    text = from_file.read_text(encoding="utf-8")
    result = extract_all(text)
    console.print(result.model_dump_json(indent=2, exclude={"excerpt"}))


@inference_app.command("series")
def inference_series(
    investor: str = typer.Option(..., help="Investor ticker."),
    lab: str = typer.Option(..., help="Lab: anthropic / openai."),
    anchor_pct: float = typer.Option(..., help="Disclosed stake percentage at anchor date."),
    anchor_date: str = typer.Option(..., help="Anchor date YYYY-MM-DD."),
    anchor_source: str = typer.Option("disclosed", help="Source tag for the anchor."),
) -> None:
    """Walk an anchor stake forward through recorded events."""
    df_events = load_events()
    anchor = StakeAnchor(
        investor_ticker=investor.upper(),
        lab=lab.lower(),
        snapshot_date=date.fromisoformat(anchor_date),
        stake_pct=anchor_pct,
        source=anchor_source,
    )
    steps = walk_forward(anchor, df_events)
    df = steps_to_frame(steps)
    table = Table(title=f"Inferred stake series — {investor.upper()} in {lab.lower()}")
    for col in ("snapshot_date", "stake_pct", "method", "event_id"):
        table.add_column(col)
    for _, row in df.iterrows():
        evt = row["event_id"] if row["event_id"] else ""
        table.add_row(str(row["snapshot_date"]), f"{row['stake_pct']:.4f}", row["method"], str(evt))
    console.print(table)


@lookthrough_app.command("eps")
def lookthrough_eps(
    ticker: str = typer.Option(..., help="Issuer ticker."),
    quarter: str = typer.Option(..., help="Quarter label, e.g., 2026Q1."),
    gaap_ni: float = typer.Option(..., help="GAAP net income (USD bn)."),
    shares: float = typer.Option(..., help="Shares outstanding (bn)."),
    stake: float = typer.Option(..., help="Stake percentage (0-100)."),
    delta_v: float = typer.Option(
        0.0, help="Change in lab post-money during the quarter (USD bn)."
    ),
    investee_ni: float = typer.Option(0.0, help="Investee NI for the quarter (USD bn)."),
    pretax_gain: float | None = typer.Option(
        None, help="If issuer disclosed a pre-tax gain (USD bn), uses top-down."
    ),
    tax_rate: float = typer.Option(0.21, help="Statutory federal tax rate."),
    scenarios: bool = typer.Option(False, "--scenarios", help="Run bear/base/bull scenarios."),
) -> None:
    """Compute look-through EPS for an issuer's stake in a lab."""
    inputs = LookThroughInputs(
        issuer_ticker=ticker.upper(),
        quarter=quarter,
        gaap_net_income_billion=gaap_ni,
        shares_outstanding_billion=shares,
        stake_pct=stake,
        delta_v_post_billion=delta_v,
        investee_net_income_billion=investee_ni,
        disclosed_pretax_gain_billion=pretax_gain,
        tax_rate=tax_rate,
    )
    if scenarios:
        results = evaluate_scenarios(inputs, default_scenarios())
        table = Table(title=f"Look-through scenarios — {ticker.upper()} {quarter}")
        for col in ("scenario", "lt_ni_billion", "lt_eps", "gaap_eps", "method"):
            table.add_column(col)
        for r in results:
            scenario_name = r.notes.split(";")[0].replace("scenario=", "").strip()
            table.add_row(
                scenario_name,
                f"{r.look_through_net_income_billion:.2f}",
                f"{r.look_through_eps:.3f}",
                f"{r.gaap_eps:.3f}",
                r.method,
            )
        console.print(table)
    else:
        r = look_through(inputs)
        labels = ("GAAP NI ($bn)", "LT NI ($bn)", "EPS drag ($bn)", "GAAP EPS", "LT EPS", "Method")
        values = (
            f"{r.gaap_net_income_billion:.2f}",
            f"{r.look_through_net_income_billion:.2f}",
            f"{r.eps_drag_billion:.2f}",
            f"{r.gaap_eps:.3f}",
            f"{r.look_through_eps:.3f}",
            r.method,
        )
        table = Table(title=f"Look-through EPS — {ticker.upper()} {quarter}")
        for col in labels:
            table.add_column(col)
        table.add_row(*values)
        console.print(table)


@disclosure_app.command("score")
def disclosure_score(
    from_file: Path = typer.Option(  # noqa: B008
        ..., "--from-file", help="Path to a footnote text file."
    ),
    issuer: str = typer.Option("", help="Issuer label for the report."),
) -> None:
    """Score a single footnote against the 7-criterion rubric."""
    text = from_file.read_text(encoding="utf-8")
    result = score_disclosure(text, issuer=issuer)
    table = Table(title=f"Disclosure score — {issuer or 'unknown'} (total {result.total}/7)")
    for col in ("#", "criterion", "score", "evidence"):
        table.add_column(col)
    for c in result.criteria:
        table.add_row(str(c.criterion_id), c.name, f"{c.score:.1f}", c.evidence)
    console.print(table)


@disclosure_app.command("compare-fixtures")
def disclosure_compare_fixtures() -> None:
    """Score all 3 baked-in fixtures and rank issuers by total score."""
    footnotes: dict[str, str] = {}
    for issuer, filename in (
        ("GOOGL", "footnote_googl_q3_2024.txt"),
        ("MSFT", "footnote_msft_q3_fy26.txt"),
        ("AMZN", "footnote_amzn_q1_2026.txt"),
    ):
        footnotes[issuer] = (FIXTURES_DIR / filename).read_text(encoding="utf-8")
    df = compare_issuers(footnotes)
    table = Table(title="Disclosure quality — fixture comparison")
    for col in df.columns:
        table.add_column(col)
    for _, row in df.iterrows():
        table.add_row(*[str(row[c]) for c in df.columns])
    console.print(table)


@backtest_app.command("run")
def backtest_run(
    holding_days: int = typer.Option(30, help="Trading days to hold post-event."),
    lab: str = typer.Option("anthropic", help="Filter events by lab: anthropic / openai / all."),
    output: Path = typer.Option(  # noqa: B008
        Path("data/backtest_results.csv"), help="Output CSV with per-trade rows."
    ),
    strategies: str = typer.Option(
        "both",
        help="Which strategies to run: 'long', 'pairs', or 'both'.",
    ),
    refresh: bool = typer.Option(
        False, "--refresh", help="Force a fresh yfinance fetch (skip cache)."
    ),
) -> None:
    """Run cross-wrapper arbitrage backtest against live yfinance data."""
    from datetime import timedelta

    from bigtech_ai_stakes.backtest.core import (
        run_cross_wrapper_strategy,
        run_event_drift_strategy,
    )
    from bigtech_ai_stakes.backtest.prices import load_returns

    df_events = load_events()
    if lab.lower() != "all":
        df_events = df_events[df_events["lab"].str.lower() == lab.lower()]
    if df_events.empty:
        console.print("[red]no events selected[/red]")
        raise typer.Exit(1)

    earliest = df_events["announcement_date"].min().date() - timedelta(days=400)
    latest = df_events["announcement_date"].max().date() + timedelta(days=holding_days + 10)

    tickers = ["GOOGL", "AMZN", "MSFT", "NVDA", "SPY"]
    console.print(f"[bold]Loading returns[/bold] for {tickers} from {earliest} to {latest} ...")
    panel = load_returns(tickers, earliest, latest, force_refresh=refresh)
    console.print(f"  loaded {len(panel)} trading days")

    summaries: list = []
    if strategies in ("long", "both"):
        s_long = run_event_drift_strategy(df_events, panel, holding_window=(1, holding_days))
        summaries.append(s_long)
    if strategies in ("pairs", "both"):
        s_pair = run_cross_wrapper_strategy(df_events, panel, holding_window=(1, holding_days))
        summaries.append(s_pair)

    output.parent.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, object]] = []
    for summary in summaries:
        for t in summary.trades:
            rows.append(
                {
                    "strategy": summary.strategy,
                    "event_id": t.event_id,
                    "event_date": t.event_date,
                    "lab": t.lab,
                    "wrapper": t.wrapper,
                    "direction": t.direction,
                    "stake_pct": t.stake_pct,
                    "market_cap_billion": t.market_cap_billion,
                    "expected_return_announce": t.expected_return_announce,
                    "actual_return_announce": t.actual_return_announce,
                    "holding_period_return": t.holding_period_return,
                    "benchmark_return": t.benchmark_return,
                    "abnormal_return": t.abnormal_return,
                    "notes": t.notes,
                }
            )
    if rows:
        import pandas as pd

        pd.DataFrame(rows).to_csv(output, index=False)
        console.print(f"[green]wrote {len(rows)} trade rows to {output}[/green]")

    for summary in summaries:
        table = Table(title=f"Backtest summary - {summary.strategy} (holding {holding_days}d)")
        for col in (
            "metric",
            "value",
        ):
            table.add_column(col)
        table.add_row("n_trades", str(int(summary.n_trades)))
        table.add_row("mean_abnormal_return", f"{summary.mean_abnormal_return:.4f}")
        table.add_row("median_abnormal_return", f"{summary.median_abnormal_return:.4f}")
        table.add_row("win_rate", f"{summary.win_rate:.2%}")
        table.add_row("sharpe_annualized", f"{summary.sharpe_annualized:.2f}")
        table.add_row("max_drawdown", f"{summary.max_drawdown:.2%}")
        table.add_row("total_pnl", f"{summary.total_pnl:.2%}")
        console.print(table)


@app.command()
def dashboard(
    print_only: bool = typer.Option(
        False, "--print-only", help="Print the launch command without exec'ing it."
    ),
) -> None:
    """Launch the Streamlit dashboard."""
    repo_root = Path(__file__).resolve().parents[2]
    app_path = repo_root / "streamlit_app.py"
    if not app_path.exists():
        raise typer.BadParameter(f"streamlit_app.py not found at {app_path}")
    args = [
        "uv",
        "run",
        "--extra",
        "dashboard",
        "--extra",
        "analysis",
        "streamlit",
        "run",
        str(app_path),
    ]
    if print_only:
        console.print("Run: [bold]" + " ".join(args) + "[/bold]")
        return
    console.print(f"Launching Streamlit dashboard from {app_path} ...")
    os.execvp(args[0], args)


if __name__ == "__main__":
    app()
