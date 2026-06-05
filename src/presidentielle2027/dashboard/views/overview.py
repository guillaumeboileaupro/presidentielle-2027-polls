from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from presidentielle2027.dashboard.colors import get_political_color
from presidentielle2027.dashboard.plot_theme import PLOT_LAYOUT_THEME


def _build_series_label(row: pd.Series, round_name: str) -> str:
    if round_name == "first_round":
        party = row.get("candidate_party")
        if party is not None and str(party) != "nan" and str(party).strip() != "":
            return str(party)
    return str(row["candidate_name"])


def render_overview_page(frame: pd.DataFrame) -> None:
    st.subheader("Vue générale")
    if frame.empty:
        st.info("Aucune donnée pour les filtres sélectionnés.")
        return

    scenario_name = frame["scenario_name"].dropna().iloc[0] if frame["scenario_name"].notna().any() else "Scénario inconnu"
    round_name = frame["round"].dropna().iloc[0] if frame["round"].notna().any() else "unknown"
    poll_count = frame["poll_id"].nunique() if "poll_id" in frame.columns else len(frame)
    candidate_count = frame["candidate_name"].nunique()
    latest_date = frame["publication_date"].max()
    earliest_date = frame["publication_date"].min()

    st.markdown(
        '<div class="wiki-note">Ces sondages sont affichés pour une hypothèse unique. '
        'Le tableau détaillé reste présenté en ordre antéchronologique : les plus récents en tête.</div>',
        unsafe_allow_html=True,
    )

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Scénario sélectionné", scenario_name)
    col2.metric("Sondages", int(poll_count))
    col3.metric("Candidats", int(candidate_count))
    col4.metric(
        "Période",
        f"{earliest_date:%d/%m/%Y} → {latest_date:%d/%m/%Y}" if earliest_date is not None and latest_date is not None else "n/a",
    )

    working = frame.copy().sort_values("publication_date")
    working["series_label"] = working.apply(lambda row: _build_series_label(row, round_name), axis=1)

    color_map = {
        row["series_label"]: get_political_color(row.get("candidate_party"), row.get("political_family"))
        for _, row in working[["series_label", "candidate_party", "political_family"]]
        .drop_duplicates(subset=["series_label"])
        .iterrows()
    }

    figure = go.Figure()
    for series_label, group in working.groupby("series_label", dropna=False):
        ordered = group.sort_values("publication_date").copy()
        color = color_map.get(series_label, "#616161")

        figure.add_trace(
            go.Scatter(
                x=ordered["publication_date"],
                y=ordered["estimate_percent"],
                mode="markers",
                name=f"{series_label} - points",
                marker={"color": color, "size": 6, "opacity": 0.65},
                legendgroup=str(series_label),
                showlegend=False,
                customdata=ordered[["polling_company", "candidate_name", "candidate_party"]].to_numpy(),
                hovertemplate="%{x|%d/%m/%Y}<br>%{y:.1f}%<br>Institut: %{customdata[0]}<br>Candidat: %{customdata[1]}<br>Parti: %{customdata[2]}<extra></extra>",
            )
        )

    figure.update_layout(
        title=f"Points observés - {scenario_name}",
        legend_title="Série politique" if round_name == "first_round" else "Candidat",
        xaxis_title="Date de publication",
        yaxis_title="Intentions de vote (%)",
        **PLOT_LAYOUT_THEME,
    )
    st.plotly_chart(figure, width="stretch", config={"displayModeBar": False, "responsive": True})
    st.caption("Cette vue n’affiche que les points observés. Aucun lissage ni ajustement linéaire n’est utilisé.")

    st.dataframe(
        working[
            [
                "publication_date",
                "polling_company",
                "scenario_name",
                "candidate_name",
                "candidate_party",
                "political_family",
                "estimate_percent",
                "sample_size",
            ]
        ].sort_values("publication_date", ascending=False),
        width="stretch",
    )
