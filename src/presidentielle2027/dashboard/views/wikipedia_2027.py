from __future__ import annotations

import unicodedata

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from presidentielle2027.analytics.trends import build_lowess_curve
from presidentielle2027.dashboard.colors import get_political_color
from presidentielle2027.dashboard.plot_theme import PLOT_LAYOUT_THEME
from presidentielle2027.dashboard.table_views import render_poll_results_table


DEFAULT_PARTIES = ["PCF", "LFI", "ECO", "PS", "ENS", "LR", "RN", "REC"]

PARTY_ALIASES: dict[str, set[str]] = {
    "PCF": {"PCF"},
    "LFI": {"LFI"},
    "ECO": {"ECO", "EELV", "LE"},
    "PS": {"PS"},
    "ENS": {"ENS", "RE", "HOR", "MODEM", "MoDem"},
    "LR": {"LR"},
    "RN": {"RN"},
    "REC": {"REC"},
}

CANDIDATE_SPECS = [
    ("Arthaud — LO", "Arlette Arthaud", "LO", ("arthaud",), "solid"),
    ("Mélenchon — LFI", "Jean-Luc Mélenchon", "LFI", ("melenchon",), "solid"),
    ("Roussel — PCF", "Fabien Roussel", "PCF", ("roussel",), "solid"),
    ("Tondelier — LE", "Marine Tondelier", "LE", ("tondelier",), "solid"),
    ("Faure — PS", "Olivier Faure", "PS", ("faure",), "solid"),
    ("Hollande — PS", "François Hollande", "PS", ("hollande",), "dash"),
    ("Glucksmann — PP", "Raphaël Glucksmann", "PP", ("glucksmann",), "solid"),
    ("Attal — RE", "Gabriel Attal", "RE", ("attal",), "solid"),
    ("Philippe — HOR", "Édouard Philippe", "HOR", ("philippe",), "dash"),
    ("Retailleau — LR", "Bruno Retailleau", "LR", ("retailleau",), "solid"),
    ("Villepin — LFH", "Dominique de Villepin", "LFH", ("villepin",), "solid"),
    ("Dupont-Aignan — DLF", "Nicolas Dupont-Aignan", "DLF", ("dupont-aignan", "dupont aignan"), "solid"),
    ("Bardella — RN", "Jordan Bardella", "RN", ("bardella",), "dash"),
    ("Le Pen — RN", "Marine Le Pen", "RN", ("le pen",), "solid"),
    ("Zemmour — REC", "Éric Zemmour", "REC", ("zemmour",), "solid"),
]


def _normalize_text(value: object) -> str:
    text = "" if value is None or pd.isna(value) else str(value)
    normalized = unicodedata.normalize("NFKD", text)
    normalized = "".join(char for char in normalized if not unicodedata.combining(char))
    return " ".join(normalized.lower().replace("’", "'").split())


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


def _build_curve(frame: pd.DataFrame, frac: float = 0.25) -> pd.DataFrame | None:
    ordered = frame.sort_values("publication_date").dropna(subset=["publication_date", "estimate_percent"])
    if ordered.empty:
        return None
    curve = build_lowess_curve(
        ordered,
        "estimate_percent",
        frac=frac,
        degree=3,
        method="loess",
    )
    if curve is not None and not curve.empty:
        return curve
    if len(ordered.index) < 2:
        return None
    return pd.DataFrame(
        {
            "publication_date": ordered["publication_date"],
            "score_smooth": ordered["estimate_percent"],
        }
    )


def _base_figure(title: str) -> go.Figure:
    figure = go.Figure()
    figure.update_layout(
        title=title,
        xaxis_title="Date",
        yaxis_title="Intentions de vote (%)",
        **PLOT_LAYOUT_THEME,
    )
    figure.update_yaxes(ticksuffix=" %")
    return figure


