"""Streamlit dashboard for bigtech-ai-stakes.

Run locally::

    uv run --extra dashboard --extra analysis streamlit run streamlit_app.py

Or via the CLI shortcut::

    uv run bigtech-ai-stakes dashboard
"""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from bigtech_ai_stakes import __version__
from bigtech_ai_stakes.dashboard.data import (
    FIXTURES_CATALOG,
    LOOKTHROUGH_PRESETS,
    load_extracted,
    load_fixture,
)
from bigtech_ai_stakes.data import load_events, load_stakes
from bigtech_ai_stakes.disclosure.core import compare_issuers, score_disclosure
from bigtech_ai_stakes.disclosure.rubric import CRITERIA, MAX_SCORE
from bigtech_ai_stakes.lookthrough.core import (
    LookThroughInputs,
    default_scenarios,
    evaluate_scenarios,
    look_through,
)

st.set_page_config(
    page_title="bigtech-ai-stakes",
    layout="wide",
    initial_sidebar_state="expanded",
)


@st.cache_data
def _events() -> pd.DataFrame:
    return load_events()


@st.cache_data
def _stakes() -> pd.DataFrame:
    return load_stakes()


@st.cache_data
def _extracted() -> pd.DataFrame:
    return load_extracted()


@st.cache_data
def _fixture(name: str) -> str:
    return load_fixture(name)


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------
with st.sidebar:
    st.title("bigtech-ai-stakes")
    st.caption(f"v{__version__}")
    st.markdown(
        "[GitHub repo](https://github.com/YichengYang-Ethan/bigtech-ai-stakes)"
        "  ·  [Methodology](https://github.com/YichengYang-Ethan/"
        "bigtech-ai-stakes/blob/main/docs/methodology.md)"
    )
    st.divider()
    st.markdown("**Data sources**")
    st.caption("- SEC EDGAR (10-K / 10-Q / 8-K)")
    st.caption("- Court records (US v. Google)")
    st.caption("- Company press releases")
    st.divider()
    st.markdown("**Confidence flags**")
    st.caption("V — verified by primary source")
    st.caption("P — multi-source secondary")
    st.caption("S — single-source speculative")
    st.divider()
    st.caption("Research output, not investment advice.")


tab_overview, tab_panel, tab_lt, tab_disc, tab_about = st.tabs(
    [
        "Overview",
        "Stake panel",
        "Look-through EPS",
        "Disclosure scorer",
        "About",
    ]
)


# ---------------------------------------------------------------------------
# Tab 1 — Overview
# ---------------------------------------------------------------------------
with tab_overview:
    st.header("AI-lab equity-stake dashboard")
    st.caption(
        "Public-company markups of private AI-lab investments, "
        "tracked from primary SEC filings and press releases."
    )

    extracted = _extracted()
    if extracted.empty:
        st.warning(
            "No machine-extracted data found. "
            "Run `uv run python scripts/run_live_extraction.py` to populate."
        )
    else:
        c1, c2, c3, c4 = st.columns(4)

        googl_cv = extracted[
            (extracted["ticker"] == "GOOGL") & extracted["carrying_value_billion"].notna()
        ].sort_values("filing_date", ascending=False)
        if not googl_cv.empty:
            row = googl_cv.iloc[0]
            c1.metric(
                "GOOGL non-mkt equity",
                f"${row['carrying_value_billion']:.1f}B",
                help=f"as of {row['filing_date'].date()}",
            )

        msft_stake = extracted[
            (extracted["ticker"] == "MSFT") & extracted["stake_pct"].notna()
        ].sort_values("filing_date", ascending=False)
        if not msft_stake.empty:
            row = msft_stake.iloc[0]
            c2.metric(
                "MSFT - OpenAI stake",
                f"{row['stake_pct']:.1f}%",
                help=f"as of {row['filing_date'].date()}",
            )

        msft_funded = extracted[
            (extracted["ticker"] == "MSFT") & extracted["funded_to_date_billion"].notna()
        ].sort_values("filing_date", ascending=False)
        if not msft_funded.empty:
            row = msft_funded.iloc[0]
            c3.metric(
                "MSFT funded to date",
                f"${row['funded_to_date_billion']:.1f}B",
                help=f"of {row['funding_commitment_billion']:.0f}B committed",
            )

        amzn_gain = extracted[
            (extracted["ticker"] == "AMZN") & extracted["pretax_gain_quarter_billion"].notna()
        ].sort_values("filing_date", ascending=False)
        if not amzn_gain.empty:
            row = amzn_gain.iloc[0]
            c4.metric(
                "AMZN Anthropic gain",
                f"${row['pretax_gain_quarter_billion']:.1f}B",
                help=f"{row['form']} {row['filing_date'].date()}",
            )

        st.divider()

        if not googl_cv.empty:
            chart_df = googl_cv[["filing_date", "carrying_value_billion"]].sort_values(
                "filing_date"
            )
            fig = px.line(
                chart_df,
                x="filing_date",
                y="carrying_value_billion",
                markers=True,
                title="GOOGL non-marketable equity carrying value (USD bn)",
            )
            fig.update_layout(
                yaxis_title="USD billions",
                xaxis_title="filing date",
                height=380,
            )
            st.plotly_chart(fig, use_container_width=True)
            st.caption(
                "From primary 10-Q / 10-K disclosures. Includes Anthropic + other "
                "non-marketable holdings (Alphabet does not name investees in "
                "financial-statement notes)."
            )

        with st.expander("Recent extraction summary"):
            summary = (
                extracted.groupby("ticker")
                .agg(
                    total_filings=("anchor_hit", "size"),
                    anchor_hits=("anchor_hit", "sum"),
                )
                .reset_index()
            )
            st.dataframe(summary, use_container_width=True)


