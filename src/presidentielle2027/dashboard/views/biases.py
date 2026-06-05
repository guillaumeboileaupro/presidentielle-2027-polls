from __future__ import annotations

from pathlib import Path

import plotly.express as px
import pandas as pd
import streamlit as st

from presidentielle2027.analytics.historical_corrections import compute_first_round_correction_context, get_reference_dir
from presidentielle2027.dashboard.plot_theme import PLOT_LAYOUT_THEME
from presidentielle2027.dashboard.table_views import clean_user_facing_frame, rename_user_facing_columns


def render_biases_page(frame: pd.DataFrame) -> None:
    st.subheader("Biais calculés")
    working = frame.loc[(frame["round"] == "first_round") & (~frame["is_generic_bloc"])].copy()
    context = compute_first_round_correction_context(get_reference_dir(Path.cwd()), working)
    bias_catalog = context.bias_catalog.copy()

    if bias_catalog.empty:
        st.info("Aucun biais calculable avec les données locales disponibles.")
        return

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Forces suivies", int(bias_catalog["force_label"].nunique()))
    col2.metric("Calculés", int((bias_catalog["status"] == "calculé").sum()))
    col3.metric("À vérifier", int((bias_catalog["status"] == "à vérifier").sum()))
    col4.metric("Insuffisants", int((bias_catalog["status"] == "données insuffisantes").sum()))

    historical = context.historical_errors.copy()
    temporal_rows = []
    if not historical.empty:
        historical["months_before_vote"] = pd.to_numeric(historical["days_until_election"], errors="coerce") / 30.44
        for force_label, group in historical.groupby("force_label", dropna=False):
            row = {"force_label": force_label}
            row["median_error"] = float(group["historical_error"].median())
            for months in [18, 12, 6, 3, 1]:
                nearby = group.loc[(group["months_before_vote"] - months).abs() <= 1.5]
                row[f"temporal_bias_{months}m"] = float(-nearby["historical_error"].mean()) if not nearby.empty else pd.NA
            temporal_rows.append(row)
    temporal_frame = pd.DataFrame(temporal_rows)
    if not temporal_frame.empty:
        bias_catalog = bias_catalog.merge(temporal_frame, on="force_label", how="left")

    st.dataframe(
        clean_user_facing_frame(
            rename_user_facing_columns(
                bias_catalog,
                {
                    "temporal_bias_18m": "Biais temporel 18m",
                    "temporal_bias_12m": "Biais temporel 12m",
                    "temporal_bias_6m": "Biais temporel 6m",
                    "temporal_bias_3m": "Biais temporel 3m",
                    "temporal_bias_1m": "Biais temporel 1m",
                },
            )
        ),
        width="stretch",
        hide_index=True,
        column_config={
            "Résultat réel 2022": st.column_config.NumberColumn("Résultat réel 2022", format="%.2f %%"),
            "Erreur moyenne": st.column_config.NumberColumn("Erreur moyenne", format="%.2f"),
            "Erreur médiane": st.column_config.NumberColumn("Erreur médiane", format="%.2f"),
            "Incertitude": st.column_config.NumberColumn("Incertitude", format="%.2f"),
            "Biais structurel": st.column_config.NumberColumn("Biais structurel", format="%.2f"),
            "Biais temps long": st.column_config.NumberColumn("Biais temps long", format="%.2f"),
            "Biais temporel 18m": st.column_config.NumberColumn("Biais temporel 18m", format="%.2f"),
            "Biais temporel 12m": st.column_config.NumberColumn("Biais temporel 12m", format="%.2f"),
            "Biais temporel 6m": st.column_config.NumberColumn("Biais temporel 6m", format="%.2f"),
            "Biais temporel 3m": st.column_config.NumberColumn("Biais temporel 3m", format="%.2f"),
            "Biais temporel 1m": st.column_config.NumberColumn("Biais temporel 1m", format="%.2f"),
            "Biais trajectoire": st.column_config.NumberColumn("Biais trajectoire", format="%.2f"),
            "Correction totale": st.column_config.NumberColumn("Correction totale", format="%.2f"),
        },
    )

    plot_source = bias_catalog.melt(
        id_vars=["force_label", "status"],
        value_vars=["structural_bias", "temporal_bias", "trajectory_bias"],
        var_name="bias_type",
        value_name="bias_value",
    ).dropna(subset=["bias_value"])
    plot_source["bias_type"] = plot_source["bias_type"].map(
        {
            "structural_bias": "Biais structurel",
            "temporal_bias": "Biais temps long",
            "trajectory_bias": "Biais trajectoire",
        }
    )
    figure = px.bar(
        plot_source,
        x="force_label",
        y="bias_value",
        color="bias_type",
        barmode="group",
        title="Décomposition des trois biais par force",
        labels={"force_label": "Force", "bias_value": "Biais", "bias_type": "Type"},
    )
    figure.update_layout(**PLOT_LAYOUT_THEME)
    st.plotly_chart(figure, width="stretch", config={"displayModeBar": False, "responsive": True})

    with st.expander("Méthode appliquée", expanded=False):
        st.markdown(
            """
            - `Biais structurel` : moyenne pondérée des erreurs 2022 par force, avec plus de poids aux sondages les plus proches du scrutin.
            - `Biais temps long` : ajustement de cette erreur selon la fenêtre temporelle 2027 (`0_30`, `31_90`, `91_180`, `181_plus`) observée en 2022.
            - `Biais trajectoire` : correction liée à la dynamique récente 2027 comparée à la dynamique historique des erreurs de cette force.
            - `Statut` : `calculé` si les trois composantes sont suffisamment renseignées, `à vérifier` si la fenêtre ou la dynamique est fragile, `données insuffisantes` sinon.
            """
        )
