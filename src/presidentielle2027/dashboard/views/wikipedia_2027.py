from __future__ import annotations

from pathlib import Path
import unicodedata

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from presidentielle2027.analytics.trends import build_lowess_curve
from presidentielle2027.dashboard.colors import get_political_color
from presidentielle2027.dashboard.table_views import render_poll_results_table


DEFAULT_PARTIES = ["PCF", "LFI", "ECO", "PS", "ENS", "LR", "RN", "REC"]

PARTY_ALIASES: dict[str, set[str]] = {
    "PCF": {"PCF"},
    "LFI": {"LFI"},
    "ECO": {"ECO", "EELV", "LE"},
    "PS": {"PS", "PS-PP"},
    "ENS": {"ENS", "RE", "HOR", "MODEM", "MoDem"},
    "LR": {"LR"},
    "RN": {"RN"},
    "REC": {"REC"},
}

CANDIDATE_SPECS = [
    ("Arthaud — LO", "LO", ("arthaud",), "solid"),
    ("Mélenchon — LFI", "LFI", ("melenchon",), "solid"),
    ("Roussel — PCF", "PCF", ("roussel",), "solid"),
    ("Tondelier — LE", "LE", ("tondelier",), "solid"),
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

SCREENSHOT_COLORS = {
    "PCF": "#d00000",
    "LFI": "#d7193f",
    "ECO": "#00b83f",
    "PS": "#ff6f6f",
    "ENS": "#f2c500",
    "LR": "#0085c2",
    "RN": "#073b8c",
    "REC": "#333333",
}


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


def _screenshot_figure(*, x_start: str, x_end: str) -> go.Figure:
    figure = go.Figure()
    figure.update_layout(
        paper_bgcolor="#EBEBEB",
        plot_bgcolor="#EBEBEB",
        font={"color": "#222222", "family": "Arial, sans-serif", "size": 13},
        margin={"l": 55, "r": 210, "t": 15, "b": 45},
        hovermode="closest",
        legend={
            "orientation": "v",
            "yanchor": "middle",
            "y": 0.5,
            "xanchor": "left",
            "x": 1.01,
            "bgcolor": "#EBEBEB",
            "borderwidth": 0,
            "font": {"size": 14},
        },
        xaxis={
            "range": [pd.Timestamp(x_start), pd.Timestamp(x_end)],
            "showgrid": True,
            "gridcolor": "#FFFFFF",
            "gridwidth": 1,
            "zeroline": False,
            "title": None,
        },
        yaxis={
            "range": [0, 42],
            "dtick": 10,
            "ticksuffix": "%",
            "showgrid": True,
            "gridcolor": "#FFFFFF",
            "gridwidth": 1,
            "zeroline": False,
            "title": None,
        },
    )
    return figure


def _add_series(
    figure: go.Figure,
    frame: pd.DataFrame,
    *,
    label: str,
    party: str,
    dash: str = "solid",
    frac: float = 0.25,
    color: str | None = None,
) -> None:
    ordered = frame.sort_values("publication_date").dropna(subset=["publication_date", "estimate_percent"])
    if ordered.empty:
        return
    resolved_color = color or get_political_color(party, None)
    figure.add_trace(
        go.Scatter(
            x=ordered["publication_date"],
            y=ordered["estimate_percent"],
            mode="markers",
            marker={"size": 5, "color": resolved_color, "opacity": 0.35},
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
            line={"width": 2.1, "color": resolved_color, "dash": dash},
            name=label,
            legendgroup=label,
            showlegend=True,
            hovertemplate="%{x|%d/%m/%Y}<br>%{y:.1f}%<extra></extra>",
        )
    )


def _load_2022_party_history() -> pd.DataFrame:
    path = Path("data/reference/historical_polls_2022_first_round.csv")
    if not path.exists():
        return pd.DataFrame()
    historical = pd.read_csv(path)
    historical["publication_date"] = pd.to_datetime(historical["fieldwork_end_date"], errors="coerce")
    historical["estimate_percent"] = pd.to_numeric(historical["estimate_percent"], errors="coerce")
    historical["candidate_party"] = historical["force_label"]
    historical["polling_company"] = historical["pollster"]
    historical["poll_id"] = "HIST-2022-" + historical.index.astype(str)
    historical["scenario_name"] = "Présidentielle 2022"
    return historical


def _render_party_chart(working: pd.DataFrame) -> None:
    current = working.copy()
    current["display_party"] = current["candidate_party"].map(_party_group)
    historical = _load_2022_party_history()
    if not historical.empty:
        historical["display_party"] = historical["candidate_party"].map(_party_group)
        historical = historical.loc[historical["publication_date"] >= pd.Timestamp("2022-04-01")]
        party_frame = pd.concat([historical, current], ignore_index=True, sort=False)
    else:
        party_frame = current

    party_frame = party_frame.loc[party_frame["display_party"].isin(DEFAULT_PARTIES)].copy()
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

    figure = _screenshot_figure(x_start="2022-04-01", x_end="2027-07-01")
    for party in DEFAULT_PARTIES:
        _add_series(
            figure,
            party_frame.loc[party_frame["display_party"] == party],
            label=party,
            party=party,
            color=SCREENSHOT_COLORS[party],
        )
    st.plotly_chart(
        figure,
        width="stretch",
        key="wikipedia_2027_party_trace_chart",
        config={"displayModeBar": False, "responsive": True},
    )


def _render_candidate_chart(working: pd.DataFrame) -> None:
    figure = _screenshot_figure(x_start="2026-02-01", x_end="2027-05-01")
    for label, party, aliases, dash in CANDIDATE_SPECS:
        current = working.loc[_candidate_mask(working, aliases)].copy()
        _add_series(figure, current, label=label, party=party, dash=dash)
    st.plotly_chart(
        figure,
        width="stretch",
        key="wikipedia_2027_candidate_trace_chart",
        config={"displayModeBar": False, "responsive": True},
    )


def _render_latest_values_table(working: pd.DataFrame) -> None:
    st.markdown("### Lecture rapide des forces")
    latest_rows: list[dict[str, object]] = []
    party_frame = working.copy()
    party_frame["Sigle"] = party_frame["candidate_party"].map(_party_group)
    party_frame = party_frame.loc[party_frame["Sigle"].isin(DEFAULT_PARTIES)].copy()
    for party in DEFAULT_PARTIES:
        current = party_frame.loc[party_frame["Sigle"] == party].copy()
        if current.empty:
            continue
        latest_date = current["publication_date"].max()
        latest = current.loc[current["publication_date"] == latest_date, "estimate_percent"]
        latest_rows.append(
            {
                "Sigle": party,
                "Dernière valeur": f"{latest.mean():.1f}%",
                "Date": latest_date.strftime("%d/%m/%Y"),
            }
        )
    st.table(pd.DataFrame(latest_rows))


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

    _render_party_chart(working)
    _render_candidate_chart(working)
    _render_latest_values_table(working)

    st.markdown("### Tableau détaillé")
    detailed = working.sort_values(["publication_date", "candidate_name"], ascending=[False, True])
    render_poll_results_table(detailed)