# ---------------------------------------------------------------------------
# Tab 2 — Stake panel
# ---------------------------------------------------------------------------
with tab_panel:
    st.header("Stake panel")
    extracted = _extracted()
    curated = _stakes()

    col1, col2 = st.columns(2)
    with col1:
        unique_tickers = (
            sorted(extracted["ticker"].unique().tolist()) if not extracted.empty else []
        )
        ticker_options = ["All", *unique_tickers]
        ticker_filter = st.selectbox("Issuer", options=ticker_options)
    with col2:
        view = st.radio(
            "Source",
            ["Both", "Machine-extracted (V)", "Curated (V/P/S)"],
            horizontal=True,
        )

    if view in ("Both", "Machine-extracted (V)") and not extracted.empty:
        df = extracted.copy()
        if ticker_filter != "All":
            df = df[df["ticker"] == ticker_filter]
        df = df[df["anchor_hit"]].copy()
        st.subheader(f"Machine-extracted ({len(df)} rows)")
        cols = [
            "ticker",
            "form",
            "filing_date",
            "investees",
            "carrying_value_billion",
            "stake_pct",
            "funding_commitment_billion",
            "funded_to_date_billion",
            "pretax_gain_quarter_billion",
        ]
        st.dataframe(df[cols], use_container_width=True, hide_index=True)

        # Time-series chart per ticker for carrying_value_billion or stake_pct
        if not df.empty and ticker_filter != "All":
            t = ticker_filter
            cv_series = df[df["carrying_value_billion"].notna()].sort_values("filing_date")
            if not cv_series.empty:
                fig = px.line(
                    cv_series,
                    x="filing_date",
                    y="carrying_value_billion",
                    markers=True,
                    title=f"{t} carrying value over time (USD bn)",
                )
                st.plotly_chart(fig, use_container_width=True)
            stake_series = df[df["stake_pct"].notna()].sort_values("filing_date")
            if not stake_series.empty:
                fig = px.line(
                    stake_series,
                    x="filing_date",
                    y="stake_pct",
                    markers=True,
                    title=f"{t} disclosed stake percentage over time",
                )
                fig.update_layout(yaxis_title="stake (%)")
                st.plotly_chart(fig, use_container_width=True)

    if view in ("Both", "Curated (V/P/S)"):
        df = curated.copy()
        if ticker_filter != "All":
            df = df[df["investor_ticker"] == ticker_filter]
        st.subheader(f"Curated snapshots ({len(df)} rows)")
        st.dataframe(df, use_container_width=True, hide_index=True)


