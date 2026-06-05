from __future__ import annotations

import plotly.graph_objects as go
import streamlit as st

from presidentielle2027.analytics.uncertainty import approximate_margin_of_error
from presidentielle2027.dashboard.colors import get_political_color
from presidentielle2027.dashboard.plot_theme import PLOT_LAYOUT_THEME


def render_candidate_trends_page(frame) -> None:
    st.subheader("Vue candidat")
    if frame.empty:
        st.info("Aucune donnée pour les filtres sélectionnés.")
        return

    candidates = sorted(frame["candidate_name"].dropna().astype(str).unique().tolist())
    candidate = st.selectbox("Candidat", candidates)
    candidate_frame = frame.loc[frame["candidate_name"] == candidate].copy()
    candidate_frame["approx_moe"] = candidate_frame.apply(
        lambda row: approximate_margin_of_error(row.get("sample_size"), row.get("estimate_percent", 50)), axis=1
    )
    candidate_frame["uncertainty_low"] = candidate_frame["estimate_percent"] - candidate_frame["approx_moe"].fillna(0)
    candidate_frame["uncertainty_high"] = candidate_frame["estimate_percent"] + candidate_frame["approx_moe"].fillna(0)
    candidate_color = get_political_color(
        candidate_frame["candidate_party"].dropna().iloc[0] if candidate_frame["candidate_party"].notna().any() else None,
        candidate_frame["political_family"].dropna().iloc[0] if candidate_frame["political_family"].notna().any() else None,
    )

    ordered = candidate_frame.sort_values("publication_date")
    figure = go.Figure()
    figure.add_trace(
        go.Scatter(
            x=ordered["publication_date"],
            y=ordered["estimate_percent"],
            mode="markers",
            name="Sondages bruts",
            marker={"color": candidate_color, "size": 7},
            customdata=ordered[["polling_company", "scenario_name", "candidate_party"]].to_numpy(),
            hovertemplate="%{x|%d/%m/%Y}<br>%{y:.1f}%<br>Institut: %{customdata[0]}<br>Scénario: %{customdata[1]}<br>Parti: %{customdata[2]}<extra></extra>",
        )
    )
    figure.update_layout(title=f"Points observés - {candidate}", **PLOT_LAYOUT_THEME)
    st.plotly_chart(figure, width="stretch", config={"displayModeBar": False, "responsive": True})
    st.caption("Aucune tendance lissée ni projection n’est affichée sur cette vue.")
    interval_figure = go.Figure(
        data=[
            go.Scatter(
                x=ordered["publication_date"],
                y=ordered["estimate_percent"],
                mode="markers",
                marker={"color": candidate_color, "size": 9},
                error_y={
                    "type": "data",
                    "array": ordered["uncertainty_high"] - ordered["estimate_percent"],
                    "arrayminus": ordered["estimate_percent"] - ordered["uncertainty_low"],
                    "color": candidate_color,
                    "thickness": 1.4,
                },
                customdata=ordered[["polling_company", "scenario_name"]].to_numpy(),
                hovertemplate="%{x|%d/%m/%Y}<br>%{y:.1f}%<br>Institut: %{customdata[0]}<br>Scénario: %{customdata[1]}<extra></extra>",
                name="Intervalle approximatif",
            )
        ]
    )
    interval_figure.update_layout(title="Intervalle d’incertitude approximatif", **PLOT_LAYOUT_THEME)
    st.plotly_chart(interval_figure, width="stretch", config={"displayModeBar": False, "responsive": True})
