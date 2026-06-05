from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from presidentielle2027.analytics.historical_corrections import (
    CURRENT_ELECTION_DATE,
    apply_second_round_legislative_correction,
    apply_first_round_historical_correction,
    get_reference_dir,
)
from presidentielle2027.analytics.uncertainty import approximate_margin_of_error
from presidentielle2027.analytics.trends import build_lowess_curve, exploratory_extension
from presidentielle2027.dashboard.colors import get_political_color
from presidentielle2027.dashboard.methodology_text import corrected_dataset_methodology_html, second_round_methodology_html
from presidentielle2027.dashboard.party_assets import build_candidate_summary_table, build_force_summary_table
from presidentielle2027.dashboard.plot_theme import PLOT_LAYOUT_THEME
from presidentielle2027.dashboard.table_views import clean_user_facing_frame


REQUIRED_CORRECTION_COLUMNS = {
    "structural_bias_component": 0.0,
    "temporal_bias_component": 0.0,
    "trajectory_bias_component": 0.0,
    "legislative_2024_bias_component": 0.0,
    "historical_2022_weight": 1.0,
    "legislative_2024_weight": 0.0,
    "representativity_bias_component": 0.0,
    "historical_correction": 0.0,
    "historically_corrected_estimate": 0.0,
}

REQUIRED_EXPORT_COLUMNS = {
    "publication_date": pd.NaT,
    "polling_company": "Non renseigné",
    "candidate_name": "Non renseigné",
    "candidate_party": "Non renseigné",
    "political_family": "Non renseigné",
    "estimate_percent": 0.0,
    "structural_bias_component": 0.0,
    "temporal_bias_component": 0.0,
    "trajectory_bias_component": 0.0,
    "legislative_2024_bias_component": 0.0,
    "historical_2022_weight": 1.0,
    "legislative_2024_weight": 0.0,
    "historical_correction": 0.0,
    "historically_corrected_estimate": 0.0,
    "sample_size": pd.NA,
    "source_url": pd.NA,
    "status": "données insuffisantes",
    "scenario_name": "Non renseigné",
    "round": "Non renseigné",
}

FRENCH_BLOC_LABELS = {
    "gauche": "Gauche",
    "centre": "Centre",
    "droite": "Droite",
    "extrême_droite": "Extrême droite",
    "autres": "Autres",
}

SECOND_ROUND_SCENARIO_LABELS = {
    "Attal vs Bardella": "Hypothèse Attal – Bardella",
    "Mélenchon vs Bardella": "Hypothèse Mélenchon – Bardella",
    "Philippe vs Bardella": "Hypothèse Philippe – Bardella",
    "Glucksmann vs Bardella": "Hypothèse Glucksmann – Bardella",
    "Retailleau vs Bardella": "Hypothèse Retailleau – Bardella",
    "Philippe vs Le Pen": "Hypothèse Philippe – Le Pen",
    "Attal vs Le Pen": "Hypothèse Attal – Le Pen",
    "Mélenchon vs Le Pen": "Hypothèse Mélenchon – Le Pen",
    "Ruffin vs Le Pen": "Hypothèse Ruffin – Le Pen",
    "Macron vs Le Pen rerun": "Hypothèse Macron – Le Pen",
    "Macron vs Le Pen official 2022": "Référence 2022 · Macron – Le Pen",
}


def _prepare_2027_corrected_frame(frame: pd.DataFrame, grouping: str) -> pd.DataFrame:
    working = frame.copy()
    for column, default_value in REQUIRED_CORRECTION_COLUMNS.items():
        if column not in working.columns:
            working[column] = default_value

    if grouping == "Parti politique":
        working["force_name"] = working["candidate_party"].fillna("Sans parti")
    else:
        working["force_name"] = working["political_family"].fillna("Autre")
    return working


def _build_quality_alerts(frame: pd.DataFrame) -> pd.DataFrame:
    alerts: list[dict[str, object]] = []
    if frame.empty:
        return pd.DataFrame()

    invalid_scores = frame.loc[(frame["historically_corrected_estimate"] < 0) | (frame["historically_corrected_estimate"] > 100)]
    for row in invalid_scores.itertuples(index=False):
        alerts.append({"Type": "Score corrigé", "Message": f"Score corrigé hors bornes pour {row.candidate_name}."})

    invalid_sample = frame.loc[frame["sample_size"].notna() & (pd.to_numeric(frame["sample_size"], errors="coerce") <= 0)]
    for row in invalid_sample.itertuples(index=False):
        alerts.append({"Type": "Échantillon", "Message": f"Échantillon non valide pour le sondage {row.poll_id}."})

    missing_publication = frame.loc[frame["publication_date"].isna()]
    for row in missing_publication.itertuples(index=False):
        alerts.append({"Type": "Publication", "Message": f"Date de publication absente pour le sondage {row.poll_id}."})

    if {"poll_id", "scenario_name", "estimate_percent"}.issubset(frame.columns):
        sums = (
            frame.groupby(["poll_id", "scenario_name"], dropna=False)["estimate_percent"]
            .sum()
            .reset_index(name="score_sum")
        )
        incoherent = sums.loc[(sums["score_sum"] < 85) | (sums["score_sum"] > 105)]
        for row in incoherent.itertuples(index=False):
            alerts.append(
                {
                    "Type": "Somme des scores",
                    "Message": f"Somme des scores incohérente : vérifier le parsing du sondage {row.poll_id} ({row.score_sum:.1f}%).",
                }
            )
    return pd.DataFrame(alerts)