# ---------------------------------------------------------------------------
# Tab 3 — Look-through EPS
# ---------------------------------------------------------------------------
with tab_lt:
    st.header("Look-through EPS calculator")
    st.caption(
        "Strip AI-stake markups from reported earnings. "
        "Bottom-up uses inferred stake * dV_post; "
        "top-down uses disclosed pre-tax gain * (1 - tax)."
    )

    preset_labels = ["Custom"] + [p.label for p in LOOKTHROUGH_PRESETS]
    selected_preset = st.selectbox("Preset", preset_labels)
    preset = next((p for p in LOOKTHROUGH_PRESETS if p.label == selected_preset), None)

    c1, c2 = st.columns(2)
    with c1:
        ticker = st.text_input("Issuer ticker", value=preset.ticker if preset else "")
        quarter = st.text_input("Quarter", value=preset.quarter if preset else "")
        gaap_ni = st.number_input(
            "GAAP net income (USD bn)",
            value=float(preset.gaap_ni) if preset else 0.0,
        )
        shares = st.number_input(
            "Shares outstanding (bn)",
            value=float(preset.shares) if preset else 1.0,
            min_value=0.001,
        )
    with c2:
        stake_pct = st.number_input(
            "Stake (%)",
            value=float(preset.stake_pct) if preset else 0.0,
            min_value=0.0,
            max_value=100.0,
        )
        delta_v = st.number_input(
            "ΔV_post (USD bn) — bottom-up",
            value=float(preset.delta_v_post) if preset else 0.0,
        )
        investee_ni = st.number_input(
            "Investee NI for the quarter (USD bn)",
            value=float(preset.investee_ni) if preset else 0.0,
        )
        use_pretax = st.checkbox(
            "Use disclosed pre-tax gain (top-down)",
            value=preset is not None and preset.pretax_gain is not None,
        )
        pretax_gain = st.number_input(
            "Disclosed pre-tax gain (USD bn)",
            value=float(preset.pretax_gain) if (preset and preset.pretax_gain) else 0.0,
            disabled=not use_pretax,
        )
        tax_rate = st.number_input(
            "Tax rate",
            value=0.21,
            min_value=0.0,
            max_value=0.5,
            step=0.01,
            disabled=not use_pretax,
        )

    inputs = LookThroughInputs(
        issuer_ticker=ticker.upper() or "X",
        quarter=quarter or "?",
        gaap_net_income_billion=gaap_ni,
        shares_outstanding_billion=shares,
        stake_pct=stake_pct,
        delta_v_post_billion=delta_v,
        investee_net_income_billion=investee_ni,
        disclosed_pretax_gain_billion=pretax_gain if use_pretax else None,
        tax_rate=tax_rate if use_pretax else 0.21,
    )

    result = look_through(inputs)
    m1, m2, m3 = st.columns(3)
    m1.metric("GAAP EPS", f"${result.gaap_eps:.3f}")
    m2.metric(
        "Look-through EPS",
        f"${result.look_through_eps:.3f}",
        delta=f"{result.look_through_eps - result.gaap_eps:+.3f}",
    )
    m3.metric(
        "EPS drag (USD bn)", f"${result.eps_drag_billion:.2f}", help=f"method={result.method}"
    )

    fig = go.Figure(
        data=[
            go.Bar(
                x=["GAAP", "Look-through"],
                y=[result.gaap_net_income_billion, result.look_through_net_income_billion],
                marker_color=["#1f77b4", "#ff7f0e"],
                text=[
                    f"${result.gaap_net_income_billion:.1f}B",
                    f"${result.look_through_net_income_billion:.1f}B",
                ],
                textposition="auto",
            )
        ]
    )
    fig.update_layout(
        title=f"Reported vs look-through net income — {ticker.upper() or 'X'} {quarter}",
        yaxis_title="USD billions",
        height=380,
    )
    st.plotly_chart(fig, use_container_width=True)

    st.subheader("Bear / base / bull scenarios on investee NI")
    scenario_results = evaluate_scenarios(inputs, default_scenarios())
    scenario_df = pd.DataFrame(
        [
            {
                "scenario": s.notes.split(";")[0].replace("scenario=", "").strip(),
                "investee_NI_billion": (
                    scenario_results[i].look_through_net_income_billion
                    - inputs.gaap_net_income_billion
                    + (
                        inputs.disclosed_pretax_gain_billion * (1 - inputs.tax_rate)
                        if inputs.disclosed_pretax_gain_billion is not None
                        else inputs.stake_pct / 100.0 * inputs.delta_v_post_billion
                    )
                )
                / max(inputs.stake_pct / 100.0, 1e-9)
                if inputs.stake_pct
                else None,
                "lt_ni_billion": s.look_through_net_income_billion,
                "lt_eps": s.look_through_eps,
            }
            for i, s in enumerate(scenario_results)
        ]
    )
    st.dataframe(scenario_df, use_container_width=True, hide_index=True)
    fig2 = px.bar(
        scenario_df,
        x="scenario",
        y="lt_eps",
        title="Look-through EPS by scenario",
        text="lt_eps",
    )
    fig2.update_traces(texttemplate="$%{text:.3f}", textposition="outside")
    st.plotly_chart(fig2, use_container_width=True)


