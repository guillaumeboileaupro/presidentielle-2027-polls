from __future__ import annotations

import plotly.express as px
import streamlit as st

from presidentielle2027.adjustments.house_effects import estimate_house_effects
from presidentielle2027.dashboard.plot_theme import PLOT_LAYOUT_THEME


def render_pollster_bias_page(frame) -> None:
    st.subheader("Vue instituts")
    if frame.empty:
        st.info("Aucune donnée pour les filtres sélectionnés.")
        return
    scenario_name = frame["scenario_name"].dropna().iloc[0] if frame["scenario_name"].notna().any() else "Scénario inconnu"
    effects = estimate_house_effects(frame)
    figure = px.bar(
        effects.sort_values("house_effect"),
        x="polling_company",
        y="house_effect",
        title=f"House effects moyens par institut - {scenario_name}",
    )
    figure.update_layout(**PLOT_LAYOUT_THEME)
    st.plotly_chart(figure, width="stretch", config={"displayModeBar": False, "responsive": True})
    counts = frame.groupby("polling_company", dropna=False)["poll_id"].nunique().reset_index(name="poll_count")
    st.dataframe(counts.sort_values("poll_count", ascending=False), width="stretch")
