from __future__ import annotations

import pandas as pd
import streamlit as st

from presidentielle2027.dashboard.party_assets import get_party_logo_url


USER_VALUE_REPLACEMENTS = {
    "unknown": "Non renseigné",
    "unknown_source": "Source à vérifier",
    "unknown_pollster": "Institut à vérifier",
    "unknown_scenario": "Scénario à vérifier",
    "unknown_round": "Tour à vérifier",
    "nan": "Non renseigné",
    "None": "Non renseigné",
    "NaT": "Date non disponible",
    "": "Non renseigné",
    "first_round": "Premier tour",
    "second_round": "Second tour",
    "left": "Gauche",
    "centre_left": "Centre-gauche",
    "center_left": "Centre-gauche",
    "green": "Écologistes",
    "greens": "Écologistes",
    "centre": "Centre",
    "center": "Centre",
    "right": "Droite",
    "far_right": "Extrême droite",
    "far_left": "Extrême gauche",
    "sovereigntist_right": "Droite souverainiste",
    "extrême_droite": "Extrême droite",
    "extrême_gauche": "Extrême gauche",
    "autres": "Autres",
    "gauche": "Gauche",
    "droite": "Droite",
    "0_30": "0 à 30 jours",
    "31_90": "31 à 90 jours",
    "91_180": "91 à 180 jours",
    "181_plus": "181 jours et plus",
}

USER_COLUMN_LABELS = {
    "source_name": "Source",
    "polling_company": "Institut",
    "pollster": "Institut",
    "round": "Tour",
    "scenario_name": "Scénario",
    "candidate_name": "Candidat",
    "candidate_party": "Parti",
    "political_family": "Famille politique",
    "sample_size": "Échantillon",
    "fieldwork_start_date": "Début terrain",
    "fieldwork_end_date": "Fin terrain",
    "publication_date": "Publication",
    "estimate_percent": "Score",
    "source_url": "Lien source",
    "collection_method": "Collecte",
    "commissioner": "Commanditaire",
    "media_partner": "Média",
    "population": "Population",
    "force_label": "Force",
    "broad_bloc": "Bloc",
    "avg_poll_minus_result": "Erreur moyenne",
    "median_poll_minus_result": "Erreur médiane",
    "mean_abs_error": "Erreur absolue moyenne",
    "polls": "Lignes",
    "official_result": "Résultat officiel",
    "mean_error": "Erreur moyenne",
    "median_error": "Erreur médiane",
    "uncertainty": "Incertitude",
    "result_percent": "Résultat réel 2022",
    "current_days_bucket": "Fenêtre 2027",
    "n_polls_used": "Sondages historiques",
    "current_poll_count": "Sondages 2027",
    "polls_in_matching_bucket": "Sondages fenêtre",
    "structural_bias": "Biais structurel",
    "temporal_bias": "Biais temps long",
    "trajectory_bias": "Biais trajectoire",
    "total_bias": "Correction totale",
    "status": "Statut",
    "years_used": "Années",
}


def rename_user_facing_columns(frame: pd.DataFrame, extra_labels: dict[str, str] | None = None) -> pd.DataFrame:
    rename_map = USER_COLUMN_LABELS.copy()
    if extra_labels:
        rename_map.update(extra_labels)
    return frame.rename(columns=rename_map)


def clean_user_facing_frame(frame: pd.DataFrame) -> pd.DataFrame:
    working = frame.copy()
    object_columns = working.select_dtypes(include=["object"]).columns.tolist()
    for column in object_columns:
        working[column] = (
            working[column]
            .fillna("Non renseigné")
            .astype(str)
            .map(lambda value: USER_VALUE_REPLACEMENTS.get(value.strip(), value.strip()))
        )
    datetime_columns = working.select_dtypes(include=["datetime64[ns]", "datetimetz"]).columns.tolist()
    for column in datetime_columns:
        working[column] = working[column].dt.strftime("%Y-%m-%d").fillna("Date non disponible")
    return working


def render_poll_results_table(frame: pd.DataFrame) -> None:
    if frame.empty:
        st.info("Aucune ligne à afficher.")
        return

    working = clean_user_facing_frame(rename_user_facing_columns(frame))
    if "Parti" in working.columns:
        working["Logo"] = working["Parti"].map(get_party_logo_url)
    ordered_columns = [
        "Logo",
        "Source",
        "Institut",
        "Tour",
        "Scénario",
        "Publication",
        "Début terrain",
        "Fin terrain",
        "Force",
        "Candidat",
        "Parti",
        "Famille politique",
        "Score",
        "Échantillon",
        "Commanditaire",
        "Média",
        "Collecte",
        "Population",
        "Lien source",
    ]
    available = [column for column in ordered_columns if column in working.columns]
    st.dataframe(
        working[available],
        width="stretch",
        hide_index=True,
        column_config={
            "Logo": st.column_config.ImageColumn("Logo"),
            "Score": st.column_config.NumberColumn("Score", format="%.1f %%"),
            "Échantillon": st.column_config.NumberColumn("Échantillon", format="%d"),
            "Lien source": st.column_config.LinkColumn("Lien source"),
        },
    )


def render_adjustments_table(frame: pd.DataFrame) -> None:
    if frame.empty:
        st.info("Aucune ligne à afficher.")
        return
    working = frame.copy()
    if "house_effect_adjusted_mean" not in working.columns and "corrected_2027_mean" in working.columns:
        working["house_effect_adjusted_mean"] = working["corrected_2027_mean"]
    working = clean_user_facing_frame(
        working.rename(
            columns={
                "candidate_name": "Candidat",
                "candidate_party": "Parti",
                "raw_mean": "Brut",
                "recency_weighted_mean": "Récence",
                "sample_weighted_mean": "Échantillon pondéré",
                "house_effect_adjusted_mean": "Correction institut",
                "polls": "Sondages",
            }
        )
    )
    st.dataframe(
        working,
        width="stretch",
        hide_index=True,
        column_config={
            "Brut": st.column_config.NumberColumn("Brut", format="%.1f %%"),
            "Récence": st.column_config.NumberColumn("Récence", format="%.1f %%"),
            "Échantillon pondéré": st.column_config.NumberColumn("Échantillon pondéré", format="%.1f %%"),
            "Correction institut": st.column_config.NumberColumn("Correction institut", format="%.1f %%"),
            "Sondages": st.column_config.NumberColumn("Sondages", format="%d"),
        },
    )