def _build_corrected_export_table(frame: pd.DataFrame) -> pd.DataFrame:
    export_frame = frame.copy()
    for column, default_value in REQUIRED_EXPORT_COLUMNS.items():
        if column not in export_frame.columns:
            export_frame[column] = default_value
    export_frame["correction_totale"] = export_frame["historical_correction"]
    export_frame["marge_erreur_95"] = export_frame.apply(
        lambda row: approximate_margin_of_error(row.get("sample_size"), row.get("estimate_percent", 50.0)),
        axis=1,
    )
    export_frame["intervalle_bas_95"] = (export_frame["estimate_percent"] - export_frame["marge_erreur_95"].fillna(0.0)).clip(lower=0.0)
    export_frame["intervalle_haut_95"] = (export_frame["estimate_percent"] + export_frame["marge_erreur_95"].fillna(0.0)).clip(upper=100.0)
    export_frame["status"] = export_frame["status"].fillna("données insuffisantes")
    return export_frame[
        [
            "publication_date",
            "polling_company",
            "candidate_name",
            "candidate_party",
            "political_family",
            "estimate_percent",
            "structural_bias_component",
            "temporal_bias_component",
            "trajectory_bias_component",
            "legislative_2024_bias_component",
            "historical_2022_weight",
            "legislative_2024_weight",
            "correction_totale",
            "historically_corrected_estimate",
            "sample_size",
            "marge_erreur_95",
            "intervalle_bas_95",
            "intervalle_haut_95",
            "source_url",
            "status",
            "scenario_name",
            "round",
        ]
    ].rename(
        columns={
            "publication_date": "Publication",
            "polling_company": "Institut",
            "candidate_name": "Candidat",
            "candidate_party": "Parti",
            "political_family": "Famille politique",
            "estimate_percent": "Score brut",
            "structural_bias_component": "Biais structurel",
            "temporal_bias_component": "Biais temporel",
            "trajectory_bias_component": "Biais trajectoire",
            "legislative_2024_bias_component": "Biais blocs 2024",
            "historical_2022_weight": "Poids 2022",
            "legislative_2024_weight": "Poids 2024",
            "correction_totale": "Correction totale",
            "historically_corrected_estimate": "Score corrigé",
            "sample_size": "Échantillon",
            "marge_erreur_95": "Marge d’erreur 95",
            "intervalle_bas_95": "Intervalle bas 95",
            "intervalle_haut_95": "Intervalle haut 95",
            "source_url": "Lien source",
            "status": "Statut",
            "scenario_name": "Scénario",
            "round": "Tour",
        }
    )


def _build_2027_grouped(frame: pd.DataFrame) -> pd.DataFrame:
    grouped = (
        frame.groupby(["publication_date", "force_name"], dropna=False)
        .agg(
            raw_estimate=("estimate_percent", "mean"),
            corrected_estimate=("historically_corrected_estimate", "mean"),
            candidate_party=("candidate_party", "first"),
            political_family=("political_family", "first"),
            structural_bias=("structural_bias_component", "mean"),
            temporal_bias=("temporal_bias_component", "mean"),
            trajectory_bias=("trajectory_bias_component", "mean"),
            legislative_2024_bias=("legislative_2024_bias_component", "mean"),
            weight_2022=("historical_2022_weight", "mean"),
            weight_2024=("legislative_2024_weight", "mean"),
            total_correction=("historical_correction", "mean"),
        )
        .reset_index()
        .sort_values(["force_name", "publication_date"])
    )
    return grouped


def _format_second_round_scenario(value: object) -> str:
    label = str(value).strip() if value not in (None, "") else "Scénario non renseigné"
    return SECOND_ROUND_SCENARIO_LABELS.get(label, label)


