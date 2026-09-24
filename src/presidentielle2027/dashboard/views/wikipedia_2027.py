from __future__ import annotations

import unicodedata
from typing import cast

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from presidentielle2027.analytics.adjustment_core import (
    build_polynomial_curve,
    select_auto_polynomial_degree,
)
from presidentielle2027.analytics.trends import build_lowess_curve
from presidentielle2027.dashboard.colors import get_political_color
from presidentielle2027.dashboard.plot_theme import PLOT_LAYOUT_THEME
from presidentielle2027.dashboard.views.first_round_raw import GITLAB_LOESS_SPANS
from presidentielle2027.extraction.canonicalization import canonicalize_polling_company

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

CANDIDATE_TABLE_ORDER = [
    "Arlette Arthaud",
    "Jean-Luc Mélenchon",
    "Fabien Roussel",
    "Marine Tondelier",
    "Raphaël Glucksmann",
    "Olivier Faure",
    "François Hollande",
    "Gabriel Attal",
    "Édouard Philippe",
    "Dominique de Villepin",
    "Bruno Retailleau",
    "Nicolas Dupont-Aignan",
    "Marine Le Pen",
    "Jordan Bardella",
    "Éric Zemmour",
    "Sarah Knafo",
]

CANDIDATE_TABLE_PARTIES = {
    "Arlette Arthaud": "LO",
    "Jean-Luc Mélenchon": "LFI",
    "Fabien Roussel": "PCF",
    "Marine Tondelier": "EELV",
    "Raphaël Glucksmann": "PP",
    "Olivier Faure": "PS",
    "François Hollande": "PS",
    "Gabriel Attal": "RE",
    "Édouard Philippe": "HOR",
    "Dominique de Villepin": "LFH",
    "Bruno Retailleau": "LR",
    "Nicolas Dupont-Aignan": "DLF",
    "Marine Le Pen": "RN",
    "Jordan Bardella": "RN",
    "Éric Zemmour": "REC",
    "Sarah Knafo": "REC",
}


def wikipedia_table_cell_styles(row: pd.Series) -> list[str]:
    """Highlight and bold the two highest scores, as in Wikipedia's table."""
    styles = [""] * len(row.index)
    candidate_scores: list[tuple[str, float]] = []
    metadata_columns = {"Sondeur", "Date", "Échantillon", "Hypothèse"}
    for column in row.index:
        if column in metadata_columns:
            continue
        score = pd.to_numeric(row[column], errors="coerce")
        if pd.notna(score):
            candidate_scores.append((str(column), float(score)))
    qualified = sorted(candidate_scores, key=lambda item: (-item[1], item[0]))[:2]
    light_parties = {"PP", "RE", "LFH"}
    for candidate_name, _ in qualified:
        party = CANDIDATE_TABLE_PARTIES.get(candidate_name)
        color = get_political_color(party, None)
        foreground = "#111111" if party in light_parties else "#ffffff"
        position = row.index.get_loc(candidate_name)
        styles[position] = (
            f"background-color: {color}; color: {foreground}; "
            "font-weight: 800; border: 2px solid #111111"
        )
    return styles


def _format_sample_size(value: object) -> str:
    if value is None or pd.isna(value):
        return "—"
    number = pd.to_numeric(value, errors="coerce")
    if pd.isna(number):
        return str(value)
    return f"{int(round(float(number))):,}".replace(",", "\u00a0")


