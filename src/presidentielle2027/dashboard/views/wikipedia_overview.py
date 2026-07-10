from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from presidentielle2027.analytics.trends import build_lowess_curve
from presidentielle2027.dashboard.colors import get_political_color
from presidentielle2027.dashboard.plot_theme import PLOT_LAYOUT_THEME


DEFAULT_PARTIES = ["PCF", "LFI", "ECO", "PS", "ENS", "LR", "RN", "REC"]
DEFAULT_CANDIDATES = [
    ("Arlette Arthaud", "LO", "Arthaud – LO"),
    ("Jean-Luc Mélenchon", "LFI", "Mélenchon – LFI"),
    ("Fabien Roussel", "PCF", "Roussel – PCF"),
    ("Marine Tondelier", "LE", "Tondelier – LE"),
    ("Olivier Faure", "PS", "Faure – PS"),
    ("François Hollande", "PS", "Hollande – PS"),
    ("Raphaël Glucksmann", "PP", "Glucksmann – PP"),
    ("Gabriel Attal", "RE", "Attal – RE"),
    ("Édouard Philippe", "HOR", "Philippe – HOR"),
    ("Bruno Retailleau", "LR", "Retailleau – LR"),
    ("Dominique de Villepin", "LFH", "Villepin – LFH"),
    ("Nicolas Dupont-Aignan", "DLF", "Dupont-Aignan – DLF"),
    ("Jordan Bardella", "RN", "Bardella – RN"),
    ("Marine Le Pen", "RN", "Le Pen – RN"),
    ("Éric Zemmour", "REC", "Zemmour – REC"),
]

PARTY_STORAGE_ALIASES = {
    "ECO": {"ECO", "EELV", "LE"},
    "ENS": {"ENS", "RE", "HOR", "MODEM", "MoDem"},
}

CANDIDATE_PARTY_COLORS = {
    "LO": "#9b0000",
    "LFI": "#d7193f",
    "PCF": "#d50000",
    "LE": "#16a34a",
    "PS": "#ff7373",
    "PP": "#ffb2b2",
    "RE": "#ffd700",
    "HOR": "#1515b8",
    "LR": "#0072b2",
    "LFH": "#a9c7ff",
    "DLF": "#0070a8",
    "RN": "#123f91",
    "REC": "#444444",
}


def _party_mask(frame: pd.DataFrame, display_party: str) -> pd.Series:
    aliases = PARTY_STORAGE_ALIASES.get(display_party, {display_party})
    return frame["candidate_party"].fillna("").astype(str).isin(aliases)


def _add_poll_series(
    figure: go.Figure,
    group: pd.DataFrame,
    *,
    display_name: str,
    color: str,
    dash: str = "solid",
) -> None:
    ordered = group.sort_values("publication_date")
    if ordered.empty:
        return
    figure.add_trace(
        go.Scatter(
            x=ordered["publication_date"],
            y=ordered["estimate_percent"],
            mode="markers",
            marker={"size": 5, "color": color, "opacity": 0.45},
            name=f"{display_name} – points",
            legendgroup=display_name,
            showlegend=False,
            customdata=ordered[["polling_company", "sample_size"]].to_numpy(),
            hovertemplate=(
                "%{x|%d/%m/%Y}<br>%{y:.1f}%"
                "<br>Institut : %{customdata[0]}"
                "<br>Échantillon : %{customdata[1]}<extra></extra>"
            ),
        )
    )
    smoothed = build_lowess_curve(
        ordered,
        "estimate_percent",
        frac=0.30,
        degree=4,
        method="polynomial",
    )
    if smoothed is None:
        return
    figure.add_trace(
        go.Scatter(
            x=smoothed["publication_date"],
            y=smoothed["score_smooth"],
            mode="lines",
            line={"width": 2.5, "color": color, "dash": dash},
            name=display_name,
            legendgroup=display_name,
            hovertemplate="%{x|%d/%m/%Y}<br>%{y:.1f}%<extra></extra>",
        )
    )


def _finish_figure(figure: go.Figure, title: str) -> None:
    figure.update_layout(
        title=title,
        xaxis_title="Date",
        yaxis_title="Intentions de vote (%)",
        legend={"orientation": "v", "x": 1.01, "y": 1.0, "xanchor": "left", "yanchor": "top"},
        **PLOT_LAYOUT_THEME,
    )
    figure.update_yaxes(ticksuffix="%", rangemode="tozero")
    figure.add_vline(x=pd.Timestamp("2022-04-10"), line_width=1, line_color="#999999", opacity=0.6)
    figure.add_vline(x=pd.Timestamp("2027-04-11"), line_width=1, line_color="#999999", opacity=0.6)


def _render_party_chart(first_round: pd.DataFrame) -> None:
    st.markdown("### Évolution par parti politique")
    available = [party for party in DEFAULT_PARTIES if _party_mask(first_round, party).any()]
    selected = st.multiselect(
        "Partis affichés",
        DEFAULT_PARTIES,
        default=available,
        key="wiki_default_parties",
    )
    figure = go.Figure()
    for party in selected:
        group = first_round.loc[_party_mask(first_round, party)].copy()
        if group.empty:
            continue
        grouped = (
            group.groupby("publication_date", dropna=False)
            .agg(
                estimate_percent=("estimate_percent", "mean"),
                polling_company=("polling_company", "first"),
                sample_size=("sample_size", "mean"),
            )
            .reset_index()
        )
        storage_party = group["candidate_party"].dropna().astype(str).iloc[0]
        family = group["political_family"].dropna().astype(str).iloc[0] if group["political_family"].notna().any() else None
        _add_poll_series(
            figure,
            grouped,
            display_name=party,
            color=get_political_color(storage_party, family),
        )
    _finish_figure(figure, "Sondages du premier tour par parti")
    st.plotly_chart(figure, width="stretch", config={"displayModeBar": False, "responsive": True})


def _render_candidate_chart(first_round: pd.DataFrame) -> None:
    st.markdown("### Évolution par candidat")
    labels = [label for _, _, label in DEFAULT_CANDIDATES]
    available_labels = [
        label
        for candidate, _, label in DEFAULT_CANDIDATES
        if first_round["candidate_name"].fillna("").astype(str).eq(candidate).any()
    ]
    selected_labels = st.multiselect(
        "Candidats affichés",
        labels,
        default=available_labels,
        key="wiki_default_candidates",
    )
    figure = go.Figure()
    for candidate, display_party, label in DEFAULT_CANDIDATES:
        if label not in selected_labels:
            continue
        group = first_round.loc[first_round["candidate_name"].fillna("").astype(str) == candidate].copy()
        if group.empty:
            continue
        dash = "dash" if candidate == "Jordan Bardella" else "solid"
        _add_poll_series(
            figure,
            group,
            display_name=label,
            color=CANDIDATE_PARTY_COLORS[display_party],
            dash=dash,
        )
    _finish_figure(figure, "Sondages du premier tour par candidat")
    st.plotly_chart(figure, width="stretch", config={"displayModeBar": False, "responsive": True})


def render_wikipedia_overview_page(frame: pd.DataFrame) -> None:
    st.subheader("Sondages présidentielle 2027")
    st.caption(
        "Vue de référence calée sur les deux lectures Wikipédia : partis puis candidats. "
        "Les points représentent les sondages publiés et les courbes leur tendance lissée."
    )
    first_round = frame.loc[(frame["round"] == "first_round") & (~frame["is_generic_bloc"])].copy()
    if first_round.empty:
        st.info("Aucune donnée de premier tour exploitable.")
        return
    _render_party_chart(first_round)
    _render_candidate_chart(first_round)