def _build_second_round_export_table(frame: pd.DataFrame) -> pd.DataFrame:
    export_frame = frame.copy()
    export_frame["marge_erreur_95"] = export_frame.apply(
        lambda row: approximate_margin_of_error(row.get("sample_size"), row.get("estimate_percent", 50.0)),
        axis=1,
    )
    export_frame["intervalle_bas_95"] = (
        export_frame["legislatively_corrected_estimate"] - export_frame["marge_erreur_95"].fillna(0.0)
    ).clip(lower=0.0)
    export_frame["intervalle_haut_95"] = (
        export_frame["legislatively_corrected_estimate"] + export_frame["marge_erreur_95"].fillna(0.0)
    ).clip(upper=100.0)
    return export_frame[
        [
            "publication_date",
            "polling_company",
            "scenario_name",
            "candidate_name",
            "candidate_party",
            "political_family",
            "broad_bloc",
            "estimate_percent",
            "legislative_benchmark",
            "legislative_poll_bias",
            "legislative_seat_premium",
            "legislatively_corrected_estimate",
            "sample_size",
            "marge_erreur_95",
            "intervalle_bas_95",
            "intervalle_haut_95",
            "source_url",
        ]
    ].rename(
        columns={
            "publication_date": "Publication",
            "polling_company": "Institut",
            "scenario_name": "Scénario",
            "candidate_name": "Candidat",
            "candidate_party": "Parti",
            "political_family": "Famille politique",
            "broad_bloc": "Bloc",
            "estimate_percent": "Score brut",
            "legislative_benchmark": "Benchmark 2024",
            "legislative_poll_bias": "Biais de bloc",
            "legislative_seat_premium": "Prime sièges",
            "legislatively_corrected_estimate": "Score corrigé",
            "sample_size": "Échantillon",
            "marge_erreur_95": "Marge d’erreur 95",
            "intervalle_bas_95": "Intervalle bas 95",
            "intervalle_haut_95": "Intervalle haut 95",
            "source_url": "Lien source",
        }
    )


