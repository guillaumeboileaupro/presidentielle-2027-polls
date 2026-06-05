from __future__ import annotations

from pathlib import Path

import pandas as pd


def load_csv_if_exists(path: Path) -> pd.DataFrame:
    if path.exists():
        return pd.read_csv(path, engine="python", on_bad_lines="skip")
    return pd.DataFrame()


def build_frame_completeness_summary(frame: pd.DataFrame) -> pd.DataFrame:
    checks = {
        "sample_size": "Taille d'échantillon",
        "fieldwork_start_date": "Date de terrain début",
        "fieldwork_end_date": "Date de terrain fin",
        "publication_date": "Date de publication",
        "collection_method": "Mode de collecte",
        "quota_method": "Méthode des quotas",
        "commissioner": "Commanditaire",
        "media_partner": "Partenaire média",
        "population": "Population interrogée",
        "margin_of_error": "Marge d'erreur",
        "extraction_confidence": "Confiance d'extraction",
    }
    rows: list[dict[str, object]] = []
    total = len(frame.index)
    if total == 0:
        return pd.DataFrame(columns=["field", "label", "filled_count", "missing_count", "coverage_percent"])

    for column, label in checks.items():
        if column not in frame.columns:
            filled_count = 0
        else:
            series = frame[column]
            filled_count = int(series.notna().sum()) if str(series.dtype) != "object" else int(series.fillna("").astype(str).str.strip().ne("").sum())
        rows.append(
            {
                "field": column,
                "label": label,
                "filled_count": filled_count,
                "missing_count": total - filled_count,
                "coverage_percent": round(100 * filled_count / total, 1),
            }
        )
    return pd.DataFrame(rows).sort_values(["coverage_percent", "label"], ascending=[False, True])


def yes_no_icon(value: object) -> str:
    normalized = str(value).strip().lower()
    if normalized in {"true", "yes", "oui", "1"}:
        return "Oui"
    if normalized in {"false", "no", "non", "0"}:
        return "Non"
    return "Inconnu"


def status_label(value: object) -> str:
    normalized = str(value).strip().lower()
    if normalized in {"ready", "complete", "completed"}:
        return "Complet"
    if normalized in {"partial", "partiel"}:
        return "Partiel"
    if normalized in {"demo", "sample"}:
        return "Démo"
    if normalized in {"missing", "none", ""}:
        return "Manquant"
    return str(value)


def build_dataset_registry_view(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return frame
    working = frame.copy()
    boolean_columns = [
        "sample_size_available",
        "fieldwork_dates_available",
        "publication_date_available",
        "collection_method_available",
        "quota_method_available",
        "margin_of_error_available",
        "commissioner_available",
        "media_partner_available",
        "population_available",
        "error_bars_ready",
        "corrected_plot_ready",
    ]
    for column in boolean_columns:
        if column in working.columns:
            working[column] = working[column].map(yes_no_icon)
    if "status" in working.columns:
        working["status"] = working["status"].map(status_label)
    rename_map = {
        "dataset_name": "Dataset",
        "source_name": "Source",
        "round_scope": "Tours",
        "extraction_method": "Extraction",
        "sample_size_available": "Échantillon",
        "fieldwork_dates_available": "Dates terrain",
        "publication_date_available": "Date publication",
        "collection_method_available": "Collecte",
        "quota_method_available": "Quotas",
        "margin_of_error_available": "Marge erreur",
        "commissioner_available": "Commanditaire",
        "media_partner_available": "Média",
        "population_available": "Population",
        "error_bars_ready": "Barres erreur",
        "corrected_plot_ready": "Plot corrigé",
        "status": "Statut",
    }
    return working.rename(columns=rename_map)


def build_pollster_registry_view(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return frame
    working = frame.copy()
    if "metadata_status" in working.columns:
        working["metadata_status"] = working["metadata_status"].map(status_label)
    if "commission_des_sondages_reference" in working.columns:
        working["commission_des_sondages_reference"] = working["commission_des_sondages_reference"].map(yes_no_icon)
    if "quota_method_expected" in working.columns:
        working["quota_method_expected"] = working["quota_method_expected"].map(yes_no_icon)
    return working.rename(
        columns={
            "polling_company": "Institut",
            "website_url": "Site web",
            "commission_des_sondages_reference": "Commission",
            "default_collection_method": "Collecte par défaut",
            "default_population": "Population par défaut",
            "quota_method_expected": "Quotas attendus",
            "methodology_notes": "Notes",
            "metadata_status": "Statut",
        }
    )
