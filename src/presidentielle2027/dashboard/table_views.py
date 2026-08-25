from __future__ import annotations

import re
from functools import wraps

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
    "centre_gauche": "Centre-gauche",
    "central_gauche": "Centre-gauche",
    "central-gauche": "Centre-gauche",
    "centre-gauche": "Centre-gauche",
    "gauche_radicale": "Gauche radicale",
    "green": "Écologistes",
    "greens": "Écologistes",
    "écologistes": "Écologistes",
    "centre": "Centre",
    "center": "Centre",
    "centre_droit": "Centre-droit",
    "central_droit": "Centre-droit",
    "central-droit": "Centre-droit",
    "centre-droit": "Centre-droit",
    "right": "Droite",
    "gaullist_right": "Droite gaulliste",
    "droite_gaulliste": "Droite gaulliste",
    "droite_nationale": "Droite nationale",
    "droite_souverainiste": "Droite souverainiste",
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
    "historical_2022": "Calcul automatique 2022",
    "manual_override": "Surcharge manuelle",
    "generic_bloc": "Bloc politique commun",
    "online": "En ligne",
    "telephone": "Téléphone",
    "phone": "Téléphone",
    "mixed": "Méthode mixte",
    "registered_voters": "Personnes inscrites sur les listes électorales",
    "general_population": "Population générale",
    "true": "Oui",
    "false": "Non",
    "ready": "Prêt",
    "partial": "Partiel",
    "complete": "Complet",
    "wikipedia_fr_raw_tables": "Wikipédia France — tableaux bruts corrigés",
    "wikipedia_excel_v2": "Wikipédia — extraction structurée",
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
    "bias_source": "Source du biais",
    "poll_id": "Identifiant du sondage",
    "quota_method": "Méthode des quotas",
    "margin_of_error": "Marge d’erreur",
    "extraction_confidence": "Confiance de l’extraction",
    "lower_bound_percent": "Borne basse",
    "upper_bound_percent": "Borne haute",
    "undecided_percent": "Indécis",
    "abstention_estimate": "Abstention estimée",
    "registered_voters_basis": "Base des personnes inscrites",
    "raw_text_context": "Texte source",
    "rows": "Lignes",
    "rounds": "Tours",
    "scenarios": "Scénarios",
    "pollsters": "Instituts",
    "average_sample_size": "Échantillon moyen",
    "first_publication": "Première publication",
    "last_publication": "Dernière publication",
    "missing_sample_size": "Échantillons manquants",
    "missing_collection_method": "Modes de collecte manquants",
    "field": "Champ",
    "label": "Libellé",
    "filled_count": "Présents",
    "missing_count": "Manquants",
    "coverage_percent": "Couverture",
    "page": "Page",
    "visual_row": "Ligne visuelle",
    "row_text": "Texte de la ligne",
    "layout_line": "Ligne de mise en page",
    "raw_line": "Texte brut",
    "line_number": "Numéro de ligne",
    "text": "Texte",
}


def rename_user_facing_columns(
    frame: pd.DataFrame,
    extra_labels: dict[str, str] | None = None,
) -> pd.DataFrame:
    rename_map = USER_COLUMN_LABELS.copy()
    if extra_labels:
        rename_map.update(extra_labels)
    for column in frame.columns:
        is_internal_name = isinstance(column, str) and re.fullmatch(r"[a-z][a-z0-9_]*", column)
        if column not in rename_map and is_internal_name:
            rename_map[column] = column.replace("_", " ").capitalize()
    return frame.rename(columns=rename_map)


def user_facing_value(value: object) -> object:
    if not isinstance(value, str):
        return value
    stripped = value.strip()
    translated = USER_VALUE_REPLACEMENTS.get(
        stripped,
        USER_VALUE_REPLACEMENTS.get(stripped.lower()),
    )
    if translated is not None:
        return translated
    if re.fullmatch(r"[a-z][a-z0-9_]*", stripped) and "_" in stripped:
        return stripped.replace("_", " ").capitalize()
    return stripped


def clean_user_facing_frame(frame: pd.DataFrame) -> pd.DataFrame:
    working = frame.copy()
    object_columns = working.select_dtypes(include=["object"]).columns.tolist()
    for column in object_columns:
        working[column] = (
            working[column]
            .fillna("Non renseigné")
            .astype(str)
            .map(user_facing_value)
        )
    datetime_columns = working.select_dtypes(include=["datetime64[ns]", "datetimetz"]).columns.tolist()
    for column in datetime_columns:
        working[column] = working[column].dt.strftime("%d/%m/%Y").fillna("Date non disponible")
    return working


def _sanitize_display_frame(data: object) -> object:
    if not isinstance(data, pd.DataFrame):
        return data
    return clean_user_facing_frame(rename_user_facing_columns(data))


def install_user_facing_text_guard() -> None:
    """Prevent internal identifiers from leaking through Streamlit widgets."""
    if getattr(st, "_presidentielle_text_guard_installed", False):
        return

    original_dataframe = st.dataframe
    original_table = st.table
    original_selectbox = st.selectbox
    original_multiselect = st.multiselect
    original_radio = st.radio

    @wraps(original_dataframe)
    def guarded_dataframe(data: object = None, *args: object, **kwargs: object) -> object:
        sanitized = _sanitize_display_frame(data)
        column_config = kwargs.get("column_config")
        if isinstance(data, pd.DataFrame) and isinstance(column_config, dict):
            rename_lookup = dict(zip(data.columns, sanitized.columns))
            kwargs["column_config"] = {
                rename_lookup.get(column, column): config
                for column, config in column_config.items()
            }
        return original_dataframe(sanitized, *args, **kwargs)

    @wraps(original_table)
    def guarded_table(data: object = None, *args: object, **kwargs: object) -> object:
        return original_table(_sanitize_display_frame(data), *args, **kwargs)

    def _guard_format_func(kwargs: dict[str, object]) -> dict[str, object]:
        if kwargs.get("format_func") is None:
            kwargs["format_func"] = user_facing_value
        return kwargs

    @wraps(original_selectbox)
    def guarded_selectbox(*args: object, **kwargs: object) -> object:
        return original_selectbox(*args, **_guard_format_func(kwargs))

    @wraps(original_multiselect)
    def guarded_multiselect(*args: object, **kwargs: object) -> object:
        return original_multiselect(*args, **_guard_format_func(kwargs))

    @wraps(original_radio)
    def guarded_radio(*args: object, **kwargs: object) -> object:
        return original_radio(*args, **_guard_format_func(kwargs))

    st.dataframe = guarded_dataframe
    st.table = guarded_table
    st.selectbox = guarded_selectbox
    st.multiselect = guarded_multiselect
    st.radio = guarded_radio
    st._presidentielle_text_guard_installed = True


def render_poll_results_table(frame: pd.DataFrame) -> None:
    if frame.empty:
        st.info("Aucune ligne à afficher.")
        return

    working = clean_user_facing_frame(rename_user_facing_columns(frame))
    if "Parti" in working.columns:
        working["Logo"] = working.apply(
            lambda row: get_party_logo_url(row.get("Parti"), row.get("Candidat")),
            axis=1,
        )
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