def _render_corrected_first_round_section(frame: pd.DataFrame) -> tuple[pd.DataFrame, object, object]:
    working = frame.loc[(frame["round"] == "first_round") & (~frame["is_generic_bloc"])].copy()
    if working.empty:
        st.info("Aucune donnée de premier tour exploitable.")
        return pd.DataFrame(), None, None

    pollsters = ["Tous"] + sorted(working["polling_company"].dropna().astype(str).unique().tolist())
    min_date = working["publication_date"].min().date() if working["publication_date"].notna().any() else date.today()
    max_date = working["publication_date"].max().date() if working["publication_date"].notna().any() else date.today()

    parties = ["Tous"] + sorted(working["candidate_party"].dropna().astype(str).unique().tolist())
    rounds = ["Tous"] + sorted(working["round"].dropna().astype(str).unique().tolist())

    c1, c2, c3, c4, c5 = st.columns([1.1, 1.4, 1.2, 1.2, 1.0])
    pollster = c1.selectbox("Institut", pollsters, key="corrected_pollster")
    period = c2.date_input("Période", value=(min_date, max_date), min_value=min_date, max_value=max_date, key="corrected_period")
    grouping = c3.selectbox("Regrouper la correction par", ["Parti politique", "Famille politique"], key="corrected_grouping")
    party = c4.selectbox("Parti", parties, key="corrected_party")
    round_filter = c5.selectbox("Tour", rounds, key="corrected_round")

    filtered = working.copy()
    if pollster != "Tous":
        filtered = filtered.loc[filtered["polling_company"] == pollster]
    if party != "Tous":
        filtered = filtered.loc[filtered["candidate_party"] == party]
    if round_filter != "Tous":
        filtered = filtered.loc[filtered["round"] == round_filter]
    if isinstance(period, tuple) and len(period) == 2:
        filtered = filtered.loc[
            filtered["publication_date"].between(pd.Timestamp(period[0]), pd.Timestamp(period[1]), inclusive="both")
        ]
    if filtered.empty:
        st.warning("Aucune donnée disponible pour ces filtres.")
        return pd.DataFrame(), None, period

    corrected, context = apply_first_round_historical_correction(filtered, get_reference_dir(Path.cwd()))
    corrected = _prepare_2027_corrected_frame(corrected, grouping)
    quality_alerts = _build_quality_alerts(corrected)

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Périmètre 2027", "Sondages du premier tour")
    col2.metric("Lignes 2027", int(len(corrected)))
    col3.metric("Instituts 2027", int(corrected["polling_company"].nunique()))
    latest_publication = corrected["publication_date"].max()
    col4.metric("Dernière publication", latest_publication.strftime("%d/%m/%Y") if pd.notna(latest_publication) else "n.d.")

    if not quality_alerts.empty:
        st.warning("Des contrôles qualité ont signalé des incohérences dans le dataset filtré.")
        st.dataframe(quality_alerts, width="stretch", hide_index=True)

    summary_source = (
        corrected.sort_values(["publication_date", "historically_corrected_estimate"], ascending=[False, False])
        .groupby("force_name", dropna=False)
        .head(1)
        .copy()
    )
    force_summary = build_force_summary_table(
        summary_source.rename(columns={"historically_corrected_estimate": "corrected_value"}),
        "force_name",
        "corrected_value",
    )
    if not force_summary.empty:
        st.dataframe(
            force_summary,
            width="stretch",
            hide_index=True,
            column_config={
                "party_logo": st.column_config.ImageColumn("Logo"),
                "force_name": st.column_config.TextColumn("Force"),
                "candidate_party": st.column_config.TextColumn("Parti"),
                "political_family": st.column_config.TextColumn("Famille"),
                "value_display": st.column_config.TextColumn("Dernière valeur corrigée"),
            },
        )

    grouped = _build_2027_grouped(corrected)
    _render_2027_chart(grouped, grouping)

    latest_summary = (
        grouped.sort_values(["publication_date", "corrected_estimate"], ascending=[False, False])
        .groupby("force_name", dropna=False)
        .head(1)
        .copy()
        .rename(
            columns={
                "force_name": "Candidat",
                "candidate_party": "Parti",
                "raw_estimate": "Brut",
                "corrected_estimate": "Corrigé 2027",
                "structural_bias": "Biais structurel",
                "temporal_bias": "Biais temps long",
                "trajectory_bias": "Biais trajectoire",
                "total_correction": "Correction totale",
            }
        )
    )

    if not context.bias_catalog.empty:
        latest_summary = latest_summary.merge(
            context.bias_catalog[["force_label", "status"]].rename(columns={"force_label": "Parti", "status": "Statut"}),
            on="Parti",
            how="left",
        )
    else:
        latest_summary["Statut"] = "données insuffisantes"

    latest_summary["Sondages"] = (
        corrected.groupby("force_name", dropna=False)["poll_id"].nunique().reindex(latest_summary["Candidat"]).fillna(0).astype(int).to_numpy()
        if "poll_id" in corrected.columns
        else 0
    )

    st.dataframe(
        latest_summary[
            [
                "Candidat",
                "Parti",
                "Brut",
                "Corrigé 2027",
                "Sondages",
                "Statut",
                "Biais structurel",
                "Biais temps long",
                "Biais trajectoire",
                "Correction totale",
            ]
        ],
        width="stretch",
        hide_index=True,
        column_config={
            "Brut": st.column_config.NumberColumn("Brut", format="%.1f %%"),
            "Corrigé 2027": st.column_config.NumberColumn("Corrigé 2027", format="%.1f %%"),
            "Sondages": st.column_config.NumberColumn("Sondages", format="%d"),
            "Biais structurel": st.column_config.NumberColumn("Biais structurel", format="%.2f"),
            "Biais temps long": st.column_config.NumberColumn("Biais temps long", format="%.2f"),
            "Biais trajectoire": st.column_config.NumberColumn("Biais trajectoire", format="%.2f"),
            "Correction totale": st.column_config.NumberColumn("Correction totale", format="%.2f"),
        },
    )

    export_table = _build_corrected_export_table(corrected)
    export_table_clean = clean_user_facing_frame(export_table)
    st.markdown("**Dataset corrigé détaillé**")
    st.dataframe(
        export_table_clean,
        width="stretch",
        hide_index=True,
        column_config={
            "Score brut": st.column_config.NumberColumn("Score brut", format="%.1f %%"),
            "Biais structurel": st.column_config.NumberColumn("Biais structurel", format="%.2f"),
            "Biais temporel": st.column_config.NumberColumn("Biais temporel", format="%.2f"),
            "Biais trajectoire": st.column_config.NumberColumn("Biais trajectoire", format="%.2f"),
            "Correction totale": st.column_config.NumberColumn("Correction totale", format="%.2f"),
            "Score corrigé": st.column_config.NumberColumn("Score corrigé", format="%.1f %%"),
            "Échantillon": st.column_config.NumberColumn("Échantillon", format="%d"),
            "Marge d’erreur 95": st.column_config.NumberColumn("Marge d’erreur 95", format="%.2f %%"),
            "Intervalle bas 95": st.column_config.NumberColumn("Intervalle bas 95", format="%.2f %%"),
            "Intervalle haut 95": st.column_config.NumberColumn("Intervalle haut 95", format="%.2f %%"),
            "Lien source": st.column_config.LinkColumn("Lien source"),
        },
    )
    csv_payload = export_table.to_csv(index=False).encode("utf-8")
    json_payload = export_table.to_json(orient="records", force_ascii=False, date_format="iso").encode("utf-8")
    d1, d2 = st.columns(2)
    d1.download_button("Télécharger CSV", data=csv_payload, file_name="dataset_corrige_premier_tour_2027.csv", mime="text/csv")
    d2.download_button("Télécharger JSON", data=json_payload, file_name="dataset_corrige_premier_tour_2027.json", mime="application/json")
    return corrected, context, period


