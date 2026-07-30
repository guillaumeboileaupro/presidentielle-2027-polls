from __future__ import annotations

import unicodedata

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from presidentielle2027.analytics.adjustment_core import build_polynomial_curve, select_auto_polynomial_degree
from presidentielle2027.analytics.trends import build_lowess_curve
from presidentielle2027.dashboard.colors import get_political_color
from presidentielle2027.dashboard.plot_theme import PLOT_LAYOUT_THEME
from presidentielle2027.dashboard.views.first_round_raw import GITLAB_LOESS_SPANS


CANDIDATE_SPECS = [
    ("Arthaud — LO", "LO", ("arthaud",), "solid"),
    ("Mélenchon — LFI", "LFI", ("melenchon",), "solid"),
    ("Roussel — PCF", "PCF", ("roussel",), "solid"),
    ("Tondelier — EELV", "EELV", ("tondelier",), "solid"),
    ("Faure — PS", "PS", ("faure",), "solid"),
    ("Hollande — PS", "PS", ("hollande",), "dash"),
    ("Glucksmann — PP", "PP", ("glucksmann",), "solid"),
    ("Attal — RE", "RE", ("attal",), "solid"),
    ("Philippe — HOR", "HOR", ("philippe",), "solid"),
    ("Retailleau — LR", "LR", ("retailleau",), "solid"),
    ("Villepin — LFH", "LFH", ("villepin",), "solid"),
    ("Dupont-Aignan — DLF", "DLF", ("dupont-aignan", "dupont aignan"), "solid"),
    ("Bardella — RN", "RN", ("bardella",), "dash"),
    ("Le Pen — RN", "RN", ("le pen",), "solid"),
    ("Zemmour — REC", "REC", ("zemmour",), "solid"),
]


def _normalize_text(value: object) -> str:
    text = "" if value is None or pd.isna(value) else str(value)
    normalized = unicodedata.normalize("NFKD", text)
    normalized = "".join(char for char in normalized if not unicodedata.combining(char))
    return " ".join(normalized.lower().replace("’", "'").split())


def _candidate_mask(frame: pd.DataFrame, aliases: tuple[str, ...]) -> pd.Series:
    names = frame["candidate_name"].map(_normalize_text)
    normalized_aliases = tuple(_normalize_text(alias) for alias in aliases)
    return names.map(lambda name: any(alias in name for alias in normalized_aliases))


def _select_primary_scenarios(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty or "scenario_name" not in frame.columns or "poll_id" not in frame.columns:
        return frame
    ranking = (
        frame.groupby(["poll_id", "scenario_name"], dropna=False)
        .agg(
            candidate_count=("candidate_name", "nunique"),
            party_count=("candidate_party", "nunique"),
            total_score=("estimate_percent", "sum"),
        )
        .reset_index()
        .sort_values(
            ["poll_id", "candidate_count", "party_count", "total_score", "scenario_name"],
            ascending=[True, False, False, False, True],
        )
    )
    primary = ranking.groupby("poll_id", dropna=False).head(1)[["poll_id", "scenario_name"]]
    return frame.merge(primary, on=["poll_id", "scenario_name"], how="inner")


def _build_candidate_curve(frame: pd.DataFrame, party: str) -> pd.DataFrame | None:
    trend_method = str(st.session_state.get("first_round_trend_method", "Régression locale (LOESS)"))
    polynomial_order = int(st.session_state.get("first_round_polynomial_order", 4))

    if trend_method == "Polynôme auto":
        resolved_order = select_auto_polynomial_degree(
            frame,
            "estimate_percent",
            max_degree=polynomial_order,
        )
        return build_polynomial_curve(
            frame,
            "estimate_percent",
            degree=resolved_order,
        )

    loess_frac = GITLAB_LOESS_SPANS.get(party, 0.25)
    method = (
        "loess"
        if trend_method == "Régression locale (LOESS)"
        else ("bins" if trend_method == "Classes temporelles" else "polynomial")
    )
    return build_lowess_curve(
        frame,
        "estimate_percent",
        frac=loess_frac,
        degree=polynomial_order,
        method=method,
    )


def _add_candidate_trace(
    figure: go.Figure,
    frame: pd.DataFrame,
    *,
    label: str,
    party: str,
    dash: str,
) -> None:
    ordered = frame.sort_values("publication_date").dropna(subset=["publication_date", "estimate_percent"])
    if ordered.empty:
        return

    color = get_political_color(party, None)
    figure.add_trace(
        go.Scatter(
            x=ordered["publication_date"],
            y=ordered["estimate_percent"],
            mode="markers",
            marker={"size": 7, "color": color, "opacity": 0.8, "line": {"color": "#ffffff", "width": 1.0}},
            name=f"{label} - points",
            legendgroup=label,
            showlegend=False,
            customdata=ordered[["polling_company", "sample_size"]].to_numpy(),
            hovertemplate=(
                "%{x|%d/%m/%Y}<br>%{y:.1f}%<br>Institut: %{customdata[0]}"
                "<br>Échantillon: %{customdata[1]}<extra></extra>"
            ),
        )
    )

    curve = _build_candidate_curve(ordered, party)
    if curve is None or curve.empty:
        return

    figure.add_trace(
        go.Scatter(
            x=curve["publication_date"],
            y=curve["score_smooth"],
            mode="lines",
            line={"width": 2.6, "color": color, "dash": dash},
            name=label,
            legendgroup=label,
            showlegend=True,
            hovertemplate="%{x|%d/%m/%Y}<br>%{y:.1f}%<extra></extra>",
        )
    )


def render_candidate_trace_chart(frame: pd.DataFrame) -> None:
    working = frame.loc[(frame["round"] == "first_round") & (~frame["is_generic_bloc"])].copy()
    working["publication_date"] = pd.to_datetime(working["publication_date"], errors="coerce")
    working["estimate_percent"] = pd.to_numeric(working["estimate_percent"], errors="coerce")
    working = working.dropna(subset=["publication_date", "estimate_percent"])

    pollster = st.session_state.get("first_round_pollster", "Tous")
    if pollster != "Tous":
        working = working.loc[working["polling_company"] == pollster].copy()

    period = st.session_state.get("first_round_period")
    if isinstance(period, tuple) and len(period) == 2:
        working = working.loc[
            working["publication_date"].between(pd.Timestamp(period[0]), pd.Timestamp(period[1]), inclusive="both")
        ].copy()

    working = _select_primary_scenarios(working)
    if working.empty:
        return

    st.markdown("**Évolution par candidat**")
    figure = go.Figure()
    for label, party, aliases, dash in CANDIDATE_SPECS:
        current = working.loc[_candidate_mask(working, aliases)].copy()
        _add_candidate_trace(figure, current, label=label, party=party, dash=dash)

    figure.update_layout(
        title="Sondages 2027 · candidats",
        xaxis_title="Date de publication",
        yaxis_title="Intentions de vote (%)",
        **PLOT_LAYOUT_THEME,
    )
    figure.update_layout(legend={**PLOT_LAYOUT_THEME["legend"], "traceorder": "normal"})
    figure.update_yaxes(ticksuffix=" %")
    st.plotly_chart(
        figure,
        width="stretch",
        key="first_round_candidate_trace_chart",
        config={"displayModeBar": False, "responsive": True},
    )
