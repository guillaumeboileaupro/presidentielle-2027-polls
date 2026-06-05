from __future__ import annotations

from datetime import date
import inspect
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from presidentielle2027.analytics.historical_corrections import apply_first_round_historical_correction, get_reference_dir
from presidentielle2027.analytics.historical_corrections import CURRENT_ELECTION_DATE
from presidentielle2027.analytics.trends import build_lowess_curve, exploratory_extension
from presidentielle2027.dashboard.colors import get_political_color
from presidentielle2027.dashboard.plot_theme import PLOT_LAYOUT_THEME


def _supports_clip_upper() -> bool:
    try:
        return "clip_upper" in inspect.signature(exploratory_extension).parameters
    except (TypeError, ValueError):
        return False


def render_projection_scenarios_page(frame: pd.DataFrame) -> None:
    st.subheader("Scénarios exploratoires")
    st.caption("Scénario exploratoire fondé sur la dynamique récente lissée. Ce n’est pas une prédiction électorale validée.")

    working = frame.loc[(frame["round"] == "first_round") & (~frame["is_generic_bloc"])].copy()
    if working.empty:
        st.info("Aucune donnée disponible.")
        return
    if "source_url" not in working.columns:
        working["source_url"] = pd.NA

    scenarios = ["Tous"] + sorted(working["scenario_name"].dropna().astype(str).unique().tolist())
    blocs = ["Tous"] + sorted(working["political_family"].dropna().astype(str).unique().tolist())
    pollsters = ["Tous"] + sorted(working["polling_company"].dropna().astype(str).unique().tolist())
    min_date = working["publication_date"].min().date() if working["publication_date"].notna().any() else date.today()
    max_date = working["publication_date"].max().date() if working["publication_date"].notna().any() else date.today()

    c1, c2, c3 = st.columns(3)
    scenario = c1.selectbox("Scénario", scenarios, key="projection_scenario")
    bloc = c2.selectbox("Bloc politique", blocs, key="projection_bloc")
    pollster = c3.selectbox("Institut", pollsters, key="projection_pollster")

    filtered = working.copy()
    if scenario != "Tous":
        filtered = filtered.loc[filtered["scenario_name"] == scenario]
    if bloc != "Tous":
        filtered = filtered.loc[filtered["political_family"] == bloc]
    if pollster != "Tous":
        filtered = filtered.loc[filtered["polling_company"] == pollster]

    parties = ["Tous"] + sorted(filtered["candidate_party"].dropna().astype(str).unique().tolist())
    party = st.selectbox("Parti", parties, key="projection_party")
    if party != "Tous":
        filtered = filtered.loc[filtered["candidate_party"] == party]

    candidate_options = sorted(filtered["candidate_name"].dropna().astype(str).unique().tolist())
    default_candidates = candidate_options[:4]
    c4, c5, c6, c7, c8 = st.columns([0.8, 1.2, 0.8, 0.8, 0.8])
    display_mode = c4.selectbox("Vue", ["Brut", "Corrigé 2027"], key="projection_mode")
    period = c5.date_input("Période", value=(min_date, max_date), min_value=min_date, max_value=max_date, key="projection_period")
    trend_method = c6.selectbox("Modèle", ["Polynomial", "Bins"], index=0, key="projection_trend_method")
    polynomial_order = c7.selectbox("Ordre", [1, 2, 3, 4, 5, 6], index=3, key="projection_polynomial_order")
    show_extension = c8.checkbox(
        "Pointillé",
        value=True,
        key="projection_extension",
    )

    if isinstance(period, tuple) and len(period) == 2:
        filtered = filtered.loc[
            filtered["publication_date"].between(pd.Timestamp(period[0]), pd.Timestamp(period[1]), inclusive="both")
        ]
        period_start_ts = pd.Timestamp(period[0])
        period_end_ts = pd.Timestamp(period[1])
    else:
        period_start_ts = pd.Timestamp(min_date)
        period_end_ts = pd.Timestamp(max_date)
    selected_candidates = st.multiselect("Candidats", candidate_options, default=default_candidates, key="projection_candidates")
    if selected_candidates:
        filtered = filtered.loc[filtered["candidate_name"].isin(selected_candidates)]
    if filtered.empty:
        st.info("Aucune donnée pour ces filtres.")
        return

    value_column = "estimate_percent"
    if display_mode == "Corrigé 2027":
        filtered, _ = apply_first_round_historical_correction(filtered, get_reference_dir(Path.cwd()))
        value_column = "historically_corrected_estimate"

    grouped = (
        filtered.groupby(["publication_date", "candidate_name"], dropna=False)
        .agg(
            estimate_value=(value_column, "mean"),
            candidate_party=("candidate_party", "first"),
            political_family=("political_family", "first"),
            source_url=("source_url", "first"),
        )
        .reset_index()
        .sort_values(["candidate_name", "publication_date"])
    )
    figure = go.Figure()
    insufficient: list[str] = []
    supports_clip_upper = _supports_clip_upper()
    for candidate_name, group in grouped.groupby("candidate_name", dropna=False):
        ordered = group.sort_values("publication_date")
        party_name = ordered["candidate_party"].dropna().iloc[0] if ordered["candidate_party"].notna().any() else None
        family = ordered["political_family"].dropna().iloc[0] if ordered["political_family"].notna().any() else None
        color = get_political_color(party_name, family)
        figure.add_trace(
            go.Scatter(
                x=ordered["publication_date"],
                y=ordered["estimate_value"],
                mode="markers",
                marker={"size": 6, "color": color, "opacity": 0.35},
                name=f"{candidate_name} - points",
                legendgroup=str(candidate_name),
                showlegend=False,
                hovertemplate=f"{candidate_name}<br>%{{x|%d/%m/%Y}}<br>%{{y:.1f}}%<extra></extra>",
            )
        )
        smoothed = build_lowess_curve(
            ordered.rename(columns={"estimate_value": "estimate_percent"}),
            "estimate_percent",
            frac=0.30,
            degree=polynomial_order,
            method="bins" if trend_method == "Bins" else "polynomial",
        )
        if smoothed is None:
            insufficient.append(str(candidate_name))
        else:
            figure.add_trace(
                go.Scatter(
                    x=smoothed["publication_date"],
                    y=smoothed["score_smooth"],
                    mode="lines",
                    line={"width": 2.8, "color": color},
                    name=str(candidate_name),
                    legendgroup=str(candidate_name),
                    showlegend=True,
                    hovertemplate=f"{candidate_name}<br>%{{x|%d/%m/%Y}}<br>%{{y:.1f}}%<extra></extra>",
                )
            )
        if show_extension:
            extension_kwargs = {
                "frame": ordered.rename(columns={"estimate_value": "estimate_percent"}),
                "election_date": CURRENT_ELECTION_DATE,
                "value_column": "estimate_percent",
                "recent_days": 30,
                "degree": polynomial_order,
                "method": "bins" if trend_method == "Bins" else "polynomial",
            }
            if supports_clip_upper:
                extension_kwargs["clip_upper"] = None
            extension = exploratory_extension(**extension_kwargs)
            if extension is not None:
                figure.add_trace(
                    go.Scatter(
                        x=extension.x,
                        y=extension.y,
                        mode="lines",
                        line={"width": 1.8, "color": color, "dash": "dot"},
                        name=f"{candidate_name} - prolongation",
                        legendgroup=str(candidate_name),
                        showlegend=False,
                        hovertemplate="Prolongation exploratoire<br>%{x|%d/%m/%Y}<br>%{y:.1f}%<extra></extra>",
                    )
                )
                figure.add_trace(
                    go.Scatter(
                        x=list(extension.x) + list(extension.x[::-1]),
                        y=list(extension.upper) + list(extension.lower[::-1]),
                        fill="toself",
                        fillcolor=color.replace(")", ", 0.10)") if color.startswith("rgba(") else "rgba(120,120,120,0.10)",
                        line={"color": "rgba(255,255,255,0)"},
                        hoverinfo="skip",
                        showlegend=False,
                        legendgroup=str(candidate_name),
                    )
                )
    title_suffix = "corrigé 2027" if display_mode == "Corrigé 2027" else "brut"
    model_label = "modèle par bins" if trend_method == "Bins" else f"ajustement polynomial d'ordre {polynomial_order}"
    figure.update_layout(
        title=f"Points bruts, {model_label} et scénario exploratoire {title_suffix}",
        xaxis_title="Date de publication",
        yaxis_title="Intentions de vote (%)",
        **PLOT_LAYOUT_THEME,
    )
    chart_end_ts = max(period_end_ts, CURRENT_ELECTION_DATE) if show_extension else period_end_ts
    figure.update_xaxes(range=[period_start_ts, chart_end_ts])
    figure.update_yaxes(ticksuffix=" %")
    st.plotly_chart(figure, width="stretch", config={"displayModeBar": False, "responsive": True})
    if insufficient:
        st.info("Tendance non calculée pour certaines séries : données insuffisantes ou scénarios non comparables.")