def _render_corrected_second_round_section(frame: pd.DataFrame) -> None:
    working = frame.loc[frame["round"] == "second_round"].copy()
    if working.empty:
        st.info("Aucune hypothèse de second tour disponible.")
        return
    if "source_url" not in working.columns:
        working["source_url"] = pd.NA

    st.markdown(second_round_methodology_html(), unsafe_allow_html=True)
    working["scenario_label"] = working["scenario_name"].map(_format_second_round_scenario)
    working["candidate_label"] = working["candidate_name"].fillna("Inconnu") + " · " + working["candidate_party"].fillna("Sans parti")

    candidate_catalog = (
        working[["candidate_name", "candidate_party", "candidate_label"]]
        .dropna(subset=["candidate_name"])
        .drop_duplicates()
        .sort_values(["candidate_name", "candidate_party"])
    )
    candidate_labels = candidate_catalog["candidate_label"].tolist()
    if len(candidate_labels) < 2:
        st.info("Le second tour corrigé nécessite au moins deux candidats comparables.")
        return

    pollsters = ["Tous"] + sorted(working["polling_company"].dropna().astype(str).unique().tolist())
    scenarios = ["Toutes"] + sorted(working["scenario_label"].dropna().astype(str).unique().tolist())
    min_date = working["publication_date"].min().date() if working["publication_date"].notna().any() else date.today()
    max_date = working["publication_date"].max().date() if working["publication_date"].notna().any() else date.today()

    c1, c2 = st.columns(2)
    candidate_a = c1.selectbox("Candidat A", candidate_labels, index=0, key="corrected_second_round_candidate_a")
    candidate_b_options = [label for label in candidate_labels if label != candidate_a]
    candidate_b = c2.selectbox("Candidat B", candidate_b_options, index=0, key="corrected_second_round_candidate_b")

    c3, c4, c5, c6, c7 = st.columns([1.0, 1.0, 1.4, 0.8, 0.7])
    scenario_filter = c3.selectbox("Hypothèse", scenarios, key="corrected_second_round_scenario")
    pollster = c4.selectbox("Institut", pollsters, key="corrected_second_round_pollster")
    period = c5.date_input("Période", value=(min_date, max_date), min_value=min_date, max_value=max_date, key="corrected_second_round_period")
    polynomial_order = c6.selectbox("Ordre", [1, 2, 3, 4, 5, 6], index=3, key="corrected_second_round_order")
    show_extension = c7.checkbox("Pointillé", value=True, key="corrected_second_round_extension")

    filtered = working.loc[working["candidate_label"].isin([candidate_a, candidate_b])].copy()
    if scenario_filter != "Toutes":
        filtered = filtered.loc[filtered["scenario_label"] == scenario_filter]
    if pollster != "Tous":
        filtered = filtered.loc[filtered["polling_company"] == pollster]
    if isinstance(period, tuple) and len(period) == 2:
        filtered = filtered.loc[
            filtered["publication_date"].between(pd.Timestamp(period[0]), pd.Timestamp(period[1]), inclusive="both")
        ]
        period_start_ts = pd.Timestamp(period[0])
        period_end_ts = pd.Timestamp(period[1])
    else:
        period_start_ts = pd.Timestamp(min_date)
        period_end_ts = pd.Timestamp(max_date)
    if filtered.empty:
        st.warning("Aucune donnée disponible pour cette combinaison.")
        return

    filtered = (
        filtered.groupby(["scenario_name", "publication_date", "poll_id"], dropna=False)
        .filter(lambda group: set(group["candidate_label"]) == {candidate_a, candidate_b})
        .copy()
    )
    if filtered.empty:
        st.warning("Aucun duel complet correspondant n’existe dans le dataset pour ces deux candidats.")
        return

    corrected = apply_second_round_legislative_correction(filtered, get_reference_dir(Path.cwd()))

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Duel", f"{candidate_a.split(' · ')[0]} vs {candidate_b.split(' · ')[0]}")
    col2.metric("Lignes", int(len(corrected)))
    col3.metric("Instituts", int(corrected["polling_company"].nunique()))
    col4.metric("Scénarios", int(corrected["scenario_name"].nunique()))

    summary = build_candidate_summary_table(corrected, "legislatively_corrected_estimate")
    if not summary.empty:
        st.dataframe(
            summary,
            width="stretch",
            hide_index=True,
            column_config={
                "party_logo": st.column_config.ImageColumn("Logo"),
                "candidate_name": st.column_config.TextColumn("Candidat"),
                "candidate_party": st.column_config.TextColumn("Parti"),
                "political_family": st.column_config.TextColumn("Famille"),
                "value_display": st.column_config.TextColumn("Dernière valeur corrigée"),
            },
        )

    figure = go.Figure()
    insufficient: list[str] = []
    for candidate_name, group in corrected.groupby("candidate_name", dropna=False):
        ordered = group.sort_values("publication_date")
        party = ordered["candidate_party"].dropna().iloc[0] if ordered["candidate_party"].notna().any() else None
        family = ordered["political_family"].dropna().iloc[0] if ordered["political_family"].notna().any() else None
        color = get_political_color(party, family)
        figure.add_trace(
            go.Scatter(
                x=ordered["publication_date"],
                y=ordered["estimate_percent"],
                mode="markers",
                marker={"size": 7, "color": color, "opacity": 0.30, "line": {"color": "#ffffff", "width": 1.0}},
                name=f"{candidate_name} - brut",
                legendgroup=str(candidate_name),
                showlegend=False,
                hovertemplate="%{x|%d/%m/%Y}<br>%{y:.1f}%<br>Brut<extra></extra>",
            )
        )
        smoothed = build_lowess_curve(
            ordered,
            "legislatively_corrected_estimate",
            frac=0.32,
            degree=polynomial_order,
            method="polynomial",
        )
        if smoothed is None:
            insufficient.append(str(candidate_name))
        else:
            figure.add_trace(
                go.Scatter(
                    x=smoothed["publication_date"],
                    y=smoothed["score_smooth"],
                    mode="lines",
                    line={"width": 2.8, "color": color},
                    name=str(candidate_name),
                    legendgroup=str(candidate_name),
                    showlegend=True,
                    hovertemplate=f"{candidate_name}<br>%{{x|%d/%m/%Y}}<br>%{{y:.1f}}%<extra></extra>",
                )
            )
        if show_extension:
            extension = exploratory_extension(
                ordered,
                election_date=CURRENT_ELECTION_DATE,
                value_column="legislatively_corrected_estimate",
                recent_days=30,
                degree=polynomial_order,
                method="polynomial",
            )
            if extension is not None:
                figure.add_trace(
                    go.Scatter(
                        x=extension.x,
                        y=extension.y,
                        mode="lines",
                        line={"width": 1.8, "color": color, "dash": "dot"},
                        name=f"{candidate_name} - prolongation",
                        legendgroup=str(candidate_name),
                        showlegend=False,
                    )
                )

    figure.update_layout(
        title="Second tour 2027 corrigé · benchmark 2024 et tendance lissée",
        xaxis_title="Date de publication",
        yaxis_title="Intentions de vote corrigées (%)",
        **PLOT_LAYOUT_THEME,
    )
    chart_end_ts = max(period_end_ts, CURRENT_ELECTION_DATE) if show_extension else period_end_ts
    figure.update_xaxes(range=[period_start_ts, chart_end_ts])
    figure.update_yaxes(ticksuffix=" %")
    st.plotly_chart(figure, width="stretch", config={"displayModeBar": False, "responsive": True})
    if insufficient:
        st.caption("Tendance non calculée pour certaines séries : données insuffisantes ou scénarios non comparables.")

    latest_summary = (
        corrected.sort_values(["publication_date", "legislatively_corrected_estimate"], ascending=[False, False])
        .groupby("candidate_name", dropna=False)
        .head(1)[
            [
                "candidate_name",
                "candidate_party",
                "broad_bloc",
                "estimate_percent",
                "legislative_benchmark",
                "legislative_poll_bias",
                "legislative_seat_premium",
                "legislatively_corrected_estimate",
            ]
        ]
        .rename(
            columns={
                "candidate_name": "Candidat",
                "candidate_party": "Parti",
                "broad_bloc": "Bloc",
                "estimate_percent": "Brut",
                "legislative_benchmark": "Benchmark 2024",
                "legislative_poll_bias": "Biais de bloc",
                "legislative_seat_premium": "Prime sièges",
                "legislatively_corrected_estimate": "Corrigé second tour",
            }
        )
    )
    latest_summary["Bloc"] = latest_summary["Bloc"].map(lambda value: FRENCH_BLOC_LABELS.get(value, value))
    st.dataframe(
        latest_summary,
        width="stretch",
        hide_index=True,
        column_config={
            "Brut": st.column_config.NumberColumn("Brut", format="%.1f %%"),
            "Benchmark 2024": st.column_config.NumberColumn("Benchmark 2024", format="%.1f %%"),
            "Biais de bloc": st.column_config.NumberColumn("Biais de bloc", format="%.2f"),
            "Prime sièges": st.column_config.NumberColumn("Prime sièges", format="%.2f"),
            "Corrigé second tour": st.column_config.NumberColumn("Corrigé second tour", format="%.1f %%"),
        },
    )

    export_table = clean_user_facing_frame(_build_second_round_export_table(corrected))
    st.markdown("**Dataset corrigé détaillé du second tour**")
    st.dataframe(
        export_table,
        width="stretch",
        hide_index=True,
        column_config={
            "Score brut": st.column_config.NumberColumn("Score brut", format="%.1f %%"),
            "Benchmark 2024": st.column_config.NumberColumn("Benchmark 2024", format="%.1f %%"),
            "Biais de bloc": st.column_config.NumberColumn("Biais de bloc", format="%.2f"),
            "Prime sièges": st.column_config.NumberColumn("Prime sièges", format="%.2f"),
            "Score corrigé": st.column_config.NumberColumn("Score corrigé", format="%.1f %%"),
            "Échantillon": st.column_config.NumberColumn("Échantillon", format="%d"),
            "Marge d’erreur 95": st.column_config.NumberColumn("Marge d’erreur 95", format="%.2f %%"),
            "Intervalle bas 95": st.column_config.NumberColumn("Intervalle bas 95", format="%.2f %%"),
            "Intervalle haut 95": st.column_config.NumberColumn("Intervalle haut 95", format="%.2f %%"),
            "Lien source": st.column_config.LinkColumn("Lien source"),
        },
    )
    csv_payload = export_table.to_csv(index=False).encode("utf-8")
    json_payload = export_table.to_json(orient="records", force_ascii=False, date_format="iso").encode("utf-8")
    d1, d2 = st.columns(2)
    d1.download_button("Télécharger CSV second tour", data=csv_payload, file_name="dataset_corrige_second_tour_2027.csv", mime="text/csv")
    d2.download_button("Télécharger JSON second tour", data=json_payload, file_name="dataset_corrige_second_tour_2027.json", mime="application/json")


