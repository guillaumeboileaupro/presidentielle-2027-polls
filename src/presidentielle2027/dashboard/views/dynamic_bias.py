from __future__ import annotations

from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

from presidentielle2027.analytics.dynamic_poll_bias import apply_dynamic_poll_bias_correction
from presidentielle2027.dashboard.plot_theme import PLOT_LAYOUT_THEME


MODEL_SOURCE_LABELS = {
    "pollster_force": "Institut + force",
    "force_only": "Force seule",
    "pollster_only": "Institut seul",
    "global": "Modèle global",
    "manual_override": "Override manuel",
    "unavailable": "Non disponible",
}


def render_dynamic_bias_page(frame: pd.DataFrame) -> None:
    st.subheader("Projection corrigée 2027 · tous instituts")
    st.markdown(
        """
        <div class="wiki-panel">
            <h3 style="margin-top:0;">Méthode de cette vue</h3>
            <p class="wiki-muted" style="margin-bottom:0.5rem;">
                Cette page applique une <strong>projection corrigée 2027 du biais</strong> à <strong>tous les sondages de premier tour</strong>
                et à <strong>toutes les forces politiques disponibles</strong>, en utilisant l’évolution du biais observée dans les
                historiques 2022 du repository.
            </p>
            <ul style="margin-top:0.2rem; line-height:1.55;">
                <li><strong>Biais calibré</strong> : `résultat réel 2022 - sondage historique 2022`.</li>
                <li><strong>Dynamique temporelle</strong> : le biais est modélisé selon le <strong>nombre de jours avant le scrutin</strong>, pas par moyenne brute.</li>
                <li><strong>Hiérarchie des modèles</strong> : `institut + force`, sinon `force seule`, sinon `institut seul`, sinon `global`.</li>
                <li><strong>Overrides manuels</strong> : si `manual_first_round_biases.csv` définit une force, cette valeur remplace la projection automatique.</li>
                <li><strong>Application 2027</strong> : `score corrigé 2027 = score brut 2027 + biais projeté 2027 au même temps électoral`.</li>
            </ul>
        </div>
        """,
        unsafe_allow_html=True,
    )

    working = frame.loc[(frame["round"] == "first_round") & (~frame["is_generic_bloc"])].copy()
    if working.empty:
        st.info("Aucune donnée de premier tour exploitable.")
        return

    corrected, context = apply_dynamic_poll_bias_correction(working, Path.cwd() / "data" / "reference")
    corrected["model_source_label"] = corrected["dynamic_model_source"].map(MODEL_SOURCE_LABELS).fillna("Non disponible")
    if "source_url" not in corrected.columns:
        corrected["source_url"] = pd.NA

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Lignes 2027", int(len(corrected)))
    col2.metric("Instituts 2027", int(corrected["polling_company"].nunique()))
    col3.metric("Forces 2027", int(corrected["force_label"].nunique()))
    col4.metric("Lignes corrigées", int(corrected["dynamic_correction_applied"].sum()))

    if context.calibration_frame.empty or context.segment_models.empty:
        st.warning("Les données historiques locales sont insuffisantes pour construire le modèle dynamique.")
        return

    model_catalog = context.segment_models.copy()
    model_catalog["model_source"] = model_catalog["model_level"].map(MODEL_SOURCE_LABELS).fillna(model_catalog["model_level"])
    model_catalog = model_catalog.rename(
        columns={
            "pollster": "Institut",
            "force_label": "Force",
            "model_source": "Type de modèle",
            "slope": "Pente temporelle",
            "intercept": "Constante",
            "n_points": "Points historiques",
            "min_days": "Jours min",
            "max_days": "Jours max",
            "mean_bias": "Biais moyen",
        }
    )

    st.markdown("**Catalogue des modèles de projection 2027 disponibles**")
    st.dataframe(
        model_catalog[
            ["Type de modèle", "Institut", "Force", "Points historiques", "Pente temporelle", "Biais moyen", "Jours min", "Jours max"]
        ].sort_values(["Type de modèle", "Institut", "Force"], na_position="last"),
        width="stretch",
        hide_index=True,
        column_config={
            "Pente temporelle": st.column_config.NumberColumn("Pente temporelle", format="%.4f"),
            "Biais moyen": st.column_config.NumberColumn("Biais moyen", format="%+.2f"),
            "Jours min": st.column_config.NumberColumn("Jours min", format="%.0f"),
            "Jours max": st.column_config.NumberColumn("Jours max", format="%.0f"),
        },
    )

    calibration_chart = context.calibration_frame.copy()
    calibration_chart["pollster_force"] = calibration_chart["pollster"] + " · " + calibration_chart["force_label"]
    focus_force = st.selectbox(
        "Force à inspecter dans l'historique 2022",
        sorted(calibration_chart["force_label"].dropna().unique().tolist()),
        key="dynamic_bias_force",
    )
    force_subset = calibration_chart.loc[calibration_chart["force_label"] == focus_force].copy()
    chart = px.scatter(
        force_subset,
        x="days_until_election",
        y="bias",
        color="pollster",
        title=f"Biais historique 2022 utilisé pour projeter 2027 · {focus_force}",
        labels={"days_until_election": "Jours avant scrutin", "bias": "Biais (résultat - sondage)", "pollster": "Institut"},
    )
    chart.update_layout(**PLOT_LAYOUT_THEME)
    st.plotly_chart(chart, width="stretch", config={"displayModeBar": False, "responsive": True})

    summary = (
        corrected.groupby(["force_label", "model_source_label"], dropna=False)
        .agg(
            sondages=("poll_id", "nunique"),
            biais_moyen_projete=("dynamic_bias_2027", "mean"),
            score_brut_moyen=("estimate_percent", "mean"),
            score_corrige_moyen=("dynamically_corrected_estimate", "mean"),
        )
        .reset_index()
        .sort_values(["force_label", "sondages"], ascending=[True, False])
    )
    st.markdown("**Synthèse de projection 2027 par force politique**")
    st.dataframe(
        summary,
        width="stretch",
        hide_index=True,
        column_config={
            "biais_moyen_projete": st.column_config.NumberColumn("Biais moyen projeté", format="%+.2f"),
            "score_brut_moyen": st.column_config.NumberColumn("Score brut moyen", format="%.2f %%"),
            "score_corrige_moyen": st.column_config.NumberColumn("Score corrigé moyen 2027", format="%.2f %%"),
        },
    )

    st.markdown("**Tracé du biais projeté 2027 pour chaque sondage**")
    st.caption(
        "Lecture : le biais projeté 2027 correspond à la correction ajoutée au score brut. "
        "Un biais positif signifie que le parti est historiquement sous-estime par le sondage ; "
        "un biais negatif signifie qu'il est historiquement surestime."
    )
    st.latex(r"\mathrm{score\ corrig\acute{e}\ 2027} = \mathrm{score\ brut} + \mathrm{biais\ projet\acute{e}\ 2027}")
    available_forces = ["Toutes"] + sorted(corrected["force_label"].dropna().astype(str).unique().tolist())
    available_pollsters = ["Tous"] + sorted(corrected["polling_company"].dropna().astype(str).unique().tolist())
    c1, c2 = st.columns(2)
    selected_force = c1.selectbox("Force affichée", available_forces, key="dynamic_bias_plot_force")
    selected_pollster = c2.selectbox("Institut affiché", available_pollsters, key="dynamic_bias_plot_pollster")

    plot_frame = corrected.copy()
    if selected_force != "Toutes":
        plot_frame = plot_frame.loc[plot_frame["force_label"] == selected_force]
    if selected_pollster != "Tous":
        plot_frame = plot_frame.loc[plot_frame["polling_company"] == selected_pollster]

    plot_frame["poll_label"] = plot_frame["polling_company"].fillna("Inconnu") + " · " + plot_frame["poll_id"].fillna("n/a")
    plot_frame["hover_scenario"] = plot_frame["scenario_name"].fillna("Scénario non renseigné")
    bias_chart = px.scatter(
        plot_frame.sort_values(["publication_date", "polling_company", "poll_id"]),
        x="publication_date",
        y="dynamic_bias_2027",
        color="polling_company",
        symbol="force_label",
        hover_name="candidate_name",
        hover_data={
            "poll_id": True,
            "hover_scenario": True,
            "estimate_percent": ":.1f",
            "dynamically_corrected_estimate": ":.1f",
            "model_source_label": True,
            "publication_date": "|%d/%m/%Y",
            "polling_company": False,
            "dynamic_bias_2027": False,
            "force_label": False,
        },
        title="Biais projeté 2027 appliqué à chaque sondage",
        labels={
            "publication_date": "Publication",
            "dynamic_bias_2027": "Biais projeté 2027",
            "polling_company": "Institut",
            "force_label": "Force",
            "hover_scenario": "Scénario",
            "estimate_percent": "Score brut",
            "dynamically_corrected_estimate": "Score corrigé 2027",
            "model_source_label": "Source du modèle",
        },
    )
    bias_chart.update_traces(marker={"size": 9, "opacity": 0.78, "line": {"width": 0.8, "color": "#ffffff"}})
    bias_chart.update_layout(**PLOT_LAYOUT_THEME)
    st.plotly_chart(bias_chart, width="stretch", config={"displayModeBar": False, "responsive": True})

    detailed = corrected[
        [
            "publication_date",
            "polling_company",
            "poll_id",
            "scenario_name",
            "candidate_name",
            "candidate_party",
            "force_label",
            "estimate_percent",
            "dynamic_bias_2027",
            "dynamically_corrected_estimate",
            "model_source_label",
            "source_url",
        ]
    ].rename(
        columns={
            "publication_date": "Publication",
            "polling_company": "Institut",
            "poll_id": "Poll ID",
            "scenario_name": "Scénario",
            "candidate_name": "Candidat",
            "candidate_party": "Parti",
            "force_label": "Force",
            "estimate_percent": "Score brut",
            "dynamic_bias_2027": "Biais projeté 2027",
            "dynamically_corrected_estimate": "Score corrigé 2027",
            "model_source_label": "Source du modèle",
            "source_url": "Lien source",
        }
    )
    st.markdown("**Application de la projection corrigée à tous les sondages 2027 du premier tour**")
    st.dataframe(
        detailed.sort_values(["Publication", "Institut", "Scénario", "Parti"], ascending=[False, True, True, True]),
        width="stretch",
        hide_index=True,
        column_config={
            "Score brut": st.column_config.NumberColumn("Score brut", format="%.1f %%"),
            "Biais projeté 2027": st.column_config.NumberColumn("Biais projeté 2027", format="%+.2f"),
            "Score corrigé 2027": st.column_config.NumberColumn("Score corrigé 2027", format="%.1f %%"),
            "Lien source": st.column_config.LinkColumn("Lien source"),
        },
    )