def _add_series(
    figure: go.Figure,
    frame: pd.DataFrame,
    *,
    label: str,
    party: str,
    dash: str = "solid",
    frac: float = 0.25,
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
            marker={"size": 6, "color": color, "opacity": 0.72},
            name=f"{label} - points",
            legendgroup=label,
            showlegend=False,
            customdata=ordered[["polling_company"]].to_numpy(),
            hovertemplate="%{x|%d/%m/%Y}<br>%{y:.1f}%<br>Institut : %{customdata[0]}<extra></extra>",
        )
    )
    curve = _build_curve(ordered, frac=frac)
    if curve is None:
        return
    figure.add_trace(
        go.Scatter(
            x=curve["publication_date"],
            y=curve["score_smooth"],
            mode="lines",
            line={"width": 2.5, "color": color, "dash": dash},
            name=label,
            legendgroup=label,
            showlegend=True,
            hovertemplate="%{x|%d/%m/%Y}<br>%{y:.1f}%<extra></extra>",
        )
    )


def _party_group(value: object) -> str | None:
    party = "" if value is None or pd.isna(value) else str(value).strip()
    for display_party, aliases in PARTY_ALIASES.items():
        if party in aliases:
            return display_party
    return None


def _candidate_mask(frame: pd.DataFrame, aliases: tuple[str, ...]) -> pd.Series:
    normalized_names = frame["candidate_name"].map(_normalize_text)
    normalized_aliases = tuple(_normalize_text(alias) for alias in aliases)
    return normalized_names.map(lambda name: any(alias in name for alias in normalized_aliases))


def _render_party_chart(working: pd.DataFrame) -> None:
    st.markdown("### Intentions de vote par parti politique")
    selected_parties = st.multiselect(
        "Partis affichés",
        DEFAULT_PARTIES,
        default=DEFAULT_PARTIES,
        key="wikipedia_2027_default_parties",
    )
    party_frame = working.copy()
    party_frame["display_party"] = party_frame["candidate_party"].map(_party_group)
    party_frame = party_frame.loc[party_frame["display_party"].isin(selected_parties)].copy()
    party_frame = (
        party_frame.groupby(
            ["poll_id", "scenario_name", "publication_date", "display_party"],
            dropna=False,
        )
        .agg(
            estimate_percent=("estimate_percent", "mean"),
            polling_company=("polling_company", "first"),
        )
        .reset_index()
    )
    figure = _base_figure("Sondages 2027 par parti politique")
    for party in selected_parties:
        current = party_frame.loc[party_frame["display_party"] == party]
        _add_series(figure, current, label=party, party=party)
    st.plotly_chart(figure, width="stretch", config={"displayModeBar": False, "responsive": True})


def _render_candidate_chart(working: pd.DataFrame) -> None:
    st.markdown("### Intentions de vote par candidat")
    labels = [spec[0] for spec in CANDIDATE_SPECS]
    selected_candidates = st.multiselect(
        "Candidats affichés",
        labels,
        default=labels,
        key="wikipedia_2027_default_candidates",
    )
    figure = _base_figure("Sondages 2027 par candidat")
    for label, _canonical_name, party, aliases, dash in CANDIDATE_SPECS:
        if label not in selected_candidates:
            continue
        current = working.loc[_candidate_mask(working, aliases)].copy()
        _add_series(figure, current, label=label, party=party, dash=dash)
    st.plotly_chart(figure, width="stretch", config={"displayModeBar": False, "responsive": True})


def render_wikipedia_2027_page(frame: pd.DataFrame) -> None:
    st.subheader("Sondages présidentiels 2027")
    working = frame.loc[(frame["round"] == "first_round") & (~frame["is_generic_bloc"])].copy()
    working["publication_date"] = pd.to_datetime(working["publication_date"], errors="coerce")
    working["estimate_percent"] = pd.to_numeric(working["estimate_percent"], errors="coerce")
    working = working.dropna(subset=["publication_date", "estimate_percent"])
    working = _select_primary_scenarios(working)
    if working.empty:
        st.info("Aucune donnée Wikipédia 2027 exploitable.")
        return

    st.caption(
        "Données Wikipédia rafraîchies au démarrage de l'application. Les points sont les mesures publiées ; "
        "les lignes représentent une tendance lissée."
    )
    _render_party_chart(working)
    _render_candidate_chart(working)

    st.markdown("### Tableau détaillé")
    detailed = working.sort_values(["publication_date", "candidate_name"], ascending=[False, True])
    render_poll_results_table(detailed)