def _render_2027_chart(grouped: pd.DataFrame, grouping: str) -> None:
    figure = go.Figure()
    insufficient: list[str] = []
    for force_name, group in grouped.groupby("force_name", dropna=False):
        ordered = group.sort_values("publication_date")
        party = ordered["candidate_party"].dropna().iloc[0] if ordered["candidate_party"].notna().any() else None
        family = ordered["political_family"].dropna().iloc[0] if ordered["political_family"].notna().any() else None
        color = get_political_color(party, family)
        figure.add_trace(
            go.Scatter(
                x=ordered["publication_date"],
                y=ordered["raw_estimate"],
                mode="markers",
                marker={"size": 6, "color": color, "opacity": 0.25},
                name=f"{force_name} - brut",
                legendgroup=str(force_name),
                showlegend=False,
                hoverinfo="skip",
            )
        )
        smoothed = build_lowess_curve(ordered, "corrected_estimate", frac=0.30)
        if smoothed is None:
            insufficient.append(str(force_name))
        else:
            figure.add_trace(
                go.Scatter(
                    x=smoothed["publication_date"],
                    y=smoothed["score_smooth"],
                    mode="lines",
                    line={"width": 2.8, "color": color},
                    name=str(force_name),
                    legendgroup=str(force_name),
                    showlegend=True,
                    hovertemplate=f"{force_name}<br>%{{x|%d/%m/%Y}}<br>%{{y:.1f}}%<extra></extra>",
                )
            )
    figure.update_layout(
        title=f"2027 corrigé · points et ajustement polynomial par {grouping.lower()}",
        xaxis_title="Date de publication",
        yaxis_title="Intentions de vote (%)",
        **PLOT_LAYOUT_THEME,
    )
    figure.update_yaxes(ticksuffix=" %")
    st.plotly_chart(figure, width="stretch", config={"displayModeBar": False, "responsive": True})
    if insufficient:
        st.caption("Tendance non calculée pour certaines forces : données insuffisantes ou scénarios non comparables.")