# ---------------------------------------------------------------------------
# Tab 4 — Disclosure scorer
# ---------------------------------------------------------------------------
with tab_disc:
    st.header("Disclosure-quality scorer")
    st.caption(
        "7-criterion rubric per ASC 321 / 323. Sensitivity to V_post "
        "(criterion 4) is universally zero across issuers — the headline "
        "finding from this rubric."
    )

    footnotes = {label.split()[0]: _fixture(fname) for label, fname in FIXTURES_CATALOG.items()}
    df = compare_issuers(footnotes)

    fig = px.bar(
        df,
        x="issuer",
        y="total",
        title="Disclosure quality total score (max 7)",
        text="total",
    )
    fig.update_traces(textposition="outside")
    fig.update_layout(yaxis_title="total (max 7)", height=380)
    st.plotly_chart(fig, use_container_width=True)

    st.subheader("Per-criterion radar")
    criterion_names = [name for name, _ in CRITERIA]
    fig2 = go.Figure()
    for _, row in df.iterrows():
        values = [row[name] for name in criterion_names]
        # Close the polygon by repeating the first point
        fig2.add_trace(
            go.Scatterpolar(
                r=[*values, values[0]],
                theta=[*criterion_names, criterion_names[0]],
                fill="toself",
                name=row["issuer"],
            )
        )
    fig2.update_layout(
        polar={"radialaxis": {"visible": True, "range": [0, 1]}},
        showlegend=True,
        height=480,
    )
    st.plotly_chart(fig2, use_container_width=True)

    st.subheader("Per-fixture detail")
    selected_label = st.selectbox("Fixture", list(FIXTURES_CATALOG.keys()))
    text = _fixture(FIXTURES_CATALOG[selected_label])
    issuer = selected_label.split()[0]
    detail = score_disclosure(text, issuer=issuer)
    st.metric(
        f"{issuer} total",
        f"{detail.total:.1f} / {MAX_SCORE:.0f}",
        help=f"{detail.total_pct:.0%} of max",
    )
    breakdown = pd.DataFrame(
        [
            {
                "#": c.criterion_id,
                "criterion": c.name,
                "score": c.score,
                "evidence": c.evidence,
            }
            for c in detail.criteria
        ]
    )
    st.dataframe(breakdown, use_container_width=True, hide_index=True)
    with st.expander("Raw footnote text"):
        st.code(text, language="text")


# ---------------------------------------------------------------------------
# Tab 5 — About
# ---------------------------------------------------------------------------
with tab_about:
    st.header("About")
    st.markdown(
        """
**bigtech-ai-stakes** is an open-source quarterly panel and analytics tool for
U.S. public-company equity stakes in **Anthropic** and **OpenAI**, derived from
primary SEC filings (10-K / 10-Q / 8-K), public press releases, and court records.

### What this tracks

- Disclosed fair-value adjustments and carrying values for non-marketable equity
  securities held by GOOGL / AMZN / MSFT / NVDA (+ smaller holders CRM / QCOM / ZM).
- Inferred ownership percentages from ASC 321 / 323 footnote disclosures.
- Look-through earnings stripped of AI-stake markups (Buffett framework adapted).
- 7-criterion disclosure-quality scoring rubric.

### Status

Stages 0 through 2 (data, extraction, analysis modules) are done as of May 2026.
Stage 3 (this dashboard, then quarterly note + SSRN paper template + Zenodo DOI)
is in progress.

Public repo and methodology:
- [github.com/YichengYang-Ethan/bigtech-ai-stakes](https://github.com/YichengYang-Ethan/bigtech-ai-stakes)
- [docs/methodology.md](https://github.com/YichengYang-Ethan/bigtech-ai-stakes/blob/main/docs/methodology.md)
- [docs/disclosure-rubric.md](https://github.com/YichengYang-Ethan/bigtech-ai-stakes/blob/main/docs/disclosure-rubric.md)
- [docs/citations.md](https://github.com/YichengYang-Ethan/bigtech-ai-stakes/blob/main/docs/citations.md)

### License

- Code: MIT
- Data: CC-BY-4.0
- This is research output, **not** investment advice.
"""
    )

    st.subheader("Funding events")
    st.dataframe(
        _events()[
            [
                "event_id",
                "lab",
                "event_type",
                "announcement_date",
                "v_post_billion",
                "raise_amount_billion",
                "lead_investors",
                "confidence",
            ]
        ],
        use_container_width=True,
        hide_index=True,
    )
