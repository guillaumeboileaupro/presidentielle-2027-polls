from __future__ import annotations

from datetime import date

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from presidentielle2027.analytics.uncertainty import approximate_margin_of_error
from presidentielle2027.dashboard.colors import get_political_color
from presidentielle2027.dashboard.plot_theme import PLOT_LAYOUT_THEME

PARTY_CANDIDATE_SYMBOLS = [
    "circle",
    "diamond",
    "square",
    "x",
    "triangle-up",
    "triangle-down",
    "cross",
    "star",
]


def _build_candidate_symbols(frame: pd.DataFrame) -> dict[str, str]:
    if frame.empty:
        return {}

    symbols: dict[str, str] = {}
    candidates = (
        frame[["candidate_name", "candidate_party"]]
        .dropna(subset=["candidate_name"])
        .drop_duplicates()
        .sort_values(["candidate_party", "candidate_name"], na_position="last")
    )
    for _, party_group in candidates.groupby("candidate_party", dropna=False, sort=False):
        for idx, row in enumerate(party_group.itertuples(index=False)):
            symbols[str(row.candidate_name)] = PARTY_CANDIDATE_SYMBOLS[idx % len(PARTY_CANDIDATE_SYMBOLS)]
    return symbols


def render_error_bars_raw_page(frame: pd.DataFrame) -> None:
    st.subheader("Barres d’erreur brutes")
    st.caption("Formule utilisée : `moe_95 = 1.96 * sqrt(p * (1 - p) / n) * 100`.")
    working = frame.loc[(frame["round"] == "first_round") & (~frame["is_generic_bloc"])].copy()
    if "source_url" not in working.columns:
        working["source_url"] = pd.NA
    if working.empty:
        st.info("Aucune donnée de premier tour exploitable.")
        return

    pollsters = ["Tous"] + sorted(working["polling_company"].dropna().astype(str).unique().tolist())
    parties = ["Tous"] + sorted(working["candidate_party"].dropna().astype(str).unique().tolist())
    scenarios = ["Tous"] + sorted(working["scenario_name"].dropna().astype(str).unique().tolist())
    min_date = working["publication_date"].min().date() if working["publication_date"].notna().any() else date.today()
    max_date = working["publication_date"].max().date() if working["publication_date"].notna().any() else date.today()

    c1, c2, c3 = st.columns(3)
    scenario_name = c1.selectbox("Scénario", scenarios, key="error_bars_scenario")
    pollster = c2.selectbox("Institut", pollsters, key="error_bars_pollster")
    party = c3.selectbox("Parti", parties, key="error_bars_party")

    filtered = working.copy()
    if scenario_name != "Tous":
        filtered = filtered.loc[filtered["scenario_name"] == scenario_name]
    if pollster != "Tous":
        filtered = filtered.loc[filtered["polling_company"] == pollster]
    if party != "Tous":
        filtered = filtered.loc[filtered["candidate_party"] == party]

    candidate_options = sorted(filtered["candidate_name"].dropna().astype(str).unique().tolist())
    selected_candidates = st.multiselect("Candidats", candidate_options, default=candidate_options[:3], key="error_bars_candidates")

    c4, c5 = st.columns([1.7, 1.2])
    period = c4.date_input("Période", value=(min_date, max_date), min_value=min_date, max_value=max_date, key="error_bars_period")
    point_limit = c5.slider("Maximum de séries visibles", min_value=1, max_value=8, value=3, step=1, key="error_bars_limit")

    if selected_candidates:
        filtered = filtered.loc[filtered["candidate_name"].isin(selected_candidates)]
    if isinstance(period, tuple) and len(period) == 2:
        filtered = filtered.loc[
            filtered["publication_date"].between(pd.Timestamp(period[0]), pd.Timestamp(period[1]), inclusive="both")
        ]
    if filtered.empty:
        st.warning("Aucune donnée disponible avec ces filtres.")
        return

    filtered = filtered.sort_values("publication_date", ascending=False)
    top_candidates = filtered["candidate_name"].value_counts().head(point_limit).index.tolist()
    filtered = filtered.loc[filtered["candidate_name"].isin(top_candidates)].copy()
    filtered["marge_erreur_95"] = filtered.apply(
        lambda row: approximate_margin_of_error(row.get("sample_size"), row.get("estimate_percent", 50.0)),
        axis=1,
    )
    filtered["borne_basse"] = (filtered["estimate_percent"] - filtered["marge_erreur_95"].fillna(0.0)).clip(lower=0.0)
    filtered["borne_haute"] = (filtered["estimate_percent"] + filtered["marge_erreur_95"].fillna(0.0)).clip(upper=100.0)
    candidate_symbols = _build_candidate_symbols(filtered)

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Lignes affichées", int(len(filtered)))
    col2.metric("Candidats affichés", int(filtered["candidate_name"].nunique()))
    col3.metric("Barres calculées", int(filtered["marge_erreur_95"].notna().sum()))
    col4.metric("Échantillon moyen", f"{filtered['sample_size'].dropna().mean():.0f}" if filtered["sample_size"].notna().any() else "n.d.")

    figure = go.Figure()
    for candidate_name, group in filtered.groupby("candidate_name", dropna=False):
        ordered = group.sort_values("publication_date")
        party_name = ordered["candidate_party"].dropna().iloc[0] if ordered["candidate_party"].notna().any() else None
        family = ordered["political_family"].dropna().iloc[0] if ordered["political_family"].notna().any() else None
        color = get_political_color(party_name, family)
        symbol = candidate_symbols.get(str(candidate_name), "circle")
        figure.add_trace(
            go.Scatter(
                x=ordered["publication_date"],
                y=ordered["estimate_percent"],
                mode="markers",
                name=str(candidate_name),
                marker={"size": 8, "color": color, "symbol": symbol, "line": {"color": "#ffffff", "width": 1.0}},
                error_y={
                    "type": "data",
                    "array": ordered["borne_haute"] - ordered["estimate_percent"],
                    "arrayminus": ordered["estimate_percent"] - ordered["borne_basse"],
                    "color": color,
                    "thickness": 1.5,
                    "width": 5,
                },
                customdata=ordered[["polling_company", "sample_size", "marge_erreur_95", "source_url"]].to_numpy(),
                hovertemplate="%{x|%d/%m/%Y}<br>%{y:.1f}%<br>Institut: %{customdata[0]}<br>Échantillon: %{customdata[1]}<br>Marge 95%%: %{customdata[2]:.2f}<extra></extra>",
            )
        )

    figure.update_layout(
        title="Premier tour brut avec barres d’erreur",
        xaxis_title="Date de publication",
        yaxis_title="Intentions de vote (%)",
        legend_title="Candidats",
        **PLOT_LAYOUT_THEME,
    )
    figure.update_yaxes(ticksuffix=" %")
    st.plotly_chart(figure, width="stretch", config={"displayModeBar": False, "responsive": True})

    st.dataframe(
        filtered[
            [
                "publication_date",
                "polling_company",
                "candidate_name",
                "candidate_party",
                "estimate_percent",
                "marge_erreur_95",
                "borne_basse",
                "borne_haute",
                "sample_size",
                "source_url",
            ]
        ].rename(
            columns={
                "publication_date": "Publication",
                "polling_company": "Institut",
                "candidate_name": "Candidat",
                "candidate_party": "Parti",
                "estimate_percent": "Score",
                "marge_erreur_95": "Marge d’erreur",
                "borne_basse": "Intervalle bas",
                "borne_haute": "Intervalle haut",
                "sample_size": "Échantillon",
                "source_url": "Lien source",
            }
        ),
        width="stretch",
        hide_index=True,
        column_config={
            "Score": st.column_config.NumberColumn("Score", format="%.1f %%"),
            "Marge d’erreur": st.column_config.NumberColumn("Marge d’erreur", format="%.2f %%"),
            "Intervalle bas": st.column_config.NumberColumn("Intervalle bas", format="%.2f %%"),
            "Intervalle haut": st.column_config.NumberColumn("Intervalle haut", format="%.2f %%"),
            "Échantillon": st.column_config.NumberColumn("Échantillon", format="%d"),
            "Lien source": st.column_config.LinkColumn("Lien source"),
        },
    )