def _render_2022_ui(context, selected_period: tuple[date, date] | None = None) -> None:
    historical_2022 = context.historical_errors.copy()
    if historical_2022.empty:
        st.info("Aucune donnée 2022 disponible.")
        return

    historical_2022["publication_date"] = pd.to_datetime(historical_2022["fieldwork_end_date"], errors="coerce")
    historical_2022["force_name"] = historical_2022["force_label"].fillna("Autre")
    if isinstance(selected_period, tuple) and len(selected_period) == 2:
        historical_2022 = historical_2022.loc[
            historical_2022["publication_date"].between(
                pd.Timestamp(selected_period[0]),
                pd.Timestamp(selected_period[1]),
                inclusive="both",
            )
        ].copy()
    if historical_2022.empty:
        st.info("Aucune donnée 2022 disponible pour cette période.")
        return

    summary_source = (
        historical_2022.sort_values(["publication_date", "estimate_percent"], ascending=[False, False])
        .groupby("force_name", dropna=False)
        .head(1)
        .copy()
    )
    force_summary = build_force_summary_table(
        summary_source.rename(columns={"estimate_percent": "historical_value"}),
        "force_name",
        "historical_value",
        party_column="force_label",
        family_column="political_family",
    )
    if not force_summary.empty:
        st.dataframe(
            force_summary,
            width="stretch",
            hide_index=True,
            column_config={
                "party_logo": st.column_config.ImageColumn("Logo"),
                "force_name": st.column_config.TextColumn("Force 2022"),
                "candidate_party": st.column_config.TextColumn("Parti"),
                "political_family": st.column_config.TextColumn("Famille"),
                "value_display": st.column_config.TextColumn("Dernier sondage 2022"),
            },
        )

    grouped = (
        historical_2022.groupby(["publication_date", "force_label"], dropna=False)
        .agg(
            estimate_percent=("estimate_percent", "mean"),
            result_percent=("result_percent", "first"),
            political_family=("political_family", "first"),
        )
        .reset_index()
        .sort_values(["force_label", "publication_date"])
    )
    figure = go.Figure()
    for force_name, group in grouped.groupby("force_label", dropna=False):
        ordered = group.sort_values("publication_date")
        family = ordered["political_family"].dropna().iloc[0] if ordered["political_family"].notna().any() else None
        color = get_political_color(force_name, family)
        result_value = ordered["result_percent"].dropna().iloc[0] if ordered["result_percent"].notna().any() else None
        figure.add_trace(
            go.Scatter(
                x=ordered["publication_date"],
                y=ordered["estimate_percent"],
                mode="markers",
                marker={"size": 5, "color": color, "opacity": 0.30},
                name=f"{force_name} - sondages",
                legendgroup=f"2022-{force_name}",
                showlegend=False,
                hoverinfo="skip",
            )
        )
        if pd.notna(result_value):
            figure.add_hline(
                y=float(result_value),
                line_width=1,
                line_dash="dot",
                line_color=color,
                opacity=0.55,
            )

    figure.update_layout(
        title="2022 · sondages et résultat final",
        xaxis_title="Date terrain / publication",
        yaxis_title="Intentions de vote / résultat (%)",
        **PLOT_LAYOUT_THEME,
    )
    figure.update_yaxes(ticksuffix=" %")
    st.plotly_chart(figure, width="stretch", config={"displayModeBar": False, "responsive": True})
    st.caption("Aucune droite de tendance n’est affichée. Les lignes horizontales indiquent uniquement le résultat final.")

    tabs = st.tabs(["Sondages 2022", "Résultats 2022", "Biais 2022", "Statut des calculs"])
    with tabs[0]:
        available = [
            column
            for column in [
                "pollster",
                "fieldwork_end_date",
                "candidate_name",
                "force_label",
                "estimate_percent",
                "result_percent",
                "historical_error",
                "days_until_election",
            ]
            if column in historical_2022.columns
        ]
        st.dataframe(historical_2022[available], width="stretch", hide_index=True)
    with tabs[1]:
        results = (
            historical_2022[["force_label", "candidate_name", "result_percent"]]
            .dropna(subset=["force_label", "result_percent"])
            .drop_duplicates()
            .sort_values("result_percent", ascending=False)
        )
        st.dataframe(results, width="stretch", hide_index=True)
    with tabs[2]:
        if not context.bias_catalog.empty:
            structural = context.bias_catalog[
                [
                    "force_label",
                    "structural_bias",
                    "temporal_bias",
                    "trajectory_bias",
                    "total_bias",
                ]
            ].copy()
            st.dataframe(
                structural.rename(
                    columns={
                        "force_label": "Force",
                        "structural_bias": "Biais structurel",
                        "temporal_bias": "Biais temps long",
                        "trajectory_bias": "Biais trajectoire",
                        "total_bias": "Correction totale",
                    }
                ),
                width="stretch",
                hide_index=True,
            )
        else:
            st.info("Aucun biais calculé.")
    with tabs[3]:
        if not context.bias_catalog.empty:
            status_frame = context.bias_catalog[
                [
                    "force_label",
                    "n_polls_used",
                    "result_percent",
                    "mean_error",
                    "uncertainty",
                    "status",
                ]
            ].copy()
            st.dataframe(
                status_frame.rename(
                    columns={
                        "force_label": "Force",
                        "n_polls_used": "Sondages historiques",
                        "result_percent": "Résultat réel 2022",
                        "mean_error": "Erreur moyenne",
                        "uncertainty": "Incertitude",
                        "status": "Statut",
                    }
                ),
                width="stretch",
                hide_index=True,
            )
        else:
            st.info("Aucun statut disponible.")


def render_corrected_dataset_page(frame: pd.DataFrame) -> None:
    st.subheader("Dataset corrigé 2027")
    st.markdown(corrected_dataset_methodology_html(), unsafe_allow_html=True)
    first_tab, second_tab, audit_tab = st.tabs(["Premier tour corrigé", "Second tour corrigé", "Audit 2022"])
    context = None
    selected_period = None
    with first_tab:
        _, context, selected_period = _render_corrected_first_round_section(frame)
    with second_tab:
        _render_corrected_second_round_section(frame)
    with audit_tab:
        if context is None:
            st.info("L’audit 2022 s’affiche après calcul de la correction du premier tour.")
        else:
            _render_2022_ui(context, selected_period=selected_period if isinstance(selected_period, tuple) and len(selected_period) == 2 else None)