def build_wikipedia_style_table(frame: pd.DataFrame) -> pd.DataFrame:
    """Return one wide row per scenario, close to Wikipedia's source layout."""
    required = {
        "poll_id",
        "round",
        "scenario_name",
        "candidate_name",
        "estimate_percent",
        "polling_company",
        "sample_size",
    }
    if frame.empty or not required.issubset(frame.columns):
        return pd.DataFrame()

    working = frame.loc[frame["round"].eq("first_round")].copy()
    working["polling_company"] = working["polling_company"].map(canonicalize_polling_company)
    if "parse_status" in working.columns:
        working = working.loc[
            ~working["parse_status"].isin({"technical_duplicate", "unparsed_estimate"})
        ].copy()
    working["estimate_percent"] = pd.to_numeric(working["estimate_percent"], errors="coerce")
    working = working.dropna(subset=["candidate_name"])
    if working.empty:
        return pd.DataFrame()

    scenario_key = ["poll_id", "scenario_name"]
    metadata_columns = ["poll_id", "scenario_name", "polling_company", "sample_size"]
    if "fieldwork_date_raw" in working.columns:
        metadata_columns.append("fieldwork_date_raw")
    if "publication_date" in working.columns:
        metadata_columns.append("publication_date")

    metadata = working[metadata_columns].drop_duplicates(subset=scenario_key, keep="first")
    candidate_names = working["candidate_name"].dropna().astype(str).unique().tolist()
    values = working.pivot_table(
        index=scenario_key,
        columns="candidate_name",
        values="estimate_percent",
        aggfunc="first",
    ).reset_index()
    for candidate_name in candidate_names:
        if candidate_name not in values.columns:
            values[candidate_name] = pd.NA
    wide = metadata.merge(values, on=scenario_key, how="left", validate="one_to_one")
    date_column = "fieldwork_date_raw" if "fieldwork_date_raw" in wide.columns else "publication_date"
    if "publication_date" in wide.columns:
        wide["_sort_date"] = pd.to_datetime(wide["publication_date"], errors="coerce")
    else:
        wide["_sort_date"] = pd.NaT
    wide = wide.rename(
        columns={
            "polling_company": "Sondeur",
            "sample_size": "Échantillon",
            date_column: "Date",
            "scenario_name": "Hypothèse",
        }
    )
    candidate_columns = [name for name in CANDIDATE_TABLE_ORDER if name in wide.columns]
    candidate_columns.extend(
        sorted(
            column
            for column in wide.columns
            if column not in {*metadata_columns, "Sondeur", "Échantillon", "Date", "Hypothèse", "poll_id", "_sort_date", "publication_date"}
            and column not in candidate_columns
        )
    )
    wide = wide.sort_values(["_sort_date", "Sondeur", "Hypothèse"], ascending=[False, True, True])
    result = wide[["Sondeur", "Date", "Échantillon", "Hypothèse", *candidate_columns]].copy()
    result["Échantillon"] = result["Échantillon"].map(_format_sample_size)

    # A "<1" source cell has no point estimate but is not "non testé": show its bound.
    bounded_labels: dict[tuple[str, str, str], str] = {}
    if {"parse_status", "upper_bound_percent"}.issubset(working.columns):
        bounded = working.loc[
            working["parse_status"].eq("bounded_estimate")
            & pd.to_numeric(working["upper_bound_percent"], errors="coerce").notna()
        ]
        for poll_id, scenario, candidate, bound in zip(
            bounded["poll_id"],
            bounded["scenario_name"],
            bounded["candidate_name"].astype(str),
            pd.to_numeric(bounded["upper_bound_percent"], errors="coerce"),
        ):
            bounded_labels[(str(poll_id), str(scenario), candidate)] = f"<{float(bound):g}"

    for column in candidate_columns:
        result[column] = [
            bounded_labels.get((str(poll_id), str(scenario), column), "—")
            if pd.isna(value)
            else f"{float(value):g}"
            for value, poll_id, scenario in zip(wide[column], wide["poll_id"], wide["Hypothèse"])
        ]
    return result


def render_wikipedia_style_table(frame: pd.DataFrame) -> None:
    table = build_wikipedia_style_table(frame)
    st.markdown("**Tableau des sondages au format Wikipédia**")
    st.caption(
        "Une ligne par hypothèse et une colonne par candidat ; les deux premiers, "
        "qualifiés au second tour dans l’hypothèse, sont en gras et aux couleurs politiques. "
        "« — » signifie non testé ; « <1 » signifie un score publié inférieur à 1 %."
    )
    if table.empty:
        st.info("Aucun sondage de premier tour disponible pour ce tableau.")
        return
    styled = table.style.apply(wikipedia_table_cell_styles, axis=1)
    st.dataframe(styled, width="stretch", hide_index=True, height=620)


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
    figure.update_layout(
        legend={**cast(dict[str, object], PLOT_LAYOUT_THEME["legend"]), "traceorder": "normal"}
    )
    figure.update_yaxes(ticksuffix=" %")
    st.plotly_chart(
        figure,
        width="stretch",
        key="first_round_candidate_trace_chart",
        config={"displayModeBar": False, "responsive": True},
    )
