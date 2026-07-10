from __future__ import annotations

from itertools import combinations
from io import StringIO
from pathlib import Path
import re
from urllib.parse import unquote
from zipfile import ZipFile

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import requests
import streamlit as st
from bs4 import BeautifulSoup

from presidentielle2027.analytics.dynamic_poll_bias import apply_dynamic_poll_bias_correction
from presidentielle2027.analytics.historical_corrections import (
    get_reference_dir,
    get_second_round_coalition_2024_transfer_map,
    load_legislative_2024_results,
    load_legislative_2024_seats,
    normalize_broad_bloc,
)
from presidentielle2027.dashboard.colors import get_political_color
from presidentielle2027.dashboard.plot_theme import PLOT_LAYOUT_THEME


LOCAL_2024_VISUAL_ROWS = (
    "data/imported_wiki_zip_complete/"
    "csv_from_pdf_Liste_de_sondages_sur_les_élections_législatives_françaises_de_2024/"
    "Liste_de_sondages_sur_les_élections_législatives_françaises_de_2024_visual_rows.csv"
)
OFFICIAL_GENERAL_RESULT_PATHS = [
    Path("/home/gboileau/Téléchargements/general_results.csv"),
    Path("/home/gboileau/Téléchargements/general_results(1).csv"),
    Path("/home/gboileau/Téléchargements/2024_legislative/general_results.csv"),
    Path("/home/gboileau/Téléchargements/2024_legislative/general_results(1).csv"),
    Path("/home/gboileau/Téléchargements/2024_legislative/general_results(2).csv"),
    Path.cwd() / "data" / "reference" / "official_2024_legislatives_general_results.csv",
]
OFFICIAL_2024_LEGISLATIVE_ZIP_PATHS = [
    Path("/home/gboileau/Téléchargements/2024_legislative.zip"),
    Path.cwd() / "data" / "reference" / "2024_legislative.zip",
]
OFFICIAL_2024_CIRCO_RESULTS_LOCAL_PATHS = [
    Path("/home/gboileau/Téléchargements/2024_legislative/resultats-definitifs-par-circonscriptions-legislatives.csv"),
    Path.cwd() / "data" / "reference" / "resultats-definitifs-par-circonscriptions-legislatives.csv",
]
WIKIPEDIA_2024_RESULTS_PAGE_URL = "https://fr.wikipedia.org/wiki/R%C3%A9sultats_par_d%C3%A9partement_des_%C3%A9lections_l%C3%A9gislatives_fran%C3%A7aises_de_2024"
WIKIPEDIA_2024_T2_RESULTS_LOCAL_PATHS = [
    Path.cwd() / "data" / "reference" / "wikipedia_legislatives_2024_second_tour_circonscriptions.csv",
]
OFFICIAL_2024_CANDIDATE_RESULTS_LOCAL_PATHS = [
    Path.cwd() / "data" / "reference" / "official_2024_legislatives_candidate_results.csv",
]
NFP_INTERNAL_PARTY_MAPPING_PATHS = [
    Path("/home/gboileau/NFP_circo.csv"),
    Path.cwd() / "data" / "reference" / "nfp_internal_party_mapping_2024.csv",
]
OFFICIAL_2024_CIRCO_RESULTS_INNER_PATH = "2024_legislative/resultats-definitifs-par-circonscriptions-legislatives.csv"
OFFICIAL_2024_T2_CANDIDATURES_INNER_PATH = "2024_legislative/legislatives-2024-candidatures-france-entiere-tour-2-2024-07-05.csv"
OFFICIAL_CANDIDATE_RESULTS_REMOTE_URL = "https://object.files.data.gouv.fr/data-pipeline-open/elections/candidats_results.csv"

FIVE_BLOC_ORDER = ["gauche", "centre", "droite", "extrême_droite", "autres"]
FIVE_BLOC_LABELS = {
    "gauche": "Gauche / NFP",
    "centre": "Centre / Ensemble",
    "droite": "Droite / LR",
    "extrême_droite": "RN et alliés",
    "autres": "Divers / autres",
}
LOCAL_SEARCH_ALIASES = {
    "10e circonscription du Nord": ["59", "hauts-de-france", "hauts de france", "nord", "tourcoing", "lille", "10"],
    "3e circonscription du Lot-et-Garonne": ["47", "nouvelle-aquitaine", "nouvelle aquitaine", "lot-et-garonne", "lot et garonne", "agen", "villeneuve-sur-lot", "3"],
    "1re circonscription des Alpes Maritimes": ["06", "provence-alpes-cote-d-azur", "provence alpes cote d azur", "paca", "alpes-maritimes", "alpes maritimes", "nice", "1"],
    "7e circonscription de la Seine-Saint-Denis": ["93", "ile-de-france", "ile de france", "seine-saint-denis", "seine saint denis", "montreuil", "saint-denis", "aubervilliers", "7"],
    "6e circonscription du Calvados": ["14", "normandie", "calvados", "caen", "6"],
}
DEPARTMENT_CENTROIDS = {
    "Nord": (50.514, 3.065),
    "Lot-et-Garonne": (44.369, 0.432),
    "Alpes Maritimes": (43.936, 7.179),
    "Seine-Saint-Denis": (48.914, 2.452),
    "Calvados": (49.184, -0.370),
}
SECOND_ROUND_LOCAL_NOTES = {
    "10e circonscription du Nord": "Triangulaire testée, puis duel après désistement.",
    "3e circonscription du Lot-et-Garonne": "Triangulaire testée, puis duel après désistement.",
    "1re circonscription des Alpes Maritimes": "Triangulaire testée, puis duel après désistement.",
    "7e circonscription de la Seine-Saint-Denis": "Duel local documenté dans les sources du repo.",
    "6e circonscription du Calvados": "Duel local documenté dans les sources du repo.",
}
TOKEN_BLOC_MAP = {
    "NFP": "gauche",
    "LFI": "gauche",
    "LO": "gauche",
    "PCF": "gauche",
    "PS": "gauche",
    "DVG": "gauche",
    "ECO": "gauche",
    "EAC": "gauche",
    "REV": "gauche",
    "NPA-R": "gauche",
    "PRCF": "gauche",
    "REN": "centre",
    "ENS": "centre",
    "HOR": "centre",
    "RE": "centre",
    "DVC": "centre",
    "RAD": "centre",
    "MODEM": "centre",
    "LR": "droite",
    "DVD": "droite",
    "RES": "droite",
    "DLF": "droite",
    "RN": "extrême_droite",
    "REC": "extrême_droite",
    "UDR": "extrême_droite",
}
DUEL_OPTION_TO_BLOCS = {
    "Gauche / NFP vs RN": ("gauche", "extrême_droite"),
    "Centre / Ensemble vs RN": ("centre", "extrême_droite"),
    "Droite / LR vs RN": ("droite", "extrême_droite"),
    "Gauche / NFP vs Centre / Ensemble": ("gauche", "centre"),
}
NATIONAL_DUEL_SURVEYS = pd.DataFrame(
    [
        {
            "duel_label": "Gauche / NFP vs RN",
            "source_a": "gauche",
            "source_b": "extrême_droite",
            "score_a": 33.0,
            "score_b": 41.0,
            "undecided": 26.0,
            "source_note": "OpinionWay 17-18 juin 2024 · duel local type NFP vs RN",
        },
        {
            "duel_label": "Centre / Ensemble vs RN",
            "source_a": "centre",
            "source_b": "extrême_droite",
            "score_a": 40.0,
            "score_b": 37.0,
            "undecided": 22.0,
            "source_note": "OpinionWay 17-18 juin 2024 · duel local type Ensemble vs RN",
        },
    ]
)

ELECTION_LABELS = {
    "2024_legi_t1": "Législatives 2024 · 1er tour",
    "2024_legi_t2": "Législatives 2024 · 2d tour",
}
NUANCE_LABELS = {
    "COM": "Parti communiste",
    "DVC": "Divers centre",
    "DIV": "Divers",
    "DVD": "Divers droite",
    "DVG": "Divers gauche",
    "DSV": "Divers souverainistes",
    "ECO": "Écologistes",
    "ENS": "Ensemble",
    "EXD": "Extrême droite",
    "EXG": "Extrême gauche",
    "FI": "LFI dissidents / hors NFP",
    "HOR": "Horizons",
    "LR": "Les Républicains",
    "PS": "Parti socialiste",
    "RDG": "Parti radical de gauche",
    "REC": "Reconquête",
    "REG": "Régionalistes",
    "RN": "Rassemblement national",
    "SOC": "Parti socialiste",
    "UDI": "UDI",
    "UG": "Union de la gauche / NFP",
    "UXD": "Union de l'extrême droite",
    "VEC": "Écologistes",
}
FORCE_COLORS = {
    "LFI / NFP": "#C62828",
    "PS / NFP": "#E91E63",
    "PP / NFP": "#FF5C8A",
    "EELV / NFP": "#2E7D32",
    "PCF / NFP": "#B71C1C",
    "Autre NFP": "#D32F2F",
    "LFI dissidents / hors NFP": "#8E244D",
    "Parti communiste": "#B71C1C",
    "Parti socialiste": "#E91E63",
    "Écologistes": "#2E7D32",
    "Union de la gauche / NFP": "#D32F2F",
    "Ensemble": "#F4A300",
    "Renaissance / Ensemble": "#F4A300",
    "MoDem / Ensemble": "#FFB74D",
    "Horizons / Ensemble": "#C88B00",
    "UDI / Ensemble": "#64B5F6",
    "PRV / Ensemble": "#FFCC80",
    "Agir / Ensemble": "#FFCA28",
    "TdP / Ensemble": "#FFD54F",
    "En commun / Ensemble": "#FFE082",
    "SE / Ensemble": "#F6D8A8",
    "Horizons": "#C88B00",
    "Les Républicains": "#1565C0",
    "Divers droite": "#AFC6FF",
    "Divers centre": "#F6D8A8",
    "Divers gauche": "#F8A5B6",
    "Divers souverainistes": "#7E57C2",
    "Divers": "#757575",
    "Rassemblement national": "#0D47A1",
    "Alliés RN": "#1565C0",
    "Reconquête": "#00ACC1",
    "Union de l'extrême droite": "#1565C0",
    "Extrême droite": "#00838F",
    "Extrême gauche": "#AD1457",
    "Régionalistes": "#00897B",
    "UDI": "#64B5F6",
    "Parti radical de gauche": "#EC407A",
}


def _bloc_label(bloc_label: str) -> str:
    return FIVE_BLOC_LABELS.get(bloc_label, bloc_label)


def _bloc_color(bloc_label: str) -> str:
    return get_political_color(None, bloc_label)


def _safe_percent(numerator: pd.Series, denominator: pd.Series) -> pd.Series:
    numerator = pd.to_numeric(numerator, errors="coerce").fillna(0.0)
    denominator = pd.to_numeric(denominator, errors="coerce").fillna(0.0)
    return (numerator / denominator.where(denominator > 0.0, pd.NA) * 100.0).fillna(0.0)


def _election_label(value: object) -> str:
    key = str(value)
    return ELECTION_LABELS.get(key, key)


def _force_label_from_nuance(nuance: object) -> str:
    key = str(nuance or "").strip().upper()
    return NUANCE_LABELS.get(key, key or "Non renseigné")


def _force_color(force_label: object, nuance: object | None = None) -> str:
    nuance_key = str(nuance or "").strip().upper()
    force_key = str(force_label or "").strip()
    if force_key in FORCE_COLORS:
        return FORCE_COLORS[force_key]
    return get_political_color(nuance_key, force_key)


def _force_to_bloc_key(force_label: object) -> str:
    force = str(force_label or "").strip()
    if force.endswith("/ NFP"):
        return "gauche"
    mapping = {
        "LFI": "gauche",
        "LFI / NFP": "gauche",
        "PS": "gauche",
        "PS / NFP": "gauche",
        "PP": "gauche",
        "PP / NFP": "gauche",
        "EELV": "gauche",
        "EELV / NFP": "gauche",
        "PCF": "gauche",
        "PCF / NFP": "gauche",
        "NPA": "gauche",
        "NPA-A": "gauche",
        "NPA / NFP": "gauche",
        "Autre NFP": "gauche",
        "Union de la gauche / NFP": "gauche",
        "Parti socialiste": "gauche",
        "Parti communiste": "gauche",
        "Écologistes": "gauche",
        "Divers gauche": "gauche",
        "Parti radical de gauche": "gauche",
        "Extrême gauche": "gauche",
        "RE": "centre",
        "Ensemble": "centre",
        "Renaissance": "centre",
        "Renaissance / Ensemble": "centre",
        "MoDem": "centre",
        "MoDem / Ensemble": "centre",
        "MODEM": "centre",
        "HOR": "centre",
        "Horizons / Ensemble": "centre",
        "UDI / Ensemble": "centre",
        "PRV / Ensemble": "centre",
        "Agir / Ensemble": "centre",
        "TdP / Ensemble": "centre",
        "En commun / Ensemble": "centre",
        "SE / Ensemble": "centre",
        "Horizons": "centre",
        "UDI": "centre",
        "Divers centre": "centre",
        "LR": "droite",
        "Les Républicains": "droite",
        "RES": "droite",
        "LFH": "droite",
        "DLF": "droite",
        "Divers droite": "droite",
        "RN": "extrême_droite",
        "Rassemblement national": "extrême_droite",
        "Alliés RN": "extrême_droite",
        "REC": "extrême_droite",
        "Reconquête": "extrême_droite",
        "Union de l'extrême droite": "extrême_droite",
        "Divers souverainistes": "extrême_droite",
        "LFI dissidents / hors NFP": "gauche",
    }
    return mapping.get(force, "autres")


def _force_to_bloc_label(force_label: object) -> str:
    return _bloc_label(_force_to_bloc_key(force_label))


def _force_to_coalition_label(force_label: object) -> str:
    force = str(force_label or "").strip()
    if force.endswith("/ NFP"):
        return "NFP"
    if force in {
        "LFI",
        "PS",
        "PP",
        "EELV",
        "PCF",
        "NPA",
        "NPA-A",
        "LFI / NFP",
        "PS / NFP",
        "PP / NFP",
        "EELV / NFP",
        "PCF / NFP",
        "NPA / NFP",
        "Autre NFP",
        "Union de la gauche / NFP",
    }:
        return "NFP"
    if force in {
        "RE",
        "Renaissance",
        "MoDem",
        "MODEM",
        "HOR",
        "Ensemble",
        "Renaissance / Ensemble",
        "MoDem / Ensemble",
        "Horizons / Ensemble",
        "UDI / Ensemble",
        "PRV / Ensemble",
        "Agir / Ensemble",
        "TdP / Ensemble",
        "En commun / Ensemble",
        "SE / Ensemble",
        "Horizons",
    }:
        return "Ensemble"
    if force in {"UDI", "Divers centre"}:
        return "Centre hors Ensemble"
    if force in {"RN", "Rassemblement national", "Alliés RN", "Union de l'extrême droite", "REC", "Reconquête", "Divers souverainistes"}:
        return "Extrême droite"
    return force


def _projection_level_label(force_label: object) -> str:
    force = str(force_label or "").strip()
    if force in {"NFP", "Ensemble"}:
        return "Coalition"
    if force in {"Gauche / NFP", "Centre / Ensemble", "Droite / LR", "RN et alliés", "Divers / autres", "Extrême droite"}:
        return "Bloc"
    return "Force"


def _projection_force_display_label(force_label: object) -> str:
    force = str(force_label or "").strip()
    if force.endswith("/ NFP") and force not in {
        "LFI / NFP",
        "PS / NFP",
        "PP / NFP",
        "EELV / NFP",
        "PCF / NFP",
        "NPA / NFP",
    }:
        return force.replace(" / NFP", "")
    display_map = {
        "LFI / NFP": "LFI",
        "PS / NFP": "PS",
        "PP / NFP": "Place publique",
        "EELV / NFP": "EELV",
        "PCF / NFP": "PCF",
        "NPA / NFP": "NPA",
        "Autre NFP": "Autre composante NFP",
        "Union de la gauche / NFP": "NFP",
        "Renaissance / Ensemble": "Renaissance",
        "MoDem / Ensemble": "MoDem",
        "Horizons / Ensemble": "Horizons",
        "UDI / Ensemble": "UDI",
        "PRV / Ensemble": "PRV",
        "Agir / Ensemble": "Agir",
        "TdP / Ensemble": "TdP",
        "En commun / Ensemble": "En commun",
        "SE / Ensemble": "SE allié ENS",
        "Rassemblement national": "RN",
        "Alliés RN": "Alliés RN",
        "Union de l'extrême droite": "Alliés RN",
        "Reconquête": "Reconquête",
    }
    return display_map.get(force, force)


def _duel_display_label(force_a: object, force_b: object) -> str:
    left = _projection_force_display_label(force_a)
    right = _projection_force_display_label(force_b)
    return f"{left} contre {right}"


def _is_runoff_projectable_force(force_label: object) -> bool:
    force = str(force_label or "").strip()
    if not force:
        return False
    if force in {
        "Divers",
        "Divers centre",
        "Divers droite",
        "Divers gauche",
        "Divers souverainistes",
        "Extrême gauche",
        "Extrême droite",
        "Union de la gauche / NFP",
        "Union de l'extrême droite",
        "Autre NFP",
        "Parti socialiste",
        "Parti communiste",
        "Parti radical de gauche",
        "Écologistes",
        "Régionalistes",
        "Centre hors Ensemble",
    }:
        return False
    if force.startswith("Divers"):
        return False
    return True


def _is_presidential_first_round_force(force_label: object) -> bool:
    force = str(force_label or "").strip()
    if not force:
        return False
    if force in {
        "Alliés RN",
        "Union de l'extrême droite",
        "UDI",
        "UDI / Ensemble",
        "Divers",
        "Divers centre",
        "Divers droite",
        "Divers gauche",
        "Divers souverainistes",
        "Extrême gauche",
        "Extrême droite",
        "Centre hors Ensemble",
        "Autre NFP",
        "Union de la gauche / NFP",
        "Régionalistes",
        "Parti radical de gauche",
        "Parti socialiste",
        "Parti communiste",
        "Écologistes",
    }:
        return False
    if force.startswith("Divers"):
        return False
    if force.endswith("/ NFP"):
        return True
    return force in {
        "Rassemblement national",
        "RN",
        "Reconquête",
        "REC",
        "Renaissance / Ensemble",
        "Renaissance",
        "RE",
        "MoDem / Ensemble",
        "MoDem",
        "MODEM",
        "Horizons / Ensemble",
        "Horizons",
        "Les Républicains",
        "LR",
        "LFH",
        "La France humaniste",
        "DLF",
        "LO",
        "NPA-A",
    }


def _are_runoff_finalists_compatible(force_a: object, force_b: object) -> bool:
    left = str(force_a or "").strip()
    right = str(force_b or "").strip()
    if not left or not right or left == right:
        return False
    if _projection_force_display_label(left) == _projection_force_display_label(right):
        return False
    coalition_a = _force_to_coalition_label(left)
    coalition_b = _force_to_coalition_label(right)
    if coalition_a and coalition_b and coalition_a == coalition_b:
        return False
    return True


def _analysis_force_label(force_label: object, nuance: object | None = None) -> str:
    nuance_key = str(nuance or "").strip().upper()
    force_key = str(force_label or "").strip()
    if force_key in {"LFI / NFP", "PS / NFP", "PP / NFP", "EELV / NFP", "PCF / NFP", "NPA / NFP", "Autre NFP"}:
        return force_key
    if nuance_key in {"UG", "SOC", "PS", "COM", "ECO", "VEC"}:
        return "Union de la gauche / NFP"
    return force_key or _force_label_from_nuance(nuance_key)


def _is_generic_official_family_label(force_label: object) -> bool:
    return str(force_label or "").strip() in {
        "Extrême gauche",
        "Extrême droite",
        "Divers",
        "Divers centre",
        "Divers droite",
        "Divers gauche",
        "Divers souverainistes",
        "Union de l'extrême droite",
        "Régionalistes",
    }


def _normalize_nfp_force_label(force_label: object, nuance: object | None = None) -> str:
    nuance_key = str(nuance or "").strip().upper()
    force_key = str(force_label or "").strip()
    if force_key in {"LFI / NFP", "PS / NFP", "PP / NFP", "EELV / NFP", "PCF / NFP", "NPA / NFP", "Autre NFP"}:
        return force_key
    if nuance_key in {"SOC", "PS"}:
        return "PS / NFP"
    if nuance_key in {"ECO", "VEC"}:
        return "EELV / NFP"
    if nuance_key == "COM":
        return "PCF / NFP"
    if nuance_key == "UG":
        return "Autre NFP" if force_key == "Union de la gauche / NFP" else force_key
    return force_key


def _format_circo_code(value: object) -> str:
    text = str(value or "").strip()
    if text.endswith(".0"):
        text = text[:-2]
    return text


def _detailed_force_label(
    nuance: object,
    party_label: object | None = None,
    liste: object | None = None,
    libelle_abrege_liste: object | None = None,
    libelle_etendu_liste: object | None = None,
) -> str:
    nuance_key = str(nuance or "").strip().upper()
    base_label = _force_label_from_nuance(nuance_key)
    search_text = _normalize_search_text(
        " ".join(
            [
                _safe_text(party_label),
                _safe_text(liste),
                _safe_text(libelle_abrege_liste),
                _safe_text(libelle_etendu_liste),
            ]
        )
    )
    if any(token in search_text for token in ["modem", "mouvement democrate"]):
        return "MoDem / Ensemble"
    if "horizons" in search_text or " hor " in f" {search_text} ":
        return "Horizons / Ensemble"
    if "udi" in search_text and "ens" in search_text:
        return "UDI / Ensemble"
    if "parti radical" in search_text or "prv" in search_text:
        if "ens" in search_text:
            return "PRV / Ensemble"
    if "agir" in search_text and "ens" in search_text:
        return "Agir / Ensemble"
    if ("territoire de progres" in search_text or "tdp" in search_text) and "ens" in search_text:
        return "TdP / Ensemble"
    if ("en commun" in search_text or re.search(r"\bec\b", search_text)) and "ens" in search_text:
        return "En commun / Ensemble"
    if ("sans etiquette" in search_text or re.search(r"\bse\b", search_text)) and "ens" in search_text:
        return "SE / Ensemble"
    if nuance_key == "RN":
        if any(
            token in search_text
            for token in [
                "udr",
                "union de l extreme droite",
                "union de l'extrême droite",
                "cnip",
                "rad",
                "laf",
                "rlc",
                "dlf",
                "alliance locale",
                "app rn",
            ]
        ):
            return "Alliés RN"
        return "Rassemblement national"
    if nuance_key == "UXD":
        if any(
            token in search_text
            for token in ["rn", "udr", "rad", "r a d", "räd", "rade", "mc", "cnip", "dlf"]
        ):
            return "Alliés RN"
        return "Union de l'extrême droite"
    if nuance_key in {"REC", "EXD"}:
        if "reconquete" in search_text or "zemmour" in search_text or nuance_key == "REC":
            return "Reconquête"
        if "rn" in search_text or "udr" in search_text or "rad" in search_text or "cnip" in search_text:
            return "Alliés RN"
        return "Extrême droite"
    if nuance_key == "UG":
        if any(token in search_text for token in ["france insoumise", "insoumise", "lfi"]):
            return "LFI / NFP"
        if "place publique" in search_text:
            return "PP / NFP"
        if any(token in search_text for token in ["socialiste", "parti socialiste"]):
            return "PS / NFP"
        if any(token in search_text for token in ["ecolog", "eelv", "verts"]):
            return "EELV / NFP"
        if any(token in search_text for token in ["communiste", "pcf"]):
            return "PCF / NFP"
        return "Autre NFP"
    if nuance_key == "ENS":
        if "udi" in search_text:
            return "UDI / Ensemble"
        if "parti radical" in search_text or "prv" in search_text:
            return "PRV / Ensemble"
        if "agir" in search_text:
            return "Agir / Ensemble"
        if "territoire de progres" in search_text or "tdp" in search_text:
            return "TdP / Ensemble"
        if "en commun" in search_text or re.search(r"\bec\b", search_text):
            return "En commun / Ensemble"
        if "sans etiquette" in search_text or re.search(r"\bse\b", search_text):
            return "SE / Ensemble"
        return "Renaissance / Ensemble"
    if nuance_key == "HOR":
        return "Horizons / Ensemble"
    return base_label


def _parse_percent_value(value: object) -> float:
    if pd.isna(value):
        return 0.0
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        number = float(value)
    else:
        text = (
            str(value)
            .replace("\u00a0", "")
            .replace(" ", "")
            .replace("%", "")
            .strip()
        )
        if not text:
            return 0.0
        if "," in text and "." not in text:
            text = text.replace(",", ".")
        number = float(text or 0.0)
    if number > 100.0:
        number = number / 100.0
    return number


def _parse_number_value(value: object) -> object:
    if pd.isna(value):
        return pd.NA
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    text = (
        str(value)
        .replace("\u00a0", "")
        .replace(" ", "")
        .strip()
    )
    if not text or text in {"-", "–"}:
        return pd.NA
    return pd.to_numeric(text, errors="coerce")


def _display_text(value: object, fallback: str = "n.d.") -> str:
    if pd.isna(value):
        return fallback
    text = str(value).strip()
    return text if text else fallback


def _safe_text(value: object) -> str:
    if pd.isna(value):
        return ""
    return str(value)


def _normalize_nfp_party_code(value: object) -> str:
    if pd.isna(value):
        return ""
    return (
        str(value)
        .replace("\u00a0", " ")
        .strip()
        .upper()
    )


def _map_nfp_party_code_to_label(value: object) -> str:
    party_code = _normalize_nfp_party_code(value)
    explicit_map = {
        "LFI": "LFI / NFP",
        "LFI ": "LFI / NFP",
        "LFI.": "LFI / NFP",
        "LFI?": "LFI / NFP",
        "LFI/": "LFI / NFP",
        "LFI-": "LFI / NFP",
        "LFI DISS": "LFI dissidents / hors NFP",
        "PS": "PS / NFP",
        "PP": "PP / NFP",
        "EELV": "EELV / NFP",
        "PCF": "PCF / NFP",
        "NPA": "NPA / NFP",
        "G.S": "Génération.s / NFP",
        "GS": "Génération.s / NFP",
        "GRS": "Gauche républicaine et socialiste / NFP",
        "REV": "LFI / NFP",
        "TAVINI": "Tavini / NFP",
        "PEYI-A": "Peyi-A / NFP",
        "PLR": "PLR / NFP",
        "RE974": "Réunion Écologie 974 / NFP",
        "POI": "LFI / NFP",
        "PD !": "PD ! / NFP",
        "PD!": "PD ! / NFP",
        "SSDAC": "SSDAC / NFP",
        "EH BAI": "EH Bai / NFP",
        "MDES": "MDES / NFP",
        "LP": "LP / NFP",
        "PPDG": "PPDG / NFP",
        "GE": "GE / NFP",
        "LFO": "LFO / NFP",
        "SE": "SE / NFP",
        "DVG": "DVG / NFP",
        "ABC": "ABC / NFP",
        "ND": "ND / NFP",
    }
    if party_code in explicit_map:
        return explicit_map[party_code]
    if not party_code or party_code in {"NONE", "NAN", "<NA>"}:
        return ""
    return f"{party_code.title()} / NFP"


def _has_explicit_nfp_party_code(value: object) -> bool:
    party_code = _normalize_nfp_party_code(value)
    return party_code not in {"", "NONE", "NAN", "<NA>"}


def _normalize_nfp_circo_key(value: object) -> str:
    if pd.isna(value):
        return ""
    raw = (
        str(value)
        .replace("\u00a0", " ")
        .strip()
    )
    if not raw:
        return ""
    compact = (
        raw.replace(" ", "")
        .replace("'", "")
        .replace("’", "")
        .replace("é", "e")
        .replace("è", "e")
        .replace("ê", "e")
        .replace("à", "a")
        .replace("û", "u")
        .replace("ç", "c")
    )
    exact_named_keys = {
        "Saint-Pierre-et-Miquelon": "975-97501",
        "Saint-Pierre-et-Miquelon": "975-97501",
    }
    if compact in exact_named_keys:
        return exact_named_keys[compact]
    named_prefixes = {
        "HorsdeFrance": "ZZ",
        "Nouvelle-Caledonie": "988",
        "PolynesieFrancaise": "987",
        "Saint-Pierre-et-Miquelon": "975",
        "WallisetFutuna": "986",
        "Saint-Barthelemy": "ZX",
        "Saint-Barthelemy/Saint-Martin": "ZX",
        "Saint-Martin/Saint-Barthelemy": "ZX",
    }
    match = re.fullmatch(r"([0-9A-Za-z-]+)-([0-9]{1,2})", compact)
    if not match:
        return compact
    left, right = match.groups()
    if left.isdigit():
        dept = left.zfill(2) if len(left) <= 2 else left
        circo_num = int(right)
        if len(left) <= 2:
            return f"{dept}-{int(left) * 100 + circo_num}"
        return f"{dept}-{left}{circo_num:02d}"
    prefix = named_prefixes.get(left, left.upper())
    if prefix in {"ZZ", "ZX"}:
        return f"{prefix}-{prefix}{int(right):02d}"
    if prefix.isdigit():
        return f"{prefix}-{prefix}{int(right):02d}"
    if re.fullmatch(r"[0-9][A-Z]", prefix):
        return f"{prefix}-{prefix}{int(right):02d}"
    return f"{prefix}-{int(right):02d}"


def _nfp_assignment_score(nuance: object, current_force_label: object, target_force_label: object, nfp_party_code: object) -> int:
    target = str(target_force_label or "").strip()
    current = str(current_force_label or "").strip()
    nuance_key = str(nuance or "").strip().upper()
    party_code = _normalize_nfp_party_code(nfp_party_code)

    if not target:
        return 0
    if current == target:
        return 200
    if "/ NFP" in current:
        return 150

    if target == "LFI / NFP":
        ranking = {"FI": 120, "UG": 110, "DVG": 70, "EXG": 60, "REG": 25}
    elif target in {"PS / NFP", "PP / NFP"}:
        ranking = {"SOC": 120, "PS": 120, "UG": 110, "DVG": 80, "RDG": 70, "REG": 25}
    elif target == "EELV / NFP":
        ranking = {"VEC": 120, "ECO": 120, "UG": 110, "REG": 70, "DVG": 45}
    elif target == "PCF / NFP":
        ranking = {"COM": 120, "UG": 110, "EXG": 70, "DVG": 45}
    elif target == "NPA / NFP":
        ranking = {"EXG": 120, "UG": 110}
    else:
        if party_code in {"TAVINI", "MDES", "PEYI-A", "PEYI-A", "SE", "G.S", "GS"}:
            ranking = {"REG": 130, "DVG": 100, "ECO": 90, "VEC": 90, "EXG": 80, "COM": 70, "SOC": 70, "PS": 70, "UG": 60, "FI": 50}
        elif party_code in {"PLR", "LP", "RE974", "DVG"}:
            ranking = {"DVG": 130, "REG": 80, "ECO": 90, "VEC": 90, "EXG": 80, "COM": 70, "SOC": 70, "PS": 70, "UG": 60, "FI": 50}
        else:
            ranking = {"DVG": 120, "REG": 110, "ECO": 90, "VEC": 90, "EXG": 80, "COM": 70, "SOC": 70, "PS": 70, "UG": 60, "FI": 50}
    return ranking.get(nuance_key, 0)


def _apply_nfp_circo_mapping_to_candidates(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty or "circo_key" not in frame.columns or "nfp_internal_party" not in frame.columns:
        return frame
    working = frame.copy()
    for circo_key, group in working.groupby("circo_key", dropna=False):
        target_label = str(group["nfp_internal_party"].dropna().iloc[0]).strip() if group["nfp_internal_party"].notna().any() else ""
        party_code = group["nfp_party_code"].dropna().iloc[0] if "nfp_party_code" in group.columns and group["nfp_party_code"].notna().any() else pd.NA
        if not target_label or not _has_explicit_nfp_party_code(party_code):
            continue
        scores = group.apply(
            lambda row: _nfp_assignment_score(row.get("nuance"), row.get("force_label"), target_label, party_code),
            axis=1,
        )
        if scores.empty or int(scores.max()) <= 0:
            continue
        vote_series = group["votes"] if "votes" in group.columns else pd.Series(0.0, index=group.index)
        share_series = group["share_exprimes"] if "share_exprimes" in group.columns else pd.Series(0.0, index=group.index)
        best_index = (
            group.assign(
                _nfp_score=scores,
                _sort_votes=pd.to_numeric(vote_series, errors="coerce").fillna(0.0),
                _sort_share=pd.to_numeric(share_series, errors="coerce").fillna(0.0),
            )
            .sort_values(["_nfp_score", "_sort_votes", "_sort_share"], ascending=[False, False, False])
            .index[0]
        )
        working.loc[best_index, "force_label"] = target_label
        working.loc[best_index, "analysis_force_label"] = target_label
    return working


@st.cache_data(show_spinner=False)
def _load_nfp_internal_party_mapping() -> pd.DataFrame:
    for path in NFP_INTERNAL_PARTY_MAPPING_PATHS:
        if not path.exists():
            continue
        separator = "," if path.name.lower() == "nfp_circo.csv" else ";"
        frame = pd.read_csv(path, sep=separator, dtype="string")
        if not frame.empty:
            if {"Circo", "Parti"}.issubset(frame.columns):
                normalized = frame.rename(columns={"Circo": "source_circo_code", "Parti": "nfp_party_code"}).copy()
                normalized["source_circo_code"] = normalized["source_circo_code"].astype("string").str.strip()
                normalized["nfp_party_code"] = normalized["nfp_party_code"].astype("string").str.strip()
                normalized["circo_key"] = normalized["source_circo_code"].map(_normalize_nfp_circo_key).astype("string").str.strip()
                normalized = normalized.loc[normalized["nfp_party_code"].map(_has_explicit_nfp_party_code)].copy()
                normalized["nfp_internal_party"] = normalized["nfp_party_code"].map(_map_nfp_party_code_to_label)
                normalized = normalized.loc[
                    normalized["circo_key"].notna()
                    & normalized["circo_key"].ne("")
                    & normalized["nfp_internal_party"].astype("string").str.strip().ne("")
                ].copy()
                return normalized[["circo_key", "source_circo_code", "nfp_party_code", "nfp_internal_party"]].drop_duplicates(subset=["circo_key"])
            if {"circo_key", "nfp_internal_party"}.issubset(frame.columns):
                frame["circo_key"] = frame["circo_key"].astype("string").str.strip()
                return frame
            return frame
    return pd.DataFrame()


def _normalize_person_key(first_name: object, last_name: object) -> str:
    return _normalize_search_text(f"{_safe_text(first_name)} {_safe_text(last_name)}")


def _format_department_code(value: object) -> str:
    text = str(value or "").strip()
    if text.endswith(".0"):
        text = text[:-2]
    return text.zfill(2) if text.isdigit() else text


def _load_local_2024_visual_rows() -> pd.DataFrame:
    path = Path.cwd() / LOCAL_2024_VISUAL_ROWS
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path)


@st.cache_data(show_spinner=False)
def _load_official_general_results() -> pd.DataFrame:
    chunks: list[pd.DataFrame] = []
    seen_paths: set[str] = set()
    for path in OFFICIAL_GENERAL_RESULT_PATHS:
        resolved = str(path)
        if resolved in seen_paths or not path.exists():
            continue
        seen_paths.add(resolved)
        for chunk in pd.read_csv(path, sep=";", chunksize=200000, low_memory=False):
            subset = chunk.loc[chunk["id_election"].isin(["2024_legi_t1", "2024_legi_t2"])].copy()
            if not subset.empty:
                chunks.append(subset)
    if not chunks:
        circo = _load_official_circo_results_from_zip()
        if circo.empty:
            return pd.DataFrame()
        frame = pd.DataFrame(
            {
                "id_election": "2024_legi_t1",
                "code_departement": circo.get("Code département"),
                "libelle_departement": circo.get("Libellé département"),
                "code_circonscription": circo.get("Code circonscription législative"),
                "libelle_circonscription": circo.get("Libellé circonscription législative"),
                "code_commune": pd.Series(pd.NA, index=circo.index, dtype="string"),
                "libelle_commune": pd.Series(pd.NA, index=circo.index, dtype="string"),
                "code_bv": pd.Series(pd.NA, index=circo.index, dtype="string"),
                "id_brut_miom": pd.Series(pd.NA, index=circo.index, dtype="string"),
                "inscrits": circo.get("Inscrits"),
                "abstentions": circo.get("Abstentions"),
                "votants": circo.get("Votants"),
                "blancs": circo.get("Blancs"),
                "nuls": circo.get("Nuls"),
                "exprimes": circo.get("Exprimés"),
            }
        )
    else:
        frame = pd.concat(chunks, ignore_index=True).drop_duplicates().reset_index(drop=True)
    for column in ["id_election", "code_departement", "code_commune", "code_circonscription", "code_bv", "id_brut_miom"]:
        if column in frame.columns:
            frame[column] = frame[column].astype("string").str.strip()
    for column in ["libelle_departement", "libelle_commune", "libelle_circonscription"]:
        if column in frame.columns:
            frame[column] = frame[column].astype("string").str.strip()
    for column in ["inscrits", "abstentions", "votants", "blancs", "nuls", "exprimes"]:
        if column in frame.columns:
            frame[column] = pd.to_numeric(frame[column], errors="coerce")
    return frame


@st.cache_data(show_spinner=False)
def _load_official_circo_results_from_zip() -> pd.DataFrame:
    for path in OFFICIAL_2024_CIRCO_RESULTS_LOCAL_PATHS:
        if not path.exists():
            continue
        try:
            frame = pd.read_csv(path, sep=";")
            if not frame.empty:
                return frame
        except Exception:
            continue
    for path in OFFICIAL_2024_LEGISLATIVE_ZIP_PATHS:
        if not path.exists():
            continue
        with ZipFile(path) as archive:
            if OFFICIAL_2024_CIRCO_RESULTS_INNER_PATH not in archive.namelist():
                continue
            with archive.open(OFFICIAL_2024_CIRCO_RESULTS_INNER_PATH) as handle:
                frame = pd.read_csv(handle, sep=";")
            if frame.empty:
                continue
            return frame
    return pd.DataFrame()


@st.cache_data(show_spinner=False)
def _load_official_first_round_circo_candidate_results() -> pd.DataFrame:
    circo = _load_official_circo_results_from_zip()
    if circo.empty:
        return pd.DataFrame()

    working = circo.copy()
    records: list[dict[str, object]] = []
    candidate_indexes: list[int] = []
    for column in working.columns:
        match = re.fullmatch(r"Numéro de panneau (\d+)", str(column).strip())
        if match:
            candidate_indexes.append(int(match.group(1)))
    candidate_indexes = sorted(set(candidate_indexes))

    for _, row in working.iterrows():
        dept_code = _format_department_code(row.get("Code département"))
        dept_label = _safe_text(row.get("Libellé département")).strip()
        circo_code_raw = _format_circo_code(row.get("Code circonscription législative"))
        circo_label = _safe_text(row.get("Libellé circonscription législative")).strip()
        if not dept_code or not circo_code_raw:
            continue
        circo_key = f"{dept_code}-{circo_code_raw}"
        exprimes = pd.to_numeric(row.get("Exprimés"), errors="coerce")
        for idx in candidate_indexes:
            panel = pd.to_numeric(row.get(f"Numéro de panneau {idx}"), errors="coerce")
            nuance = _safe_text(row.get(f"Nuance candidat {idx}")).strip().upper()
            last_name = _safe_text(row.get(f"Nom candidat {idx}")).strip()
            first_name = _safe_text(row.get(f"Prénom candidat {idx}")).strip()
            if pd.isna(panel) and not nuance and not last_name and not first_name:
                continue
            votes = pd.to_numeric(row.get(f"Voix {idx}"), errors="coerce")
            if pd.isna(votes):
                continue
            records.append(
                {
                    "code_departement": dept_code,
                    "libelle_departement": dept_label,
                    "code_circonscription": circo_code_raw,
                    "libelle_circonscription": circo_label,
                    "circo_key": circo_key,
                    "candidate_key": _normalize_person_key(first_name, last_name),
                    "no_panneau": panel,
                    "nuance": nuance,
                    "nom": last_name,
                    "prenom": first_name,
                    "liste": pd.NA,
                    "libelle_abrege_liste": pd.NA,
                    "libelle_etendu_liste": pd.NA,
                    "votes": float(votes),
                    "voix": float(votes),
                    "exprimes_circo": exprimes,
                    "share_exprimes": float(_safe_percent(pd.Series([votes]), pd.Series([exprimes])).iloc[0]),
                    "inscrits": pd.to_numeric(row.get("Inscrits"), errors="coerce"),
                    "votants": pd.to_numeric(row.get("Votants"), errors="coerce"),
                    "abstentions": pd.to_numeric(row.get("Abstentions"), errors="coerce"),
                    "blancs": pd.to_numeric(row.get("Blancs"), errors="coerce"),
                    "nuls": pd.to_numeric(row.get("Nuls"), errors="coerce"),
                    "exprimes": exprimes,
                    "election_id": "2024_legi_t1",
                }
            )
    if not records:
        return pd.DataFrame()
    return pd.DataFrame(records)


@st.cache_data(show_spinner=False)
def _load_official_t2_candidatures_from_zip() -> pd.DataFrame:
    for path in OFFICIAL_2024_LEGISLATIVE_ZIP_PATHS:
        if not path.exists():
            continue
        with ZipFile(path) as archive:
            if OFFICIAL_2024_T2_CANDIDATURES_INNER_PATH not in archive.namelist():
                continue
            with archive.open(OFFICIAL_2024_T2_CANDIDATURES_INNER_PATH) as handle:
                frame = pd.read_csv(handle, sep=";")
            if frame.empty:
                continue
            return frame
    return pd.DataFrame()


def _normalize_wikipedia_table_text(value: object) -> str:
    return _normalize_search_text(_safe_text(value)).replace(" ", "")


def _parse_wikipedia_circo_ordinal(value: object) -> int | None:
    text = _normalize_search_text(value)
    if not text:
        return None
    if "unique" in text:
        return 1
    match = re.search(r"(\d+)", text)
    if match:
        return int(match.group(1))
    word_map = {
        "premiere": 1,
        "deuxieme": 2,
        "troisieme": 3,
        "quatrieme": 4,
        "cinquieme": 5,
        "sixieme": 6,
        "septieme": 7,
        "huitieme": 8,
        "neuvieme": 9,
        "dixieme": 10,
        "onzieme": 11,
        "douzieme": 12,
        "treizieme": 13,
        "quatorzieme": 14,
        "quinzieme": 15,
        "seizieme": 16,
        "dixseptieme": 17,
        "dixhuitieme": 18,
        "dixneuvieme": 19,
        "vingtieme": 20,
    }
    compact = text.replace(" ", "")
    for token, ordinal in word_map.items():
        if token in compact:
            return ordinal
    return None


def _build_wikipedia_circo_code(dept_code: str, ordinal: int) -> str:
    dept_text = _format_department_code(dept_code)
    if dept_text.isdigit():
        return str(int(f"{dept_text}{int(ordinal):02d}"))
    return f"{dept_text}{int(ordinal):02d}"


def _fetch_wikipedia_html(url: str) -> str:
    response = requests.get(
        url,
        headers={"User-Agent": "Mozilla/5.0 Codex scraper"},
        timeout=30,
    )
    response.raise_for_status()
    return response.text


def _flatten_wikipedia_columns(frame: pd.DataFrame) -> list[str]:
    if isinstance(frame.columns, pd.MultiIndex):
        flattened: list[str] = []
        for column in frame.columns.to_flat_index():
            flattened.append(" | ".join(_safe_text(part) for part in column if _safe_text(part)).strip())
        return flattened
    return [_safe_text(column).strip() for column in frame.columns]


def _extract_wikipedia_summary_payload(election_table: pd.DataFrame) -> dict[str, object]:
    if election_table.empty or election_table.shape[1] < 8:
        return {}

    working = election_table.iloc[:, :8].copy()
    summary_fields = {
        "votesvalides": ("votes_valides", True),
        "votesblancs": ("votes_blancs", True),
        "votesnuls": ("votes_nuls", True),
        "total": ("total", True),
        "abstention": ("abstention", True),
        "inscrits/participation": ("inscrits_participation", False),
        "inscritsparticipation": ("inscrits_participation", False),
    }
    payload: dict[str, object] = {}

    for row in working.itertuples(index=False):
        header_text = ""
        for index in range(4):
            candidate_slot = _safe_text(row[index]).strip()
            if candidate_slot:
                header_text = candidate_slot
                break
        normalized_header = _normalize_wikipedia_table_text(header_text)
        if normalized_header not in summary_fields:
            continue
        field_prefix, include_percent = summary_fields[normalized_header]
        payload[f"{field_prefix}_t1"] = _parse_number_value(row[4])
        payload[f"{field_prefix}_t2"] = _parse_number_value(row[6])
        if include_percent:
            pct_t1 = _parse_percent_value(row[5])
            pct_t2 = _parse_percent_value(row[7])
            if field_prefix in {"votes_blancs", "votes_nuls"}:
                if pct_t1 > 10.0:
                    pct_t1 = pct_t1 / 100.0
                if pct_t2 > 10.0:
                    pct_t2 = pct_t2 / 100.0
            payload[f"{field_prefix}_pct_t1"] = pct_t1
            payload[f"{field_prefix}_pct_t2"] = pct_t2
        else:
            payload["participation_pct_t1"] = _parse_percent_value(row[5])
            payload["participation_pct_t2"] = _parse_percent_value(row[7])
    return payload


def _select_wikipedia_2024_result_table(tables: list[pd.DataFrame]) -> pd.DataFrame:
    for table in reversed(tables):
        flattened = " ".join(_flatten_wikipedia_columns(table)).lower()
        if "second tour" in flattened and "candidat" in flattened and ("parti" in flattened or "nuance" in flattened):
            if table.shape[1] >= 8:
                return table.copy()
    return pd.DataFrame()


def _parse_wikipedia_second_round_candidates(
    page_url: str,
    circo_key: str,
    dept_code: str,
    dept_label: str,
    circo_label: str,
    election_table: pd.DataFrame,
) -> pd.DataFrame:
    if election_table.empty or election_table.shape[1] < 8:
        return pd.DataFrame()

    working = election_table.iloc[:, :8].copy()
    summary_payload = _extract_wikipedia_summary_payload(working)
    working.columns = [
        "unused_candidate_slot",
        "candidate_name",
        "party_label",
        "nuance",
        "first_round_votes",
        "first_round_percent",
        "second_round_votes",
        "second_round_percent",
    ]

    rows: list[dict[str, object]] = []
    for row in working.itertuples(index=False):
        candidate_name = _safe_text(row.candidate_name).replace("[n 1]", "").replace("[n 2]", "").strip()
        if not candidate_name:
            candidate_name = _safe_text(row.unused_candidate_slot).replace("[n 1]", "").replace("[n 2]", "").strip()
        normalized_candidate = _normalize_wikipedia_table_text(candidate_name)
        if not candidate_name or normalized_candidate in {
            "votesvalides",
            "votesblancs",
            "votesnuls",
            "total",
            "abstention",
            "inscrits/participation",
            "inscritsparticipation",
            "candidat",
        }:
            continue
        second_round_percent_text = _safe_text(row.second_round_percent)
        second_round_votes_text = _safe_text(row.second_round_votes)
        if not second_round_percent_text or "retrait" in _normalize_search_text(second_round_percent_text):
            continue
        if second_round_percent_text.strip() in {"-", "–"} or second_round_votes_text.strip() in {"", "-", "–"}:
            continue
        second_round_votes = pd.to_numeric(
            second_round_votes_text.replace("\u00a0", "").replace(" ", ""),
            errors="coerce",
        )
        second_round_percent = _parse_percent_value(second_round_percent_text)
        first_round_votes = pd.to_numeric(
            _safe_text(row.first_round_votes).replace("\u00a0", "").replace(" ", ""),
            errors="coerce",
        )
        first_round_percent = _parse_percent_value(row.first_round_percent)
        if pd.isna(second_round_votes) or second_round_percent <= 0:
            continue
        nuance = _safe_text(row.nuance).strip().upper()
        party_label = _safe_text(row.party_label).strip()
        force_label = _detailed_force_label(nuance, party_label, party_label, party_label)
        force_label = _normalize_nfp_force_label(force_label, nuance)
        analysis_force_label = force_label if force_label else _analysis_force_label(force_label, nuance)
        rows.append(
            {
                "circo_key": circo_key,
                "dept_code": dept_code,
                "dept_label": dept_label,
                "circo_code": circo_key.split("-", 1)[1] if "-" in circo_key else circo_key,
                "circo_label": circo_label,
                "candidate_name": candidate_name,
                "candidate_key": _normalize_person_key("", candidate_name),
                "party_label": party_label,
                "nuance": nuance,
                "force_label": force_label,
                "analysis_force_label": analysis_force_label,
                "first_round_votes": float(first_round_votes) if pd.notna(first_round_votes) else pd.NA,
                "first_round_percent": float(first_round_percent) if first_round_percent > 0 else pd.NA,
                "voix": float(second_round_votes),
                "share_exprimes_t2": float(second_round_percent),
                "wikipedia_url": page_url,
                **summary_payload,
            }
        )
    if not rows:
        return pd.DataFrame()
    result = pd.DataFrame(rows).sort_values(["voix", "candidate_name"], ascending=[False, True]).reset_index(drop=True)
    result["rank_t2"] = result.index + 1
    return result


def _scrape_wikipedia_constituency_second_round_results() -> pd.DataFrame:
    html = _fetch_wikipedia_html(WIKIPEDIA_2024_RESULTS_PAGE_URL)
    soup = BeautifulSoup(html, "html.parser")
    page_records: list[dict[str, object]] = []
    for header in soup.select("h3"):
        header_text = " ".join(header.get_text(" ", strip=True).split())
        dept_label = ""
        dept_code = ""
        match = re.match(r"^(?P<label>.+?)\s*\((?P<code>[0-9A-Z]{2,3})\)$", header_text)
        if match:
            dept_label = match.group("label").strip()
            dept_code = _format_department_code(match.group("code"))
        elif "francais etablis hors de france" in _normalize_search_text(header_text):
            dept_label = "Français établis hors de France"
            dept_code = "ZZ"
        if not dept_code:
            continue

        sibling = header.parent.find_next_sibling() if header.parent is not None else header.find_next_sibling()
        section_links: list[str] = []
        while sibling is not None and sibling.name != "h3":
            for link in sibling.select('a[href^="/wiki/"]'):
                href = _safe_text(link.get("href"))
                decoded_href = unquote(href)
                if "Élections_législatives_de_2024_dans_" not in decoded_href:
                    continue
                section_links.append(f"https://fr.wikipedia.org{href}")
            sibling = sibling.find_next_sibling()
        if not section_links:
            continue
        page_records.append(
            {
                "dept_label": dept_label,
                "dept_code": dept_code,
                "page_url": section_links[0],
            }
        )

    selected_urls = {record["page_url"] for record in page_records}
    for link in soup.select('a[href^="/wiki/"]'):
        href = _safe_text(link.get("href"))
        decoded_href = unquote(href)
        if "circonscriptions_des_Français_établis_hors_de_France" not in decoded_href:
            continue
        page_url = f"https://fr.wikipedia.org{href}"
        if page_url in selected_urls:
            continue
        page_records.append(
            {
                "dept_label": "Français établis hors de France",
                "dept_code": "ZZ",
                "page_url": page_url,
            }
        )

    if not page_records:
        return pd.DataFrame()

    frames: list[pd.DataFrame] = []
    for record in pd.DataFrame(page_records).drop_duplicates(subset=["dept_code"]).itertuples(index=False):
        dept_html = _fetch_wikipedia_html(str(record.page_url))
        tables = pd.read_html(StringIO(dept_html))
        circo_tables = [table for table in tables if not _select_wikipedia_2024_result_table([table]).empty]
        ordinal = 1
        for election_table in circo_tables:
            circo_code = _build_wikipedia_circo_code(str(record.dept_code), ordinal)
            circo_label = f"{ordinal}ère circonscription" if ordinal == 1 else f"{ordinal}ème circonscription"
            parsed = _parse_wikipedia_second_round_candidates(
                page_url=str(record.page_url),
                circo_key=f"{record.dept_code}-{circo_code}",
                dept_code=str(record.dept_code),
                dept_label=str(record.dept_label),
                circo_label=circo_label,
                election_table=election_table,
            )
            if not parsed.empty:
                frames.append(parsed)
            ordinal += 1
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)


@st.cache_data(show_spinner=False)
def _load_wikipedia_constituency_second_round_results() -> pd.DataFrame:
    for path in WIKIPEDIA_2024_T2_RESULTS_LOCAL_PATHS:
        if not path.exists():
            continue
        try:
            frame = pd.read_csv(path)
            has_expected_columns = {
                "circo_key",
                "candidate_name",
                "share_exprimes_t2",
                "votes_valides_t2",
                "abstention_pct_t2",
            }.issubset(frame.columns)
            covered_circos = int(frame["circo_key"].nunique()) if "circo_key" in frame.columns else 0
            if not frame.empty and has_expected_columns and covered_circos >= 500:
                return frame
        except Exception:
            continue
    try:
        frame = _scrape_wikipedia_constituency_second_round_results()
        if not frame.empty:
            target_path = WIKIPEDIA_2024_T2_RESULTS_LOCAL_PATHS[0]
            target_path.parent.mkdir(parents=True, exist_ok=True)
            frame.to_csv(target_path, index=False)
        return frame
    except Exception:
        return pd.DataFrame()


@st.cache_data(show_spinner=False)
def _load_official_candidate_results_2024() -> pd.DataFrame:
    usecols = [
        "id_election",
        "id_brut_miom",
        "code_departement",
        "code_commune",
        "code_bv",
        "no_panneau",
        "voix",
        "nuance",
        "sexe",
        "nom",
        "prenom",
        "liste",
        "libelle_abrege_liste",
        "libelle_etendu_liste",
        "nom_tete_liste",
        "binome",
    ]
    dtype = {
        "id_election": "string",
        "id_brut_miom": "string",
        "code_departement": "string",
        "code_commune": "string",
        "code_bv": "string",
        "no_panneau": "string",
        "nuance": "string",
        "sexe": "string",
        "nom": "string",
        "prenom": "string",
        "liste": "string",
        "libelle_abrege_liste": "string",
        "libelle_etendu_liste": "string",
        "nom_tete_liste": "string",
        "binome": "string",
    }
    for path in OFFICIAL_2024_CANDIDATE_RESULTS_LOCAL_PATHS:
        if not path.exists():
            continue
        try:
            frame = pd.read_csv(path, sep=";", usecols=usecols, dtype=dtype, low_memory=False)
            if not frame.empty:
                frame["voix"] = pd.to_numeric(frame.get("voix"), errors="coerce")
                frame["no_panneau"] = pd.to_numeric(frame.get("no_panneau"), errors="coerce")
                for column in ["code_departement", "code_commune", "code_bv", "id_brut_miom"]:
                    if column in frame.columns:
                        frame[column] = frame[column].astype("string").str.strip()
                return frame
        except Exception:
            pass
    try:
        chunks: list[pd.DataFrame] = []
        for chunk in pd.read_csv(
            OFFICIAL_CANDIDATE_RESULTS_REMOTE_URL,
            sep=";",
            chunksize=250000,
            usecols=usecols,
            dtype=dtype,
        ):
            subset = chunk.loc[chunk["id_election"].isin(["2024_legi_t1", "2024_legi_t2"])].copy()
            if not subset.empty:
                chunks.append(subset)
        if not chunks:
            return pd.DataFrame()
        frame = pd.concat(chunks, ignore_index=True)
        frame["voix"] = pd.to_numeric(frame.get("voix"), errors="coerce")
        frame["no_panneau"] = pd.to_numeric(frame.get("no_panneau"), errors="coerce")
        for column in ["code_departement", "code_commune", "code_bv", "id_brut_miom"]:
            if column in frame.columns:
                frame[column] = frame[column].astype("string").str.strip()
        return frame
    except Exception:
        return pd.DataFrame()


@st.cache_data(show_spinner=False)
def _build_official_candidate_results_by_circo(election_id: str) -> pd.DataFrame:
    if election_id == "2024_legi_t1":
        aggregated = _load_official_first_round_circo_candidate_results()
        if aggregated.empty:
            return pd.DataFrame()
        wikipedia_hints = _load_wikipedia_constituency_second_round_results()
        if not wikipedia_hints.empty and {"circo_key", "candidate_key", "party_label"}.issubset(wikipedia_hints.columns):
            wikipedia_hints = (
                wikipedia_hints[["circo_key", "candidate_key", "party_label"]]
                .dropna(subset=["circo_key", "candidate_key", "party_label"])
                .drop_duplicates(subset=["circo_key", "candidate_key"])
                .rename(columns={"party_label": "wikipedia_party_label"})
            )
            aggregated = aggregated.merge(wikipedia_hints, on=["circo_key", "candidate_key"], how="left")
        else:
            aggregated["wikipedia_party_label"] = pd.NA
        aggregated["force_label_detailed"] = aggregated.apply(
            lambda row: _detailed_force_label(
                row.get("nuance"),
                row.get("wikipedia_party_label"),
            ),
            axis=1,
        )
        aggregated["force_label"] = aggregated["force_label_detailed"]
        aggregated["analysis_force_label"] = aggregated.apply(
            lambda row: _analysis_force_label(row.get("force_label_detailed"), row.get("nuance")),
            axis=1,
        )
        nfp_mapping = _load_nfp_internal_party_mapping()
        if not nfp_mapping.empty and {"circo_key", "nfp_internal_party"}.issubset(nfp_mapping.columns):
            nfp_mapping = (
                nfp_mapping[["circo_key", "source_circo_code", "nfp_party_code", "nfp_internal_party"]]
                .dropna(subset=["circo_key"])
                .drop_duplicates(subset=["circo_key"])
            )
            aggregated = aggregated.merge(nfp_mapping, on="circo_key", how="left")
            aggregated = _apply_nfp_circo_mapping_to_candidates(aggregated)
        return aggregated

    general = _load_official_general_results()
    candidate_results = _load_official_candidate_results_2024()
    if general.empty or candidate_results.empty or "id_election" not in general.columns:
        return pd.DataFrame()

    mapping = general.loc[general["id_election"] == election_id].copy()
    if mapping.empty or "code_circonscription" not in mapping.columns:
        return pd.DataFrame()
    for column in ["code_departement", "code_commune", "code_bv", "id_brut_miom", "code_circonscription"]:
        if column in mapping.columns:
            mapping[column] = mapping[column].astype(str)
    if mapping["code_circonscription"].replace({"None": pd.NA, "nan": pd.NA, "<NA>": pd.NA, "": pd.NA}).dropna().empty:
        return pd.DataFrame()
    join_keys = ["id_brut_miom"] if "id_brut_miom" in mapping.columns and "id_brut_miom" in candidate_results.columns else [
        key for key in ["code_departement", "code_commune", "code_bv"] if key in mapping.columns and key in candidate_results.columns
    ]
    if not join_keys:
        return pd.DataFrame()

    bureau_map = mapping[
        list(
            dict.fromkeys(
                [
                    *join_keys,
                    "code_departement",
                    "libelle_departement",
                    "code_circonscription",
                    "libelle_circonscription",
                    "exprimes",
                ]
            )
        )
    ].drop_duplicates()
    candidate_subset = candidate_results.loc[candidate_results["id_election"] == election_id].copy()
    candidate_subset = candidate_subset.drop(
        columns=[
            column
            for column in [
                "code_departement",
                "libelle_departement",
                "code_circonscription",
                "libelle_circonscription",
            ]
            if column in candidate_subset.columns and column not in join_keys
        ],
        errors="ignore",
    )
    merged = candidate_subset.merge(bureau_map, on=join_keys, how="inner")
    if merged.empty:
        return pd.DataFrame()

    aggregated = (
        merged.groupby(
            [
                "code_departement",
                "libelle_departement",
                "code_circonscription",
                "libelle_circonscription",
                "nuance",
                "nom",
                "prenom",
                "liste",
                "libelle_abrege_liste",
                "libelle_etendu_liste",
            ],
            dropna=False,
        )["voix"]
        .sum()
        .reset_index()
    )
    exprimes = (
        mapping.groupby(
            ["code_departement", "libelle_departement", "code_circonscription", "libelle_circonscription"],
            dropna=False,
        )["exprimes"]
        .sum()
        .reset_index()
        .rename(columns={"exprimes": "exprimes_circo"})
    )
    aggregated = aggregated.merge(
        exprimes,
        on=["code_departement", "libelle_departement", "code_circonscription", "libelle_circonscription"],
        how="left",
    )
    aggregated["candidate_key"] = aggregated.apply(lambda row: _normalize_person_key(row.get("prenom"), row.get("nom")), axis=1)
    aggregated["circo_key"] = aggregated.apply(
        lambda row: f"{_format_department_code(row['code_departement'])}-{_format_circo_code(row['code_circonscription'])}",
        axis=1,
    )
    wikipedia_hints = _load_wikipedia_constituency_second_round_results()
    if not wikipedia_hints.empty and {"circo_key", "candidate_key", "party_label"}.issubset(wikipedia_hints.columns):
        wikipedia_hints = (
            wikipedia_hints[["circo_key", "candidate_key", "party_label"]]
            .dropna(subset=["circo_key", "candidate_key", "party_label"])
            .drop_duplicates(subset=["circo_key", "candidate_key"])
            .rename(columns={"party_label": "wikipedia_party_label"})
        )
        aggregated = aggregated.merge(wikipedia_hints, on=["circo_key", "candidate_key"], how="left")
    else:
        aggregated["wikipedia_party_label"] = pd.NA
    aggregated["share_exprimes"] = _safe_percent(aggregated["voix"], aggregated["exprimes_circo"])
    aggregated["force_label_detailed"] = aggregated.apply(
        lambda row: _detailed_force_label(
            row.get("nuance"),
            row.get("wikipedia_party_label"),
            row.get("liste"),
            row.get("libelle_abrege_liste"),
            row.get("libelle_etendu_liste"),
        ),
        axis=1,
    )
    aggregated["analysis_force_label"] = aggregated.apply(
        lambda row: _analysis_force_label(row.get("force_label_detailed"), row.get("nuance")),
        axis=1,
    )
    return aggregated


@st.cache_data(show_spinner=False)
def _build_official_second_round_final_results() -> pd.DataFrame:
    aggregated = _build_official_candidate_results_by_circo("2024_legi_t2")
    if aggregated.empty:
        wikipedia_results = _load_wikipedia_constituency_second_round_results()
        if wikipedia_results.empty:
            return pd.DataFrame()
        result = wikipedia_results.copy()
        result["force_label"] = result["force_label"].fillna(
            result.apply(lambda row: _detailed_force_label(row.get("nuance"), row.get("party_label"), row.get("party_label"), row.get("party_label")), axis=1)
        )
        result["force_label"] = result.apply(
            lambda row: _normalize_nfp_force_label(row.get("force_label"), row.get("nuance")),
            axis=1,
        )
        result["analysis_force_label"] = result["analysis_force_label"].fillna(
            result.apply(lambda row: _analysis_force_label(row.get("force_label"), row.get("nuance")), axis=1)
        )
        result = result.sort_values(["circo_key", "rank_t2", "voix"], ascending=[True, True, False]).reset_index(drop=True)
        return result
    aggregated["share_exprimes_t2"] = aggregated["share_exprimes"]
    aggregated["force_label"] = aggregated["force_label_detailed"]
    aggregated["analysis_force_label"] = aggregated["analysis_force_label"].fillna(
        aggregated.apply(lambda row: _analysis_force_label(row.get("force_label"), row.get("nuance")), axis=1)
    )
    nfp_mapping = _load_nfp_internal_party_mapping()
    if not nfp_mapping.empty and {"circo_key", "nfp_internal_party"}.issubset(nfp_mapping.columns):
        nfp_mapping = nfp_mapping[["circo_key", "source_circo_code", "nfp_party_code", "nfp_internal_party"]].dropna(subset=["circo_key"]).drop_duplicates(subset=["circo_key"])
        aggregated = aggregated.merge(nfp_mapping, on="circo_key", how="left")
        aggregated["force_label"] = aggregated["nfp_internal_party"].where(
            aggregated["nuance"].astype(str).str.upper().eq("UG") & aggregated["nfp_internal_party"].notna(),
            aggregated["force_label"],
        )
        aggregated["analysis_force_label"] = aggregated["force_label"]
        aggregated = _apply_nfp_circo_mapping_to_candidates(aggregated)
        aggregated = aggregated.drop(columns=["nfp_internal_party", "nfp_party_code"], errors="ignore")
    aggregated["force_label"] = aggregated["force_label"].where(
        ~(aggregated["nuance"].astype(str).str.upper().eq("UG") & aggregated["force_label"].eq("Union de la gauche / NFP")),
        "Autre NFP",
    )
    aggregated["force_label"] = aggregated.apply(
        lambda row: _normalize_nfp_force_label(row.get("force_label"), row.get("nuance")),
        axis=1,
    )
    aggregated["analysis_force_label"] = aggregated["force_label"]
    aggregated["candidate_name"] = (aggregated["prenom"].fillna("").astype(str) + " " + aggregated["nom"].fillna("").astype(str)).str.strip()
    aggregated = aggregated.sort_values(
        ["circo_key", "voix", "candidate_name"],
        ascending=[True, False, True],
    ).reset_index(drop=True)
    aggregated["rank_t2"] = aggregated.groupby("circo_key").cumcount() + 1
    return aggregated


@st.cache_data(show_spinner=False)
def _build_official_2024_circo_force_analysis() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    first_round = _load_official_circo_results_from_zip()
    second_round_candidates = _load_official_t2_candidatures_from_zip()
    first_round_detailed = _build_official_candidate_results_by_circo("2024_legi_t1")
    if first_round.empty:
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

    wide = first_round.copy()
    for column in [
        "Inscrits",
        "Votants",
        "Abstentions",
        "Exprimés",
        "Blancs",
        "Nuls",
    ]:
        if column in wide.columns:
            wide[column] = pd.to_numeric(wide[column], errors="coerce")

    candidate_indices = sorted(
        {
            int(match.group(1))
            for column in wide.columns
            for match in [re.match(r"Nom candidat (\d+)", str(column))]
            if match is not None
        }
    )

    rows: list[dict[str, object]] = []
    for detail in wide.to_dict(orient="records"):
        if pd.isna(detail.get("Code département")) or pd.isna(detail.get("Code circonscription législative")):
            continue
        dept_code = _format_department_code(detail["Code département"])
        circo_code = _format_circo_code(detail["Code circonscription législative"])
        for idx in candidate_indices:
            last_name = detail.get(f"Nom candidat {idx}")
            first_name = detail.get(f"Prénom candidat {idx}")
            voix = pd.to_numeric(detail.get(f"Voix {idx}"), errors="coerce")
            if pd.isna(last_name) or pd.isna(voix):
                continue
            nuance = str(detail.get(f"Nuance candidat {idx}") or "").strip().upper()
            rows.append(
                {
                    "dept_code": dept_code,
                    "dept_label": str(detail.get("Libellé département") or ""),
                    "circo_code": circo_code,
                    "circo_label": str(detail.get("Libellé circonscription législative") or ""),
                    "circo_key": f"{dept_code}-{circo_code}",
                    "inscrits": float(detail.get("Inscrits") or 0.0),
                    "exprimes": float(detail.get("Exprimés") or 0.0),
                    "candidate_rank_panel": idx,
                    "candidate_last_name": str(last_name),
                    "candidate_first_name": str(first_name or ""),
                    "candidate_name": f"{first_name or ''} {last_name}".strip(),
                    "candidate_key": _normalize_person_key(first_name, last_name),
                    "nuance": nuance,
                    "force_label": _force_label_from_nuance(nuance),
                    "votes": float(voix),
                    "share_inscrits": _parse_percent_value(detail.get(f"% Voix/inscrits {idx}")),
                    "share_exprimes": _parse_percent_value(detail.get(f"% Voix/exprimés {idx}")),
                    "elected_first_round": str(detail.get(f"Elu {idx}") or "").strip().lower() == "élu",
                }
            )
    candidates = pd.DataFrame(rows)
    if candidates.empty:
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()
    if not first_round_detailed.empty:
        detailed_lookup = first_round_detailed[
            [
                "circo_key",
                "candidate_key",
                "force_label_detailed",
                "analysis_force_label",
                "liste",
                "libelle_abrege_liste",
                "libelle_etendu_liste",
            ]
        ].drop_duplicates(subset=["circo_key", "candidate_key"])
        candidates = candidates.merge(detailed_lookup, on=["circo_key", "candidate_key"], how="left")
        candidates["force_label"] = candidates["force_label_detailed"].fillna(candidates["force_label"])
    else:
        candidates["force_label_detailed"] = pd.NA
        candidates["analysis_force_label"] = pd.NA
        candidates["liste"] = pd.NA
        candidates["libelle_abrege_liste"] = pd.NA
        candidates["libelle_etendu_liste"] = pd.NA
    wikipedia_t2_hints = _load_wikipedia_constituency_second_round_results()
    if not wikipedia_t2_hints.empty and {"circo_key", "candidate_key", "party_label"}.issubset(wikipedia_t2_hints.columns):
        wikipedia_t2_hints = (
            wikipedia_t2_hints[["circo_key", "candidate_key", "party_label"]]
            .dropna(subset=["circo_key", "candidate_key", "party_label"])
            .drop_duplicates(subset=["circo_key", "candidate_key"])
            .rename(columns={"party_label": "wikipedia_party_label"})
        )
        candidates = candidates.merge(wikipedia_t2_hints, on=["circo_key", "candidate_key"], how="left")
    else:
        candidates["wikipedia_party_label"] = pd.NA
    candidates["force_label_detailed"] = candidates["force_label_detailed"].fillna(
        candidates.apply(
            lambda row: _detailed_force_label(
                row.get("nuance"),
                row.get("wikipedia_party_label"),
                row.get("liste"),
                row.get("libelle_abrege_liste"),
                row.get("libelle_etendu_liste"),
            ),
            axis=1,
        )
    )
    candidates["force_label"] = candidates["force_label_detailed"].fillna(candidates["force_label"])

    nfp_mapping = _load_nfp_internal_party_mapping()
    if not nfp_mapping.empty and {"circo_key", "nfp_internal_party"}.issubset(nfp_mapping.columns):
        nfp_mapping = nfp_mapping[["circo_key", "source_circo_code", "nfp_party_code", "nfp_internal_party"]].dropna(subset=["circo_key"]).drop_duplicates(subset=["circo_key"])
        candidates = candidates.merge(nfp_mapping, on="circo_key", how="left")
        candidates["force_label"] = candidates["nfp_internal_party"].where(
            candidates["nuance"].astype(str).str.upper().eq("UG") & candidates["nfp_internal_party"].notna(),
            candidates["force_label"],
        )
        candidates = _apply_nfp_circo_mapping_to_candidates(candidates)
    else:
        candidates["source_circo_code"] = pd.NA
    candidates["force_label"] = candidates["force_label"].where(
        ~(candidates["nuance"].astype(str).str.upper().eq("UG") & candidates["force_label"].eq("Union de la gauche / NFP")),
        "Autre NFP",
    )
    candidates["force_label"] = candidates.apply(
        lambda row: _normalize_nfp_force_label(row.get("force_label"), row.get("nuance")),
        axis=1,
    )

    candidates["analysis_force_label"] = candidates["analysis_force_label"].fillna(
        candidates.apply(lambda row: _analysis_force_label(row.get("force_label"), row.get("nuance")), axis=1)
    )
    candidates = candidates.drop(columns=["nfp_party_code", "nfp_internal_party"], errors="ignore")

    candidates = candidates.sort_values(["dept_code", "circo_code", "votes", "candidate_rank_panel"], ascending=[True, True, False, True]).reset_index(drop=True)
    candidates["rank_in_circo"] = candidates.groupby(["dept_code", "circo_code"]).cumcount() + 1
    candidates["qualified_by_threshold"] = candidates["share_inscrits"] >= 12.5
    candidates["qualified_for_second_round"] = candidates["qualified_by_threshold"]

    for (_dept_code, _circo_code), group in candidates.groupby(["dept_code", "circo_code"], sort=False):
        elected = bool(group["elected_first_round"].any())
        qualified_count = int(group["qualified_by_threshold"].sum())
        group_index = group.index.tolist()
        if elected:
            candidates.loc[group_index, "qualified_for_second_round"] = False
            continue
        if qualified_count < 2:
            top_two = group.sort_values(["votes", "candidate_rank_panel"], ascending=[False, True]).head(2).index.tolist()
            candidates.loc[group_index, "qualified_for_second_round"] = False
            candidates.loc[top_two, "qualified_for_second_round"] = True

    maintained = pd.DataFrame()
    if not second_round_candidates.empty:
        maintained = second_round_candidates.copy()
        maintained["Code département"] = maintained["Code département"].map(_format_department_code)
        maintained["Code circonscription"] = maintained["Code circonscription"].map(_format_circo_code)
        maintained["candidate_key"] = maintained.apply(
            lambda row: _normalize_person_key(row.get("Prénom du candidat"), row.get("Nom du candidat")),
            axis=1,
        )
        maintained["nuance"] = maintained["Code nuance"].fillna("").astype(str).str.upper()
        maintained["force_label"] = maintained["nuance"].map(_force_label_from_nuance)
        maintained["analysis_force_label"] = maintained.apply(
            lambda row: _analysis_force_label(row.get("force_label"), row.get("nuance")),
            axis=1,
        )
        maintained["circo_key"] = maintained.apply(
            lambda row: f"{_format_department_code(row['Code département'])}-{_format_circo_code(row['Code circonscription'])}"
            if pd.notna(row.get("Code département")) and pd.notna(row.get("Code circonscription"))
            else "",
            axis=1,
        )
        maintained = maintained.rename(
            columns={
                "Code département": "dept_code",
                "Département": "dept_label",
                "Code circonscription": "circo_code",
                "Libellé circonscription": "circo_label",
                "Nom du candidat": "candidate_last_name",
                "Prénom du candidat": "candidate_first_name",
            }
        )
        maintained["candidate_name"] = (
            maintained["candidate_first_name"].fillna("").astype(str).str.strip()
            + " "
            + maintained["candidate_last_name"].fillna("").astype(str).str.strip()
        ).str.strip()
        second_round_detailed = _build_official_candidate_results_by_circo("2024_legi_t2")
        if not second_round_detailed.empty:
            maintained = maintained.merge(
                second_round_detailed[
                    [
                        "circo_key",
                        "candidate_key",
                        "force_label_detailed",
                        "analysis_force_label",
                    ]
                ].drop_duplicates(subset=["circo_key", "candidate_key"]),
                on=["circo_key", "candidate_key"],
                how="left",
            )
            maintained["force_label"] = maintained["force_label_detailed"].fillna(maintained["force_label"])
            maintained["analysis_force_label"] = maintained["analysis_force_label_y"].fillna(maintained["analysis_force_label_x"])
            maintained = maintained.drop(columns=["analysis_force_label_x", "analysis_force_label_y"], errors="ignore")
        nfp_mapping = _load_nfp_internal_party_mapping()
        if not nfp_mapping.empty and {"circo_key", "nfp_internal_party"}.issubset(nfp_mapping.columns):
            nfp_mapping = nfp_mapping[["circo_key", "source_circo_code", "nfp_party_code", "nfp_internal_party"]].dropna(subset=["circo_key"]).drop_duplicates(subset=["circo_key"])
            maintained = maintained.merge(nfp_mapping, on="circo_key", how="left")
            maintained["force_label"] = maintained["nfp_internal_party"].where(
                maintained["nuance"].astype(str).str.upper().eq("UG") & maintained["nfp_internal_party"].notna(),
                maintained["force_label"],
            )
            maintained["analysis_force_label"] = maintained["force_label"]
            maintained = _apply_nfp_circo_mapping_to_candidates(maintained)
            maintained = maintained.drop(columns=["nfp_internal_party", "nfp_party_code"], errors="ignore")
        maintained["force_label"] = maintained["force_label"].where(
            ~(maintained["nuance"].astype(str).str.upper().eq("UG") & maintained["force_label"].eq("Union de la gauche / NFP")),
            "Autre NFP",
        )
        maintained["force_label"] = maintained.apply(
            lambda row: _normalize_nfp_force_label(row.get("force_label"), row.get("nuance")),
            axis=1,
        )
        maintained["analysis_force_label"] = maintained["force_label"]
        maintained = maintained.loc[maintained["dept_code"].notna() & maintained["circo_code"].notna() & maintained["candidate_key"].ne("")].copy()
        maintained = maintained[
            [
                "dept_code",
                "dept_label",
                "circo_code",
                "circo_label",
                "circo_key",
                "candidate_name",
                "candidate_key",
                "nuance",
                "force_label",
                "analysis_force_label",
            ]
        ].drop_duplicates()

    maintained_keys: set[tuple[str, str, str]] = set()
    if not maintained.empty:
        maintained_keys = {
            (_format_department_code(row.dept_code), _format_circo_code(row.circo_code), str(row.candidate_key))
            for row in maintained.itertuples(index=False)
        }
    candidates["maintained_second_round"] = candidates.apply(
        lambda row: (_format_department_code(row["dept_code"]), _format_circo_code(row["circo_code"]), str(row["candidate_key"])) in maintained_keys,
        axis=1,
    )
    candidates["withdrawn_after_qualification"] = candidates["qualified_for_second_round"] & (~candidates["maintained_second_round"])

    summary_rows: list[dict[str, object]] = []
    for (dept_code, circo_code), group in candidates.groupby(["dept_code", "circo_code"], sort=False):
        group = group.sort_values(["votes", "candidate_rank_panel"], ascending=[False, True]).reset_index(drop=True)
        leader = group.iloc[0]
        maintained_group = group.loc[group["maintained_second_round"]].copy()
        qualified_group = group.loc[group["qualified_for_second_round"]].copy()
        withdrawn_group = group.loc[group["withdrawn_after_qualification"]].copy()
        elected = bool(group["elected_first_round"].any())
        maintained_count = int(len(maintained_group))
        if elected:
            configuration = "Élu au 1er tour"
        elif maintained_count == 0:
            configuration = "Données T2 manquantes"
        elif maintained_count == 2:
            configuration = "Duel"
        elif maintained_count == 3:
            configuration = "Triangulaire"
        else:
            configuration = "Autre configuration"
        summary_rows.append(
            {
                "source_circo_code": str(group["source_circo_code"].dropna().iloc[0]).strip() if "source_circo_code" in group.columns and group["source_circo_code"].notna().any() else str(leader["circo_key"]),
                "dept_code": _format_department_code(dept_code),
                "dept_label": str(leader["dept_label"]),
                "circo_code": _format_circo_code(circo_code),
                "circo_label": str(leader["circo_label"]),
                "circo_key": str(leader["circo_key"]),
                "circo_full_label": f"{leader['dept_label']} · {leader['circo_label']}",
                "inscrits": float(leader["inscrits"]),
                "exprimes": float(leader["exprimes"]),
                "leader_name": str(leader["candidate_name"]),
                "leader_force": str(leader["analysis_force_label"]),
                "leader_nuance": str(leader["nuance"]),
                "leader_share_exprimes": float(leader["share_exprimes"]),
                "leader_share_inscrits": float(leader["share_inscrits"]),
                "elected_first_round": elected,
                "qualified_count": int(len(qualified_group)),
                "maintained_count": maintained_count,
                "withdrawn_count": int(len(withdrawn_group)),
                "configuration_t2": configuration,
                "qualified_forces": " · ".join(qualified_group["analysis_force_label"].tolist()),
                "maintained_forces": " · ".join(maintained_group["analysis_force_label"].tolist()),
                "withdrawn_forces": " · ".join(withdrawn_group["analysis_force_label"].tolist()),
                "maintained_names": " · ".join(maintained_group["candidate_name"].tolist()),
                "withdrawn_names": " · ".join(withdrawn_group["candidate_name"].tolist()),
                "duel_or_triangular_type": " · ".join(sorted(maintained_group["analysis_force_label"].tolist())) if not maintained_group.empty else "Élu au 1er tour",
            }
        )
    summary = pd.DataFrame(summary_rows).sort_values(["dept_code", "circo_code"]).reset_index(drop=True)
    second_round_final = _build_official_second_round_final_results()
    if not second_round_final.empty:
        winners = (
            second_round_final.loc[second_round_final["rank_t2"] == 1, ["circo_key", "candidate_name", "analysis_force_label", "share_exprimes_t2"]]
            .rename(
                columns={
                    "candidate_name": "winner_name_t2",
                    "analysis_force_label": "winner_force_t2",
                    "share_exprimes_t2": "winner_share_t2",
                }
            )
        )
        runners_up = (
            second_round_final.loc[second_round_final["rank_t2"] == 2, ["circo_key", "candidate_name", "analysis_force_label", "share_exprimes_t2"]]
            .rename(
                columns={
                    "candidate_name": "runner_up_name_t2",
                    "analysis_force_label": "runner_up_force_t2",
                    "share_exprimes_t2": "runner_up_share_t2",
                }
            )
        )
        summary = summary.merge(winners, on="circo_key", how="left").merge(runners_up, on="circo_key", how="left")
    else:
        summary["winner_name_t2"] = pd.NA
        summary["winner_force_t2"] = pd.NA
        summary["winner_share_t2"] = pd.NA
        summary["runner_up_name_t2"] = pd.NA
        summary["runner_up_force_t2"] = pd.NA
        summary["runner_up_share_t2"] = pd.NA
    return summary, candidates, maintained


def _extract_percentages(text: str) -> list[float]:
    return [float(match.replace(",", ".")) for match in re.findall(r"(\d+(?:,\d+)?)\s*%", str(text))]


def _extract_party_tokens(lines: list[str], expected_count: int) -> list[str]:
    tokens: list[str] = []
    for line in lines:
        for raw_token in re.split(r"\s+", str(line).replace("(", " ").replace(")", " ")):
            token = raw_token.strip(" ,.;:[]")
            if not token:
                continue
            if token in {"Premier", "tour", "Second", "Sondeur", "Date", "Échantillon"}:
                continue
            if token.lower() == token and not any(character.isupper() for character in token):
                continue
            if token in {"Ensemble"}:
                continue
            tokens.append(token)
    if expected_count <= 0:
        return tokens
    return tokens[:expected_count]


def _token_to_bloc(token: str) -> str:
    cleaned = token.strip().replace(".", "")
    if cleaned in TOKEN_BLOC_MAP:
        return TOKEN_BLOC_MAP[cleaned]
    if cleaned.startswith("LFI"):
        return "gauche"
    if cleaned.startswith("DIV"):
        return "autres"
    return "autres"


def _aggregate_to_blocs(party_tokens: list[str], percentages: list[float]) -> dict[str, float]:
    aggregates = {bloc: 0.0 for bloc in FIVE_BLOC_ORDER}
    for token, percentage in zip(party_tokens, percentages):
        aggregates[_token_to_bloc(token)] += float(percentage)
    return aggregates


def _department_from_constituency(constituency_name: str) -> str:
    match = re.search(r"circonscription\s+(?:du|de la|de l'|des)\s+(.+)$", constituency_name, flags=re.IGNORECASE)
    if match is None:
        return constituency_name
    return match.group(1).strip().replace("Maritimes", "Maritimes")


def _normalize_search_text(value: object) -> str:
    text = str(value).lower()
    replacements = {
        "é": "e",
        "è": "e",
        "ê": "e",
        "ë": "e",
        "à": "a",
        "â": "a",
        "ä": "a",
        "î": "i",
        "ï": "i",
        "ô": "o",
        "ö": "o",
        "ù": "u",
        "û": "u",
        "ü": "u",
        "ç": "c",
        "œ": "oe",
        "’": "'",
    }
    for source, target in replacements.items():
        text = text.replace(source, target)
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return " ".join(text.split())


def _build_constituency_search_blob(row: pd.Series) -> str:
    constituency_name = str(row["constituency_name"])
    aliases = LOCAL_SEARCH_ALIASES.get(constituency_name, [])
    circo_number_match = re.match(r"^(\d+)(?:re|e)\s+circonscription", constituency_name, flags=re.IGNORECASE)
    circo_number = circo_number_match.group(1) if circo_number_match is not None else ""
    raw_parts = [
        constituency_name,
        row.get("department_name", ""),
        row.get("winning_label", ""),
        row.get("local_source_note", ""),
        circo_number,
        "circo",
        "circonscription",
        *aliases,
    ]
    return _normalize_search_text(" ".join(str(part) for part in raw_parts if str(part).strip()))


def _filter_constituencies(local_frame: pd.DataFrame, query: str) -> pd.DataFrame:
    working = local_frame.copy()
    if "search_blob" not in working.columns:
        working["search_blob"] = working.apply(_build_constituency_search_blob, axis=1)
    normalized_query = _normalize_search_text(query)
    if not normalized_query:
        return working
    tokens = normalized_query.split()
    mask = working["search_blob"].map(lambda blob: all(token in blob for token in tokens))
    return working.loc[mask].copy()


def _build_official_search_blob(row: pd.Series) -> str:
    parts = [
        row.get("id_election", ""),
        row.get("libelle_departement", ""),
        row.get("libelle_commune", ""),
        row.get("libelle_circonscription", ""),
        row.get("code_departement", ""),
        row.get("code_commune", ""),
        row.get("code_circonscription", ""),
        row.get("code_bv", ""),
    ]
    return _normalize_search_text(" ".join(str(part) for part in parts if str(part).strip()))


def _build_official_constituency_results(official: pd.DataFrame) -> pd.DataFrame:
    if official.empty:
        return pd.DataFrame()

    has_circo = "code_circonscription" in official.columns and official["code_circonscription"].notna().any()
    if has_circo:
        working = official.loc[official["code_circonscription"].notna()].copy()
        group_keys = [
            "id_election",
            "code_departement",
            "libelle_departement",
            "code_circonscription",
            "libelle_circonscription",
        ]
        aggregation_level = "circonscription"
    else:
        working = official.loc[official["code_commune"].notna()].copy()
        if working.empty:
            working = official.copy()
        group_keys = [
            "id_election",
            "code_departement",
            "libelle_departement",
            "code_commune",
            "libelle_commune",
        ]
        aggregation_level = "commune"

    aggregate_columns = [
        "inscrits",
        "abstentions",
        "votants",
        "blancs",
        "nuls",
        "exprimes",
    ]
    existing_aggregate_columns = [column for column in aggregate_columns if column in working.columns]
    if not existing_aggregate_columns:
        return pd.DataFrame()

    grouped = (
        working.groupby(group_keys, dropna=False)[existing_aggregate_columns]
        .sum()
        .reset_index()
    )
    grouped["participation"] = grouped["votants"] / grouped["inscrits"] * 100.0
    grouped["abstention"] = grouped["abstentions"] / grouped["inscrits"] * 100.0
    grouped["expression"] = grouped["exprimes"] / grouped["votants"] * 100.0
    grouped["search_blob"] = grouped.apply(_build_official_search_blob, axis=1)
    grouped["aggregation_level"] = aggregation_level
    return grouped.sort_values(
        [
            column
            for column in ["id_election", "code_departement", "code_circonscription", "code_commune"]
            if column in grouped.columns
        ],
        na_position="last",
    ).reset_index(drop=True)


def _build_circo_force_analysis_table(candidates: pd.DataFrame, summary: pd.DataFrame) -> pd.DataFrame:
    if candidates.empty:
        return pd.DataFrame()
    grouped = (
        candidates.groupby(["circo_key", "analysis_force_label"], dropna=False)
        .agg(
            source_circo_code=("source_circo_code", "first"),
            circo_label=("circo_label", "first"),
            dept_label=("dept_label", "first"),
            nb_candidats=("candidate_key", lambda values: int(pd.Series(values).ne("").sum())),
            meilleur_score_t1=("share_exprimes", "max"),
            meilleur_score_inscrits_t1=("share_inscrits", "max"),
            est_qualifie=("qualified_for_second_round", lambda values: bool(pd.Series(values).astype(bool).any())),
            est_maintenu=("maintained_second_round", lambda values: bool(pd.Series(values).astype(bool).any())),
            est_retire=("withdrawn_after_qualification", lambda values: bool(pd.Series(values).astype(bool).any())),
            est_tete_t1=("rank_in_circo", lambda values: bool((pd.Series(values) == 1).any())),
            est_elu_t1=("elected_first_round", lambda values: bool(pd.Series(values).astype(bool).any())),
            meilleur_candidat=("candidate_name", "first"),
        )
        .reset_index()
    )
    if not summary.empty:
        grouped = grouped.merge(
            summary[
                [
                    "circo_key",
                    "source_circo_code",
                    "configuration_t2",
                    "maintained_forces",
                    "withdrawn_forces",
                    "qualified_forces",
                    "winner_force_t2",
                    "winner_name_t2",
                ]
            ],
            on="circo_key",
            how="left",
            suffixes=("", "_summary"),
        )
        if "source_circo_code_summary" in grouped.columns:
            grouped["source_circo_code"] = grouped["source_circo_code"].fillna(grouped["source_circo_code_summary"])
            grouped = grouped.drop(columns=["source_circo_code_summary"], errors="ignore")
    grouped["source_circo_code"] = grouped["source_circo_code"].fillna(grouped["circo_key"])
    grouped["coalition_label"] = grouped["analysis_force_label"].map(_force_to_coalition_label)
    grouped["bloc_label"] = grouped["analysis_force_label"].map(_force_to_bloc_label)
    return grouped.sort_values(["source_circo_code", "analysis_force_label"], ascending=[True, True]).reset_index(drop=True)


def _build_second_round_case_matrices(summary: pd.DataFrame, candidates: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    if summary.empty:
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()
    duel_cases = (
        summary.loc[summary["configuration_t2"] == "Duel", ["source_circo_code", "duel_or_triangular_type", "maintained_forces", "withdrawn_forces", "winner_force_t2"]]
        .groupby(["duel_or_triangular_type", "withdrawn_forces", "winner_force_t2"], dropna=False)
        .size()
        .rename("nombre_de_cas")
        .reset_index()
        .sort_values(["nombre_de_cas", "duel_or_triangular_type"], ascending=[False, True])
    )
    tri_cases = (
        summary.loc[summary["configuration_t2"] == "Triangulaire", ["source_circo_code", "duel_or_triangular_type", "maintained_forces", "withdrawn_forces", "winner_force_t2"]]
        .groupby(["duel_or_triangular_type", "winner_force_t2"], dropna=False)
        .size()
        .rename("nombre_de_cas")
        .reset_index()
        .sort_values(["nombre_de_cas", "duel_or_triangular_type"], ascending=[False, True])
    )
    withdrawal_matrix = pd.DataFrame()
    if not candidates.empty:
        withdrawal_rows = candidates.loc[candidates["withdrawn_after_qualification"]].copy()
        if not withdrawal_rows.empty:
            withdrawal_rows = withdrawal_rows.merge(
                summary[["circo_key", "source_circo_code", "configuration_t2", "maintained_forces", "duel_or_triangular_type"]],
                on="circo_key",
                how="left",
            )
            withdrawal_matrix = (
                withdrawal_rows.groupby(["analysis_force_label", "configuration_t2", "maintained_forces"], dropna=False)
                .size()
                .rename("nombre_de_retraits")
                .reset_index()
                .sort_values(["nombre_de_retraits", "analysis_force_label"], ascending=[False, True])
            )
    return duel_cases, tri_cases, withdrawal_matrix


def _split_force_list(value: object) -> list[str]:
    if pd.isna(value):
        return []
    return [part.strip() for part in str(value).split("·") if part and part.strip()]


def _build_2027_first_round_projection(
    candidates: pd.DataFrame,
    summary: pd.DataFrame,
    label_builder,
) -> pd.DataFrame:
    if candidates.empty or summary.empty:
        return pd.DataFrame()

    working = candidates.copy()
    working["projection_label"] = working["analysis_force_label"].map(label_builder)
    working = working.loc[working["projection_label"].notna() & working["projection_label"].astype(str).ne("")].copy()
    if working.empty:
        return pd.DataFrame()

    total_circos = max(int(summary["circo_key"].nunique()), 1)
    total_exprimes = pd.to_numeric(
        working.groupby("circo_key", dropna=False)["exprimes"].first(),
        errors="coerce",
    ).fillna(0.0).sum()
    if total_exprimes <= 0:
        return pd.DataFrame()
    per_force_circo = (
        working.groupby(["projection_label", "circo_key"], dropna=False)
        .agg(
            source_circo_code=("source_circo_code", "first"),
            voix_force=("votes", "sum"),
            exprimes_circo=("exprimes", "first"),
            tete_t1=("rank_in_circo", lambda values: int((pd.Series(values) == 1).any())),
            qualifie_t2=("qualified_for_second_round", lambda values: int(pd.Series(values).astype(bool).any())),
            maintenu_t2=("maintained_second_round", lambda values: int(pd.Series(values).astype(bool).any())),
            retire_t2=("withdrawn_after_qualification", lambda values: int(pd.Series(values).astype(bool).any())),
        )
        .reset_index()
    )

    projection = (
        per_force_circo.groupby("projection_label", dropna=False)
        .agg(
            circonscriptions_presentes=("circo_key", "nunique"),
            voix_t1=("voix_force", "sum"),
            exprimes_sur_presence=("exprimes_circo", "sum"),
            tetes_t1=("tete_t1", "sum"),
            qualifies_t2=("qualifie_t2", "sum"),
            maintiens_t2=("maintenu_t2", "sum"),
            retraits_t2=("retire_t2", "sum"),
        )
        .reset_index()
        .rename(columns={"projection_label": "Force"})
    )
    projection["part_nationale_brute_t1"] = projection["voix_t1"] / float(total_exprimes) * 100.0
    projection["taux_couverture"] = projection["circonscriptions_presentes"] / float(total_circos) * 100.0
    projection["score_moyen_sur_circos_presentes"] = (
        projection["voix_t1"] / projection["exprimes_sur_presence"].where(projection["exprimes_sur_presence"] > 0, pd.NA) * 100.0
    ).fillna(0.0)
    projection["taux_tete_t1"] = (
        projection["tetes_t1"] / projection["circonscriptions_presentes"].where(projection["circonscriptions_presentes"] > 0, pd.NA) * 100.0
    ).fillna(0.0)
    projection["taux_qualification_t2"] = (
        projection["qualifies_t2"] / projection["circonscriptions_presentes"].where(projection["circonscriptions_presentes"] > 0, pd.NA) * 100.0
    ).fillna(0.0)
    projection["taux_maintien_parmi_qualifies"] = (
        projection["maintiens_t2"] / projection["qualifies_t2"].where(projection["qualifies_t2"] > 0, pd.NA) * 100.0
    ).fillna(0.0)
    projection["taux_retrait_parmi_qualifies"] = (
        projection["retraits_t2"] / projection["qualifies_t2"].where(projection["qualifies_t2"] > 0, pd.NA) * 100.0
    ).fillna(0.0)

    # Le vrai point de départ du T1 2027 est la couverture :
    # une force qui n'est présente que dans peu de circonscriptions ne peut pas être lue
    # comme si son score local moyen valait partout. On construit donc d'abord un score
    # national couvert, puis seulement ensuite on applique les correctifs de dynamique.
    projection["facteur_couverture_2027"] = (
        projection["circonscriptions_presentes"] / float(total_circos)
    ).clip(lower=0.01, upper=1.0).fillna(0.0)
    projection["score_national_couvert_t1"] = (
        projection["score_moyen_sur_circos_presentes"] * projection["facteur_couverture_2027"]
    ).fillna(0.0)
    projection["presence_nationalisee_t1"] = (
        projection["score_national_couvert_t1"]
    ).fillna(0.0)
    max_presence_nationalisee = float(projection["presence_nationalisee_t1"].max()) if not projection.empty else 0.0
    if max_presence_nationalisee > 0:
        projection["indice_presence_relative_2027"] = (
            projection["presence_nationalisee_t1"] / max_presence_nationalisee
        ).clip(lower=0.05, upper=1.0).fillna(0.0)
    else:
        projection["indice_presence_relative_2027"] = 0.0
    projection["facteur_representativite_2027"] = (
        0.55 * projection["facteur_couverture_2027"]
        + 0.45 * projection["indice_presence_relative_2027"]
    ).clip(lower=0.05, upper=1.0).fillna(0.0)
    projection["coefficient_dynamique_2027"] = (
        0.85
        + 0.15
        * (
            0.50 * (projection["taux_tete_t1"] / 100.0)
            + 0.30 * (projection["taux_qualification_t2"] / 100.0)
            + 0.20 * (projection["taux_maintien_parmi_qualifies"] / 100.0)
        )
    ).clip(lower=0.85, upper=1.0).fillna(0.0)
    projection["indice_corrige_2027_t1"] = (
        projection["presence_nationalisee_t1"]
        * projection["facteur_representativite_2027"]
        * projection["coefficient_dynamique_2027"]
    ).fillna(0.0)
    total_index = float(projection["indice_corrige_2027_t1"].sum())
    if total_index > 0:
        projection["socle_projete_2027_t1"] = projection["indice_corrige_2027_t1"] / total_index * 100.0
    else:
        projection["socle_projete_2027_t1"] = 0.0
    projection["Bloc"] = projection["Force"].map(_force_to_bloc_label)
    projection["Coalition"] = projection["Force"].map(_force_to_coalition_label)
    projection["Niveau"] = projection["Force"].map(_projection_level_label)
    return projection.sort_values("socle_projete_2027_t1", ascending=False).reset_index(drop=True)


def _build_2027_first_round_force_projection(candidates: pd.DataFrame, summary: pd.DataFrame) -> pd.DataFrame:
    force_projection = _build_2027_first_round_projection(candidates, summary, lambda value: str(value or "").strip())
    if force_projection.empty:
        return force_projection
    working = force_projection.loc[force_projection["Force"].map(_is_presidential_first_round_force)].copy()
    if working.empty:
        return working

    # La lecture ici doit rester stable et intelligible :
    # on garde les mêmes forces et les mêmes couleurs, mais le socle est d'abord
    # le poids national brut observé au T1 2024. La couverture reste informative,
    # pas un moteur qui déforme le classement.
    working["penalite_couverture_presidentielle_2027"] = working["facteur_couverture_2027"].clip(lower=0.0, upper=1.0).fillna(0.0)
    working["correctif_representation_force_2027"] = 1.0
    working["indice_force_presidentielle_2027"] = (
        working["part_nationale_brute_t1"]
        * working["coefficient_dynamique_2027"]
    ).fillna(0.0)
    total_index = float(working["indice_force_presidentielle_2027"].sum())
    if total_index > 0:
        working["socle_projete_2027_t1"] = working["indice_force_presidentielle_2027"] / total_index * 100.0
    else:
        working["socle_projete_2027_t1"] = 0.0
    return working.sort_values("socle_projete_2027_t1", ascending=False).reset_index(drop=True)


def _build_2027_first_round_coalition_projection(candidates: pd.DataFrame, summary: pd.DataFrame) -> pd.DataFrame:
    return _build_2027_first_round_projection(candidates, summary, _force_to_coalition_label)


def _build_2027_first_round_bloc_projection(candidates: pd.DataFrame, summary: pd.DataFrame) -> pd.DataFrame:
    return _build_2027_first_round_projection(candidates, summary, _force_to_bloc_label)


def _build_withdrawal_and_runoff_analysis(
    summary: pd.DataFrame,
    candidates: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    if summary.empty or candidates.empty:
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

    withdrawal_rows = candidates.loc[candidates["withdrawn_after_qualification"]].copy()
    if withdrawal_rows.empty:
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

    merged = withdrawal_rows.merge(
        summary[
            [
                "circo_key",
                "source_circo_code",
                "configuration_t2",
                "maintained_forces",
                "withdrawn_forces",
                "winner_force_t2",
                "runner_up_force_t2",
                "leader_force",
            ]
        ],
        on="circo_key",
        how="left",
        suffixes=("", "_summary"),
    )
    if "source_circo_code_summary" in merged.columns:
        merged["source_circo_code"] = merged["source_circo_code"].fillna(merged["source_circo_code_summary"])
    merged["source_circo_code"] = merged["source_circo_code"].fillna(merged["circo_key"])
    merged["force_retirée"] = merged["analysis_force_label"]
    merged["force_battue_t2"] = merged["runner_up_force_t2"]
    merged["force_gagnante_t2"] = merged["winner_force_t2"]
    merged = merged.loc[merged["force_gagnante_t2"].notna() & merged["force_battue_t2"].notna()].copy()

    withdrawal_target_matrix = (
        merged.groupby(
            ["force_retirée", "configuration_t2", "maintained_forces", "force_gagnante_t2", "force_battue_t2"],
            dropna=False,
        )
        .size()
        .rename("nombre_de_cas")
        .reset_index()
        .sort_values(["nombre_de_cas", "force_retirée"], ascending=[False, True])
    )

    against_rows: list[dict[str, object]] = []
    for row in merged.itertuples(index=False):
        for opponent in _split_force_list(row.maintained_forces):
            if opponent == row.force_retirée:
                continue
            against_rows.append(
                {
                    "force_retirée": row.force_retirée,
                    "force_restée_en_face": opponent,
                    "force_gagnante_t2": row.force_gagnante_t2,
                    "force_battue_t2": row.force_battue_t2,
                }
            )
    against_matrix = pd.DataFrame(against_rows)
    if not against_matrix.empty:
        against_matrix = (
            against_matrix.groupby(
                ["force_retirée", "force_restée_en_face", "force_gagnante_t2", "force_battue_t2"],
                dropna=False,
            )
            .size()
            .rename("nombre_de_cas")
            .reset_index()
            .sort_values(["nombre_de_cas", "force_retirée"], ascending=[False, True])
        )

    anti_target_matrix = pd.DataFrame()
    if not merged.empty:
        anti_target_matrix = (
            merged.groupby(
                ["force_retirée", "force_battue_t2", "force_gagnante_t2", "configuration_t2"],
                dropna=False,
            )
            .size()
            .rename("nombre_de_cas")
            .reset_index()
            .sort_values(["nombre_de_cas", "force_retirée"], ascending=[False, True])
        )

    duel_summary = summary.loc[summary["configuration_t2"] == "Duel"].copy()
    duel_summary = duel_summary.loc[duel_summary["winner_force_t2"].notna() & duel_summary["runner_up_force_t2"].notna()].copy()
    duel_presidential_base = pd.DataFrame()
    if not duel_summary.empty and {"winner_force_t2", "runner_up_force_t2"}.issubset(duel_summary.columns):
        duel_rows: list[dict[str, object]] = []
        for row in duel_summary.itertuples(index=False):
            duel_rows.append(
                {
                    "Force": row.winner_force_t2,
                    "Adversaire": row.runner_up_force_t2,
                    "Issue": "victoire",
                }
            )
            duel_rows.append(
                {
                    "Force": row.runner_up_force_t2,
                    "Adversaire": row.winner_force_t2,
                    "Issue": "défaite",
                }
            )
        duel_frame = pd.DataFrame(duel_rows)
        duel_presidential_base = (
            duel_frame.groupby(["Force", "Adversaire", "Issue"], dropna=False)
            .size()
            .rename("nombre_de_duels")
            .reset_index()
        )
        duel_presidential_base = (
            duel_presidential_base.pivot_table(
                index=["Force", "Adversaire"],
                columns="Issue",
                values="nombre_de_duels",
                fill_value=0,
                aggfunc="sum",
            )
            .reset_index()
        )
        for column in ["victoire", "défaite"]:
            if column not in duel_presidential_base.columns:
                duel_presidential_base[column] = 0
        duel_presidential_base["total_duels"] = duel_presidential_base["victoire"] + duel_presidential_base["défaite"]
        duel_presidential_base["taux_de_victoire"] = (
            duel_presidential_base["victoire"] / duel_presidential_base["total_duels"].where(duel_presidential_base["total_duels"] > 0, pd.NA) * 100.0
        ).fillna(0.0)
        duel_presidential_base = duel_presidential_base.sort_values(
            ["taux_de_victoire", "total_duels"],
            ascending=[False, False],
        ).reset_index(drop=True)

    return withdrawal_target_matrix, against_matrix, anti_target_matrix, duel_presidential_base


def _build_2027_runoff_projection_from_2024(
    first_round_projection: pd.DataFrame,
    anti_target_matrix: pd.DataFrame,
    duel_presidential_base: pd.DataFrame,
) -> pd.DataFrame:
    if first_round_projection.empty:
        return pd.DataFrame()

    projection = first_round_projection.loc[first_round_projection["socle_projete_2027_t1"] > 0].copy()
    if len(projection) < 2:
        return pd.DataFrame()

    projection = projection.sort_values("socle_projete_2027_t1", ascending=False).reset_index(drop=True)
    candidate_pool = projection.loc[projection["Force"].map(_is_runoff_projectable_force)].copy()
    if len(candidate_pool) < 2:
        return pd.DataFrame()
    force_scores = dict(zip(candidate_pool["Force"], candidate_pool["socle_projete_2027_t1"]))
    force_coverage = dict(zip(candidate_pool["Force"], candidate_pool["facteur_couverture_2027"]))
    force_presence = dict(zip(candidate_pool["Force"], candidate_pool["presence_nationalisee_t1"]))
    force_representativity = dict(zip(candidate_pool["Force"], candidate_pool["facteur_representativite_2027"]))

    anti_lookup: dict[str, dict[str, float]] = {}
    if not anti_target_matrix.empty:
        anti_work = anti_target_matrix.copy()
        totals = anti_work.groupby("force_retirée", dropna=False)["nombre_de_cas"].sum().to_dict()
        for row in anti_work.itertuples(index=False):
            source_force = str(row.force_retirée)
            target_force = str(row.force_battue_t2)
            total = float(totals.get(source_force, 0.0))
            if total <= 0:
                continue
            anti_lookup.setdefault(source_force, {})
            anti_lookup[source_force][target_force] = anti_lookup[source_force].get(target_force, 0.0) + float(row.nombre_de_cas) / total

    duel_lookup: dict[tuple[str, str], tuple[float, int]] = {}
    if not duel_presidential_base.empty:
        for row in duel_presidential_base.itertuples(index=False):
            duel_lookup[(str(row.Force), str(row.Adversaire))] = (float(row.taux_de_victoire), int(row.total_duels))

    rows: list[dict[str, object]] = []
    for force_a, force_b in combinations(candidate_pool["Force"].tolist(), 2):
        if _projection_force_display_label(force_a) == _projection_force_display_label(force_b):
            continue
        score_a = float(force_scores.get(force_a, 0.0))
        score_b = float(force_scores.get(force_b, 0.0))
        coverage_a = float(force_coverage.get(force_a, 0.0))
        coverage_b = float(force_coverage.get(force_b, 0.0))
        representativity_a = float(force_representativity.get(force_a, 0.0))
        representativity_b = float(force_representativity.get(force_b, 0.0))
        for source_force, source_score in force_scores.items():
            if source_force in {force_a, force_b}:
                continue
            anti_against_a = float(anti_lookup.get(source_force, {}).get(force_a, 0.0))
            anti_against_b = float(anti_lookup.get(source_force, {}).get(force_b, 0.0))
            anti_total = anti_against_a + anti_against_b
            if anti_total > 0:
                raw_to_a = anti_against_b / anti_total
                raw_to_b = anti_against_a / anti_total
            else:
                raw_to_a = 0.5
                raw_to_b = 0.5

            weighted_to_a = raw_to_a * max(0.5 * coverage_a + 0.5 * representativity_a, 0.05)
            weighted_to_b = raw_to_b * max(0.5 * coverage_b + 0.5 * representativity_b, 0.05)
            weighted_total = weighted_to_a + weighted_to_b
            if weighted_total > 0:
                to_a = float(source_score) * weighted_to_a / weighted_total
                to_b = float(source_score) * weighted_to_b / weighted_total
            else:
                to_a = float(source_score) / 2.0
                to_b = float(source_score) / 2.0
            score_a += to_a
            score_b += to_b

        # Même après les barrages, on garde une correction d'implantation nationale :
        # une force peu couverte ne doit pas convertir mécaniquement tous les reports
        # comme une force très implantée.
        score_a *= 0.25 + 0.35 * max(coverage_a, 0.05) + 0.40 * max(representativity_a, 0.05)
        score_b *= 0.25 + 0.35 * max(coverage_b, 0.05) + 0.40 * max(representativity_b, 0.05)

        total_runoff = score_a + score_b
        if total_runoff > 0:
            runoff_a = score_a / total_runoff * 100.0
            runoff_b = score_b / total_runoff * 100.0
        else:
            runoff_a = 0.0
            runoff_b = 0.0

        observed_a, observed_duels = duel_lookup.get((force_a, force_b), (pd.NA, 0))
        observed_b, observed_duels_b = duel_lookup.get((force_b, force_a), (pd.NA, 0))
        direct_duels = max(int(observed_duels), int(observed_duels_b))
        if pd.notna(observed_a):
            observed_runoff_a = float(observed_a)
        elif pd.notna(observed_b):
            observed_runoff_a = 100.0 - float(observed_b)
        else:
            observed_runoff_a = pd.NA

        if pd.notna(observed_runoff_a):
            historical_weight = min(direct_duels, 12) / 24.0
            final_a = (1.0 - historical_weight) * runoff_a + historical_weight * float(observed_runoff_a)
        else:
            historical_weight = 0.0
            final_a = runoff_a
        final_b = 100.0 - final_a

        rows.append(
            {
                "force_a": force_a,
                "force_b": force_b,
                "duel_label": _duel_display_label(force_a, force_b),
                "socle_t1_a": float(force_scores.get(force_a, 0.0)),
                "socle_t1_b": float(force_scores.get(force_b, 0.0)),
                "presence_nationalisee_a": float(force_presence.get(force_a, 0.0)),
                "presence_nationalisee_b": float(force_presence.get(force_b, 0.0)),
                "facteur_couverture_a": coverage_a,
                "facteur_couverture_b": coverage_b,
                "facteur_representativite_a": representativity_a,
                "facteur_representativite_b": representativity_b,
                "score_estime_barrage_a": runoff_a,
                "score_estime_barrage_b": runoff_b,
                "score_final_estime_a": final_a,
                "score_final_estime_b": final_b,
                "gagnant_estime": force_a if final_a >= final_b else force_b,
                "ecart_estime": abs(final_a - final_b),
                "score_historique_duel_a": observed_runoff_a,
                "poids_historique_duel": historical_weight,
                "duels_historiques_directs": direct_duels,
            }
        )

    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows).sort_values(
        ["duels_historiques_directs", "ecart_estime", "score_final_estime_a"],
        ascending=[False, False, False],
    ).reset_index(drop=True)


def _render_official_constituency_results() -> None:
    summary, candidates, maintained = _build_official_2024_circo_force_analysis()
    if not summary.empty and not candidates.empty:
        second_round_final = _build_official_second_round_final_results()
        has_real_second_round_results = (
            not second_round_final.empty
            and "winner_force_t2" in summary.columns
            and summary["winner_force_t2"].notna().any()
        )
        query = st.text_input(
            "Recherche permissive circonscription / département / numéro / force / candidat",
            key="analysis_2024_force_circo_query",
            placeholder="Exemples : aisne, 203, 3e, nord, 10e, rn, ensemble, gauche, retrait",
        )
        filtered = summary.copy()
        filtered["leader_coalition"] = filtered["leader_force"].map(_force_to_coalition_label)
        filtered["leader_bloc"] = filtered["leader_force"].map(_force_to_bloc_label)
        filtered["winner_coalition_t2"] = filtered["winner_force_t2"].map(_force_to_coalition_label)
        filtered["winner_bloc_t2"] = filtered["winner_force_t2"].map(_force_to_bloc_label)
        filtered["search_blob"] = (
            filtered["source_circo_code"].astype(str)
            + " "
            + filtered["circo_full_label"].astype(str)
            + " "
            + filtered["dept_code"].astype(str)
            + " "
            + filtered["dept_label"].astype(str)
            + " "
            + filtered["circo_code"].astype(str)
            + " "
            + filtered["circo_label"].astype(str)
            + " "
            + filtered["leader_name"].astype(str)
            + " "
            + filtered["leader_force"].astype(str)
            + " "
            + filtered["maintained_forces"].astype(str)
            + " "
            + filtered["withdrawn_forces"].astype(str)
        ).map(_normalize_search_text)
        normalized_query = _normalize_search_text(query)
        if normalized_query:
            tokens = normalized_query.split()
            filtered = filtered.loc[
                filtered["search_blob"].map(lambda blob: all(token in blob for token in tokens))
            ].copy()

        configuration_options = ["Toutes"] + sorted(filtered["configuration_t2"].dropna().astype(str).unique().tolist())
        force_options = ["Toutes"] + sorted(
            {
                force
                for value in filtered["duel_or_triangular_type"].dropna().astype(str)
                for force in [part.strip() for part in value.split("·")]
                if force and force != "Élu au 1er tour"
            }
        )
        c1, c2 = st.columns(2)
        selected_configuration = c1.selectbox(
            "Configuration du second tour",
            configuration_options,
            key="analysis_2024_force_circo_configuration",
        )
        selected_force = c2.selectbox(
            "Force présente au second tour",
            force_options,
            key="analysis_2024_force_circo_force",
        )
        if selected_configuration != "Toutes":
            filtered = filtered.loc[filtered["configuration_t2"] == selected_configuration].copy()
        if selected_force != "Toutes":
            filtered = filtered.loc[filtered["duel_or_triangular_type"].str.contains(selected_force, na=False)].copy()

        total_candidates_t1 = int(candidates["candidate_key"].ne("").sum())
        total_candidates_t2 = int(maintained["candidate_key"].ne("").sum()) if not maintained.empty else 0
        col1, col2, col3, col4, col5 = st.columns(5)
        col1.metric("Circonscriptions", int(len(filtered)))
        col2.metric("Candidats T1", total_candidates_t1)
        col3.metric("Candidats T2", total_candidates_t2)
        col4.metric("Élus au 1er tour", int(filtered["elected_first_round"].sum()))
        col5.metric("Désistements qualifiés", int(filtered["withdrawn_count"].sum()))

        st.markdown("**Vue exhaustive des circonscriptions**")
        st.dataframe(
            filtered[
                [
                    "source_circo_code",
                    "circo_full_label",
                    "leader_force",
                    "leader_coalition",
                    "leader_bloc",
                    "leader_name",
                    "leader_share_exprimes",
                    "configuration_t2",
                    "qualified_forces",
                    "maintained_forces",
                    "withdrawn_forces",
                    "winner_force_t2",
                    "winner_coalition_t2",
                    "winner_bloc_t2",
                    "winner_name_t2",
                    "winner_share_t2",
                ]
            ].rename(
                columns={
                    "source_circo_code": "Code circonscription",
                    "circo_full_label": "Circonscription",
                    "leader_force": "Force en tête T1",
                    "leader_coalition": "Coalition en tête T1",
                    "leader_bloc": "Bloc en tête T1",
                    "leader_name": "Candidat en tête T1",
                    "leader_share_exprimes": "% du 1er au T1",
                    "configuration_t2": "Configuration T2",
                    "qualified_forces": "Forces qualifiées",
                    "maintained_forces": "Forces maintenues",
                    "withdrawn_forces": "Forces retirées",
                    "winner_force_t2": "Force gagnante T2",
                    "winner_coalition_t2": "Coalition gagnante T2",
                    "winner_bloc_t2": "Bloc gagnant T2",
                    "winner_name_t2": "Candidat gagnant T2",
                    "winner_share_t2": "% gagnant T2",
                }
            ),
            width="stretch",
            hide_index=True,
            column_config={
                "% du 1er au T1": st.column_config.NumberColumn("% du 1er au T1", format="%.2f %%"),
                "% gagnant T2": st.column_config.NumberColumn("% gagnant T2", format="%.2f %%"),
            },
        )

        force_stats_base = (
            candidates.groupby(["analysis_force_label", "circo_key"], dropna=False)
            .agg(
                a_un_candidat_t1=("candidate_key", lambda values: int(pd.Series(values).ne("").any())),
                est_qualifie_t2=("qualified_for_second_round", lambda values: int(pd.Series(values).astype(bool).any())),
                est_maintenu_t2=("maintained_second_round", lambda values: int(pd.Series(values).astype(bool).any())),
                est_retire_t2=("withdrawn_after_qualification", lambda values: int(pd.Series(values).astype(bool).any())),
                est_tete_t1=("rank_in_circo", lambda values: int((pd.Series(values) == 1).any())),
                est_elu_t1=("elected_first_round", lambda values: int(pd.Series(values).astype(bool).any())),
            )
            .reset_index()
        )
        force_stats = (
            force_stats_base.groupby("analysis_force_label", dropna=False)
            .agg(
                circonscriptions_t1=("a_un_candidat_t1", "sum"),
                qualifies_t2=("est_qualifie_t2", "sum"),
                maintiens_t2=("est_maintenu_t2", "sum"),
                retraits_t2=("est_retire_t2", "sum"),
                tetes_t1=("est_tete_t1", "sum"),
                elus_t1=("est_elu_t1", "sum"),
            )
            .reset_index()
            .rename(columns={"analysis_force_label": "Force"})
            .sort_values("circonscriptions_t1", ascending=False)
        )
        force_stats["Coalition"] = force_stats["Force"].map(_force_to_coalition_label)
        force_stats["Bloc"] = force_stats["Force"].map(_force_to_bloc_label)
        if has_real_second_round_results:
            winners_t2 = (
                second_round_final.loc[second_round_final["rank_t2"] == 1]
                .groupby("analysis_force_label", dropna=False)["circo_key"]
                .nunique()
                .rename("victoires_t2")
                .reset_index()
                .rename(columns={"analysis_force_label": "Force"})
            )
            finalistes_t2 = (
                second_round_final.groupby("analysis_force_label", dropna=False)["circo_key"]
                .nunique()
                .rename("candidats_resultat_t2")
                .reset_index()
                .rename(columns={"analysis_force_label": "Force"})
            )
            force_stats = force_stats.merge(finalistes_t2, on="Force", how="left").merge(winners_t2, on="Force", how="left")
        if "candidats_resultat_t2" not in force_stats.columns:
            force_stats["candidats_resultat_t2"] = 0
        if "victoires_t2" not in force_stats.columns:
            force_stats["victoires_t2"] = 0
        force_stats["candidats_resultat_t2"] = pd.to_numeric(force_stats["candidats_resultat_t2"], errors="coerce").fillna(0).astype(int)
        force_stats["victoires_t2"] = pd.to_numeric(force_stats["victoires_t2"], errors="coerce").fillna(0).astype(int)
        force_stats["est_famille_generique"] = force_stats["Force"].map(_is_generic_official_family_label)
        display_force_stats = force_stats.loc[~force_stats["est_famille_generique"]].copy()
        residual_family_stats = force_stats.loc[force_stats["est_famille_generique"]].copy()

        circo_force_analysis = _build_circo_force_analysis_table(candidates, summary)
        duel_matrix, tri_matrix, withdrawal_matrix = _build_second_round_case_matrices(summary, candidates)
        first_round_projection_2027 = _build_2027_first_round_force_projection(candidates, summary)
        withdrawal_target_matrix, against_matrix, anti_target_matrix, duel_presidential_base = _build_withdrawal_and_runoff_analysis(summary, candidates)
        descriptive_force_base = force_stats.copy()
        descriptive_force_base = descriptive_force_base.loc[descriptive_force_base["circonscriptions_t1"] > 0].copy()
        descriptive_force_base["part_tetes_t1"] = _safe_percent(
            descriptive_force_base["tetes_t1"],
            descriptive_force_base["circonscriptions_t1"],
        )
        descriptive_force_base["taux_qualification"] = _safe_percent(
            descriptive_force_base["qualifies_t2"],
            descriptive_force_base["circonscriptions_t1"],
        )
        descriptive_force_base["taux_retrait"] = _safe_percent(
            descriptive_force_base["retraits_t2"],
            descriptive_force_base["qualifies_t2"],
        )
        descriptive_force_base["taux_victoire_t2"] = _safe_percent(
            descriptive_force_base["victoires_t2"],
            descriptive_force_base["maintiens_t2"],
        )

        st.markdown("**Analyse politique synthétique 2024 -> logique 2027**")
        synthesis_mode = st.selectbox(
            "Mode de correction de la synthèse",
            ["Corrigé par la représentation", "Brut"],
            index=0,
            key="analysis_2024_synthesis_mode",
        )
        use_representation_correction = synthesis_mode == "Corrigé par la représentation"
        if use_representation_correction:
            top_heads = (
                descriptive_force_base.loc[
                    descriptive_force_base["part_tetes_t1"] > 0,
                    ["Force", "part_tetes_t1", "tetes_t1", "circonscriptions_t1"],
                ]
                .sort_values(["part_tetes_t1", "tetes_t1"], ascending=[False, False])
                .head(8)
            )
            top_qualified = (
                descriptive_force_base.loc[
                    descriptive_force_base["taux_qualification"] > 0,
                    ["Force", "taux_qualification", "qualifies_t2", "circonscriptions_t1"],
                ]
                .sort_values(["taux_qualification", "qualifies_t2"], ascending=[False, False])
                .head(8)
            )
        else:
            top_heads = (
                display_force_stats.loc[display_force_stats["tetes_t1"] > 0, ["Force", "tetes_t1"]]
                .sort_values(["tetes_t1", "Force"], ascending=[False, True])
                .head(8)
            )
            top_qualified = (
                display_force_stats.loc[display_force_stats["qualifies_t2"] > 0, ["Force", "qualifies_t2"]]
                .sort_values(["qualifies_t2", "Force"], ascending=[False, True])
                .head(8)
            )
        top_withdrawals = (
            display_force_stats.loc[display_force_stats["retraits_t2"] > 0, ["Force", "retraits_t2"]]
            .sort_values(["retraits_t2", "Force"], ascending=[False, True])
            .head(8)
        )
        top_winners = (
            display_force_stats.loc[display_force_stats["victoires_t2"] > 0, ["Force", "victoires_t2"]]
            .sort_values(["victoires_t2", "Force"], ascending=[False, True])
            .head(8)
        )
        configuration_counts = (
            filtered["configuration_t2"]
            .fillna("Inconnue")
            .value_counts()
            .rename_axis("Configuration")
            .reset_index(name="Nombre")
        )

        synth_col1, synth_col2 = st.columns(2)
        with synth_col1:
            if not top_heads.empty:
                heads_x = top_heads["part_tetes_t1"] if use_representation_correction else top_heads["tetes_t1"]
                heads_chart = go.Figure(
                    go.Bar(
                        x=heads_x,
                        y=top_heads["Force"],
                        orientation="h",
                        marker_color=[_force_color(force) for force in top_heads["Force"]],
                        customdata=top_heads[["tetes_t1", "circonscriptions_t1"]].to_numpy() if use_representation_correction else None,
                        hovertemplate=(
                            "%{y}<br>Part des têtes: %{x:.1f}%<br>Têtes T1: %{customdata[0]}<br>Circonscriptions couvertes: %{customdata[1]}<extra></extra>"
                            if use_representation_correction
                            else None
                        ),
                    )
                )
                heads_chart.update_layout(
                    title="Qui arrive en tête au 1er tour" + (" · corrigé par la représentation" if use_representation_correction else ""),
                    xaxis_title="Part des circonscriptions couvertes (%)" if use_representation_correction else "Nombre de circonscriptions",
                    yaxis_title="Force",
                    **PLOT_LAYOUT_THEME,
                )
                if use_representation_correction:
                    heads_chart.update_xaxes(ticksuffix=" %")
                st.plotly_chart(heads_chart, width="stretch", config={"displayModeBar": False, "responsive": True})
            if not configuration_counts.empty:
                configuration_chart = go.Figure(
                    go.Bar(
                        x=configuration_counts["Configuration"],
                        y=configuration_counts["Nombre"],
                        marker_color="#7c5ea8",
                        text=configuration_counts["Nombre"],
                        textposition="outside",
                    )
                )
                configuration_chart.update_layout(
                    title="Formes réelles du second tour",
                    xaxis_title="Configuration",
                    yaxis_title="Nombre de circonscriptions",
                    **PLOT_LAYOUT_THEME,
                )
                st.plotly_chart(configuration_chart, width="stretch", config={"displayModeBar": False, "responsive": True})
        with synth_col2:
            if not top_qualified.empty:
                qualified_chart = go.Figure(
                    go.Bar(
                        x=top_qualified["taux_qualification"] if use_representation_correction else top_qualified["qualifies_t2"],
                        y=top_qualified["Force"],
                        orientation="h",
                        marker_color=[_force_color(force) for force in top_qualified["Force"]],
                        customdata=top_qualified[["qualifies_t2", "circonscriptions_t1"]].to_numpy() if use_representation_correction else None,
                        hovertemplate=(
                            "%{y}<br>Taux de qualification: %{x:.1f}%<br>Qualifications: %{customdata[0]}<br>Circonscriptions couvertes: %{customdata[1]}<extra></extra>"
                            if use_representation_correction
                            else None
                        ),
                    )
                )
                qualified_chart.update_layout(
                    title="Qui se qualifie le plus souvent au 2d tour" + (" · corrigé par la représentation" if use_representation_correction else ""),
                    xaxis_title="Taux de qualification (%)" if use_representation_correction else "Nombre de qualifications",
                    yaxis_title="Force",
                    **PLOT_LAYOUT_THEME,
                )
                if use_representation_correction:
                    qualified_chart.update_xaxes(ticksuffix=" %")
                st.plotly_chart(qualified_chart, width="stretch", config={"displayModeBar": False, "responsive": True})
            if not top_withdrawals.empty:
                withdrawal_summary_chart = go.Figure(
                    go.Bar(
                        x=top_withdrawals["retraits_t2"],
                        y=top_withdrawals["Force"],
                        orientation="h",
                        marker_color=[_force_color(force) for force in top_withdrawals["Force"]],
                    )
                )
                withdrawal_summary_chart.update_layout(
                    title="Qui se retire le plus souvent après qualification",
                    xaxis_title="Nombre de retraits",
                    yaxis_title="Force",
                    **PLOT_LAYOUT_THEME,
                )
                st.plotly_chart(withdrawal_summary_chart, width="stretch", config={"displayModeBar": False, "responsive": True})

        synthesis_lines: list[str] = []
        if not top_heads.empty:
            synthesis_lines.append(
                "Forces les plus souvent en tête au 1er tour : "
                + ", ".join(
                    f"{row.Force} ({int(row.tetes_t1)} circonscriptions)"
                    for row in top_heads.head(5).itertuples(index=False)
                )
            )
        if not top_qualified.empty:
            synthesis_lines.append(
                "Forces les plus souvent qualifiées au 2d tour : "
                + ", ".join(
                    f"{row.Force} ({int(row.qualifies_t2)} qualifications)"
                    for row in top_qualified.head(5).itertuples(index=False)
                )
            )
        if not top_withdrawals.empty:
            synthesis_lines.append(
                "Forces qui se retirent le plus souvent après qualification : "
                + ", ".join(
                    f"{row.Force} ({int(row.retraits_t2)} retraits)"
                    for row in top_withdrawals.head(5).itertuples(index=False)
                )
            )
        if has_real_second_round_results and not top_winners.empty:
            synthesis_lines.append(
                "Forces qui gagnent le plus souvent au 2d tour : "
                + ", ".join(
                    f"{row.Force} ({int(row.victoires_t2)} victoires)"
                    for row in top_winners.head(5).itertuples(index=False)
                )
            )
        if synthesis_lines:
            for line in synthesis_lines:
                st.caption(line)

        force_stats_chart = go.Figure()
        for column, label in [
            ("circonscriptions_t1", "Circo avec candidat T1"),
            ("qualifies_t2", "Qualifiés T2"),
            ("maintiens_t2", "Maintenus T2"),
            ("retraits_t2", "Retraits T2"),
            ("victoires_t2", "Victoires T2"),
        ]:
            if column not in display_force_stats.columns:
                continue
            force_stats_chart.add_trace(
                go.Bar(
                    x=display_force_stats["Force"],
                    y=display_force_stats[column],
                    name=label,
                )
            )
        force_stats_chart.update_layout(
            title="Statistiques complètes par force politique identifiée",
            barmode="group",
            xaxis_title="Force",
            yaxis_title="Nombre de circonscriptions / cas",
            **PLOT_LAYOUT_THEME,
        )
        st.plotly_chart(force_stats_chart, width="stretch", config={"displayModeBar": False, "responsive": True})

        st.dataframe(
            display_force_stats.rename(
                columns={
                    "Coalition": "Coalition",
                    "Bloc": "Bloc descriptif",
                    "circonscriptions_t1": "Circo avec candidat T1",
                    "qualifies_t2": "Qualifiés T2",
                    "maintiens_t2": "Maintiens T2",
                    "retraits_t2": "Retraits T2",
                    "tetes_t1": "Têtes au T1",
                    "elus_t1": "Élus T1",
                    "candidats_resultat_t2": "Candidats au résultat T2",
                    "victoires_t2": "Victoires T2",
                }
            ),
            width="stretch",
            hide_index=True,
        )

        if not residual_family_stats.empty:
            residual_chart = go.Figure(
                go.Bar(
                    x=residual_family_stats["Force"],
                    y=residual_family_stats["circonscriptions_t1"],
                    marker_color=[_force_color(force) for force in residual_family_stats["Force"]],
                    text=residual_family_stats["circonscriptions_t1"],
                    textposition="outside",
                )
            )
            residual_chart.update_layout(
                title="Familles administratives résiduelles",
                xaxis_title="Famille",
                yaxis_title="Circonscriptions avec candidat T1",
                **PLOT_LAYOUT_THEME,
            )
            st.plotly_chart(residual_chart, width="stretch", config={"displayModeBar": False, "responsive": True})

        st.markdown("**Table d’analyse exhaustive par circonscription et par force**")
        if not circo_force_analysis.empty:
            st.dataframe(
                circo_force_analysis[
                    [
                        "source_circo_code",
                        "dept_label",
                        "circo_label",
                        "analysis_force_label",
                        "coalition_label",
                        "bloc_label",
                        "nb_candidats",
                        "meilleur_score_t1",
                        "meilleur_score_inscrits_t1",
                        "est_qualifie",
                        "est_maintenu",
                        "est_retire",
                        "est_tete_t1",
                        "est_elu_t1",
                        "meilleur_candidat",
                        "configuration_t2",
                        "qualified_forces",
                        "maintained_forces",
                        "withdrawn_forces",
                        "winner_force_t2",
                        "winner_name_t2",
                    ]
                ].rename(
                    columns={
                        "source_circo_code": "Code circonscription",
                        "circo_label": "Circonscription",
                        "dept_label": "Département",
                        "analysis_force_label": "Force",
                        "coalition_label": "Coalition",
                        "bloc_label": "Bloc descriptif",
                        "nb_candidats": "Nb candidats",
                        "meilleur_score_t1": "Meilleur score T1",
                        "meilleur_score_inscrits_t1": "Meilleur score / inscrits T1",
                        "est_qualifie": "Qualifié T2",
                        "est_maintenu": "Maintenu T2",
                        "est_retire": "Retiré après qualification",
                        "est_tete_t1": "Tête au T1",
                        "est_elu_t1": "Élu au T1",
                        "meilleur_candidat": "Candidat le mieux placé",
                        "configuration_t2": "Configuration T2",
                        "maintained_forces": "Forces maintenues",
                        "withdrawn_forces": "Forces retirées",
                        "qualified_forces": "Forces qualifiées",
                        "winner_force_t2": "Force gagnante T2",
                        "winner_name_t2": "Candidat gagnant T2",
                    }
                ),
                width="stretch",
                hide_index=True,
                column_config={
                    "Meilleur score T1": st.column_config.NumberColumn("Meilleur score T1", format="%.2f %%"),
                    "Meilleur score / inscrits T1": st.column_config.NumberColumn("Meilleur score / inscrits T1", format="%.2f %%"),
                },
            )

        st.markdown("**Matrices des cas observés en 2024**")
        if not duel_matrix.empty:
            st.dataframe(
                duel_matrix.rename(
                    columns={
                        "duel_or_triangular_type": "Type de duel",
                        "withdrawn_forces": "Force retirée avant T2",
                        "winner_force_t2": "Force gagnante T2",
                        "nombre_de_cas": "Nombre de cas",
                    }
                ),
                width="stretch",
                hide_index=True,
            )
        if not tri_matrix.empty:
            st.dataframe(
                tri_matrix.rename(
                    columns={
                        "duel_or_triangular_type": "Type de triangulaire",
                        "winner_force_t2": "Force gagnante T2",
                        "nombre_de_cas": "Nombre de cas",
                    }
                ),
                width="stretch",
                hide_index=True,
            )
        if not withdrawal_matrix.empty:
            st.dataframe(
                withdrawal_matrix.rename(
                    columns={
                        "analysis_force_label": "Force retirée",
                        "configuration_t2": "Configuration T2",
                        "maintained_forces": "Forces restées au T2",
                        "nombre_de_retraits": "Nombre de retraits",
                    }
                ),
                width="stretch",
                hide_index=True,
            )

        st.markdown("**Lecture descriptive des résultats 2024**")
        top_force_t1 = descriptive_force_base.sort_values(
            ["tetes_t1", "circonscriptions_t1"],
            ascending=[False, False],
        ).head(3)
        top_qualification = descriptive_force_base.sort_values(
            ["taux_qualification", "qualifies_t2"],
            ascending=[False, False],
        ).head(3)
        top_withdrawal = descriptive_force_base.loc[descriptive_force_base["retraits_t2"] > 0].sort_values(
            ["retraits_t2", "taux_retrait"],
            ascending=[False, False],
        ).head(3)
        top_t2 = descriptive_force_base.loc[descriptive_force_base["victoires_t2"] > 0].sort_values(
            ["victoires_t2", "taux_victoire_t2"],
            ascending=[False, False],
        ).head(3)

        descriptive_lines: list[str] = []
        if not top_force_t1.empty:
            descriptive_lines.append(
                "Premier tour : "
                + ", ".join(
                    f"{row.Force} ({int(row.tetes_t1)} têtes de circonscription)"
                    for row in top_force_t1.itertuples(index=False)
                )
            )
        if not top_qualification.empty:
            descriptive_lines.append(
                "Qualification au second tour : "
                + ", ".join(
                    f"{row.Force} ({float(row.taux_qualification):.1f}% des circonscriptions où la force était présente)"
                    for row in top_qualification.itertuples(index=False)
                )
            )
        if not top_withdrawal.empty:
            descriptive_lines.append(
                "Désistements : "
                + ", ".join(
                    f"{row.Force} ({int(row.retraits_t2)} retraits, {float(row.taux_retrait):.1f}% des qualifiés)"
                    for row in top_withdrawal.itertuples(index=False)
                )
            )
        if has_real_second_round_results and not top_t2.empty:
            descriptive_lines.append(
                "Second tour : "
                + ", ".join(
                    f"{row.Force} ({int(row.victoires_t2)} victoires, {float(row.taux_victoire_t2):.1f}% des maintiens)"
                    for row in top_t2.itertuples(index=False)
                )
            )
        if descriptive_lines:
            for line in descriptive_lines:
                st.caption(line)

        st.markdown("**Projection 2027 issue du 1er tour 2024 corrigé de la couverture des forces**")
        if not first_round_projection_2027.empty:
            top_projection = first_round_projection_2027.head(5)
            display_projection = first_round_projection_2027.copy()
            display_projection["Force_affichee"] = display_projection["Force"].map(_projection_force_display_label)
            st.caption(
                "Idée directrice : on ne reprend pas la masse brute des voix de 2024. "
                "On part d'abord d'un score national couvert, c'est-à-dire du score moyen d'une force "
                "pondéré par sa couverture réelle des circonscriptions. Ensuite seulement, on corrige "
                "par la capacité réelle à arriver en tête, à se qualifier et à se maintenir."
            )
            st.caption(
                "Forces les mieux placées dans ce socle corrigé : "
                + ", ".join(
                    f"{_projection_force_display_label(row.Force)} ({float(row.socle_projete_2027_t1):.1f}%)"
                    for row in top_projection.itertuples(index=False)
                )
            )
            first_round_projection_chart = go.Figure(
                go.Bar(
                    x=display_projection["Force_affichee"],
                    y=display_projection["socle_projete_2027_t1"],
                    marker_color=[_force_color(force) for force in display_projection["Force"]],
                    text=[f"{value:.1f} %" for value in display_projection["socle_projete_2027_t1"]],
                    textposition="outside",
                )
            )
            first_round_projection_chart.update_layout(
                title="Socle 2027 estimé à partir du 1er tour 2024 corrigé du biais de présence locale",
                xaxis_title="Force",
                yaxis_title="Socle estimé (%)",
                **PLOT_LAYOUT_THEME,
            )
            first_round_projection_chart.update_yaxes(ticksuffix=" %")
            st.plotly_chart(first_round_projection_chart, width="stretch", config={"displayModeBar": False, "responsive": True})

            st.dataframe(
                display_projection[
                    [
                        "Force_affichee",
                        "circonscriptions_presentes",
                        "taux_couverture",
                        "score_moyen_sur_circos_presentes",
                        "score_national_couvert_t1",
                        "presence_nationalisee_t1",
                        "facteur_couverture_2027",
                        "taux_tete_t1",
                        "taux_qualification_t2",
                        "taux_maintien_parmi_qualifies",
                        "taux_retrait_parmi_qualifies",
                        "coefficient_dynamique_2027",
                        "socle_projete_2027_t1",
                    ]
                ].rename(
                    columns={
                        "Force_affichee": "Force politique",
                        "circonscriptions_presentes": "Circonscriptions couvertes",
                        "taux_couverture": "Taux de couverture",
                        "score_moyen_sur_circos_presentes": "Score moyen là où la force est présente",
                        "score_national_couvert_t1": "Score national couvert T1",
                        "presence_nationalisee_t1": "Présence nationalisée au T1",
                        "facteur_couverture_2027": "Facteur de couverture",
                        "taux_tete_t1": "Taux de tête au T1",
                        "taux_qualification_t2": "Taux de qualification T2",
                        "taux_maintien_parmi_qualifies": "Taux de maintien parmi les qualifiés",
                        "taux_retrait_parmi_qualifies": "Taux de retrait parmi les qualifiés",
                        "coefficient_dynamique_2027": "Coefficient dynamique 2027",
                        "socle_projete_2027_t1": "Socle projeté 2027",
                    }
                ),
                width="stretch",
                hide_index=True,
                column_config={
                    "Taux de couverture": st.column_config.NumberColumn("Taux de couverture", format="%.2f %%"),
                    "Score moyen là où la force est présente": st.column_config.NumberColumn("Score moyen là où la force est présente", format="%.2f %%"),
                    "Score national couvert T1": st.column_config.NumberColumn("Score national couvert T1", format="%.2f %%"),
                    "Présence nationalisée au T1": st.column_config.NumberColumn("Présence nationalisée au T1", format="%.2f %%"),
                    "Facteur de couverture": st.column_config.NumberColumn("Facteur de couverture", format="%.3f"),
                    "Taux de tête au T1": st.column_config.NumberColumn("Taux de tête au T1", format="%.2f %%"),
                    "Taux de qualification T2": st.column_config.NumberColumn("Taux de qualification T2", format="%.2f %%"),
                    "Taux de maintien parmi les qualifiés": st.column_config.NumberColumn("Taux de maintien parmi les qualifiés", format="%.2f %%"),
                    "Taux de retrait parmi les qualifiés": st.column_config.NumberColumn("Taux de retrait parmi les qualifiés", format="%.2f %%"),
                    "Coefficient dynamique 2027": st.column_config.NumberColumn("Coefficient dynamique 2027", format="%.2f"),
                    "Socle projeté 2027": st.column_config.NumberColumn("Socle projeté 2027", format="%.2f %%"),
                },
            )

        st.markdown("**Désistements observés et issue politique finale**")
        if has_real_second_round_results and not anti_target_matrix.empty:
            top_withdrawal_cases = anti_target_matrix.head(5)
            st.caption(
                "Lecture politique : au second tour, on ne lit pas d'abord un vote pour, mais un vote contre. "
                "On regarde donc quelle force se retire contre quelle autre force, puis quelle force profite "
                "finalement de ce barrage."
            )
            st.caption(
                "Barrages les plus fréquents : "
                + ", ".join(
                    f"{row.force_retirée} contre {row.force_battue_t2} ({int(row.nombre_de_cas)} cas, {row.force_gagnante_t2} gagne)"
                    for row in top_withdrawal_cases.itertuples(index=False)
                )
            )
            anti_target_chart = go.Figure(
                go.Bar(
                    x=anti_target_matrix["nombre_de_cas"],
                    y=anti_target_matrix["force_retirée"] + " contre " + anti_target_matrix["force_battue_t2"],
                    orientation="h",
                    marker_color=[_force_color(force) for force in anti_target_matrix["force_retirée"]],
                    customdata=anti_target_matrix[["force_gagnante_t2", "configuration_t2"]].to_numpy(),
                    hovertemplate=(
                        "Retrait: %{y}<br>"
                        "Nombre de cas: %{x}<br>"
                        "Force qui gagne ensuite: %{customdata[0]}<br>"
                        "Configuration: %{customdata[1]}<extra></extra>"
                    ),
                )
            )
            anti_target_chart.update_layout(
                title="Désistements observés comme barrages contre une force",
                xaxis_title="Nombre de cas",
                yaxis_title="Retrait contre",
                **PLOT_LAYOUT_THEME,
            )
            st.plotly_chart(anti_target_chart, width="stretch", config={"displayModeBar": False, "responsive": True})
            st.dataframe(
                anti_target_matrix.rename(
                    columns={
                        "force_retirée": "Force retirée",
                        "force_battue_t2": "Force bloquée par le retrait",
                        "force_gagnante_t2": "Force qui gagne ensuite",
                        "configuration_t2": "Configuration finale",
                        "nombre_de_cas": "Nombre de cas",
                    }
                ),
                width="stretch",
                hide_index=True,
            )
        if has_real_second_round_results and not withdrawal_target_matrix.empty:
            st.dataframe(
                withdrawal_target_matrix.rename(
                    columns={
                        "force_retirée": "Force retirée",
                        "configuration_t2": "Configuration finale",
                        "maintained_forces": "Forces restées au T2",
                        "force_gagnante_t2": "Force qui gagne ensuite",
                        "force_battue_t2": "Force battue ensuite",
                        "nombre_de_cas": "Nombre de cas",
                    }
                ),
                width="stretch",
                hide_index=True,
            )
        if has_real_second_round_results and not against_matrix.empty:
            st.caption(
                "Détail complémentaire : quand une force se retire, on regarde aussi devant qui elle se retire "
                "concrètement dans la configuration finale."
            )
            st.dataframe(
                against_matrix.rename(
                    columns={
                        "force_retirée": "Force retirée",
                        "force_restée_en_face": "Force restée en face",
                        "force_gagnante_t2": "Force qui gagne ensuite",
                        "force_battue_t2": "Force finalement battue",
                        "nombre_de_cas": "Nombre de cas",
                    }
                ),
                width="stretch",
                hide_index=True,
            )

        st.markdown("**Rapports de force de second tour utiles pour une logique présidentielle**")
        if has_real_second_round_results and not duel_presidential_base.empty:
            top_duel_base = duel_presidential_base.head(5)
            st.caption(
                "Lecture présidentielle : on transforme les duels réels de 2024 en base de rapports de force. "
                "Ce n’est pas une prévision automatique de 2027, mais un socle pour savoir quelles affiches "
                "gagnent le plus souvent et contre qui."
            )
            st.caption(
                "Affiches les plus favorables observées : "
                + ", ".join(
                    f"{row.Force} vs {row.Adversaire} ({float(row.taux_de_victoire):.1f}% de victoires sur {int(row.total_duels)} duels)"
                    for row in top_duel_base.itertuples(index=False)
                )
            )
            duel_presidential_chart = go.Figure(
                go.Bar(
                    x=duel_presidential_base["taux_de_victoire"],
                    y=duel_presidential_base["Force"] + " vs " + duel_presidential_base["Adversaire"],
                    orientation="h",
                    marker_color=[_force_color(force) for force in duel_presidential_base["Force"]],
                    customdata=duel_presidential_base[["victoire", "défaite", "total_duels"]].to_numpy(),
                    hovertemplate=(
                        "Affiche: %{y}<br>"
                        "Taux de victoire: %{x:.1f}%<br>"
                        "Victoires: %{customdata[0]}<br>"
                        "Défaites: %{customdata[1]}<br>"
                        "Total: %{customdata[2]}<extra></extra>"
                    ),
                )
            )
            duel_presidential_chart.update_layout(
                title="Taux de victoire observé par duel politique réel",
                xaxis_title="Taux de victoire observé (%)",
                yaxis_title="Affiche politique",
                **PLOT_LAYOUT_THEME,
            )
            duel_presidential_chart.update_xaxes(ticksuffix=" %")
            st.plotly_chart(duel_presidential_chart, width="stretch", config={"displayModeBar": False, "responsive": True})

            st.dataframe(
                duel_presidential_base.rename(
                    columns={
                        "Force": "Force",
                        "Adversaire": "Adversaire",
                        "victoire": "Victoires",
                        "défaite": "Défaites",
                        "total_duels": "Total de duels",
                        "taux_de_victoire": "Taux de victoire",
                    }
                ),
                width="stretch",
                hide_index=True,
                column_config={
                    "Taux de victoire": st.column_config.NumberColumn("Taux de victoire", format="%.2f %%"),
                },
            )
        elif not has_real_second_round_results:
            st.caption("Les résultats réels du second tour ne sont pas encore exploitables proprement dans cette session ; les blocs de victoire T2 et de duel politique final sont masqués pour éviter des tableaux faux ou vides.")

        top_force_choice = st.selectbox(
            "Force politique détaillée",
            force_stats["Force"].tolist(),
            key="analysis_2024_force_stats_choice",
        )
        selected_force_rows = candidates.loc[candidates["analysis_force_label"] == top_force_choice].copy()
        selected_force_summary = (
            selected_force_rows.groupby("circo_key", dropna=False)
            .agg(
                source_circo_code=("source_circo_code", "first"),
                circo_label=("circo_label", "first"),
                dept_label=("dept_label", "first"),
                candidats=("candidate_key", "count"),
                qualifies=("qualified_for_second_round", "sum"),
                maintenus=("maintained_second_round", "sum"),
                retires=("withdrawn_after_qualification", "sum"),
                meilleur_score=("share_exprimes", "max"),
            )
            .reset_index()
            .sort_values(["meilleur_score", "candidats"], ascending=[False, False])
        )
        selected_force_summary = selected_force_summary.drop(columns=["circo_key"], errors="ignore")
        st.dataframe(
            selected_force_summary[
                [
                    "source_circo_code",
                    "dept_label",
                    "circo_label",
                    "candidats",
                    "qualifies",
                    "maintenus",
                    "retires",
                    "meilleur_score",
                ]
            ].rename(
                columns={
                    "source_circo_code": "Code circonscription",
                    "circo_label": "Circonscription",
                    "dept_label": "Département",
                    "candidats": "Nb candidats",
                    "qualifies": "Nb qualifiés",
                    "maintenus": "Nb maintenus",
                    "retires": "Nb retirés",
                    "meilleur_score": "Meilleur score T1",
                }
            ),
            width="stretch",
            hide_index=True,
            column_config={
                "Meilleur score T1": st.column_config.NumberColumn("Meilleur score T1", format="%.2f %%"),
            },
        )

        if has_real_second_round_results:
            second_round_case_stats = (
                summary.loc[summary["configuration_t2"].isin(["Duel", "Triangulaire"])]
                .groupby(["configuration_t2", "duel_or_triangular_type", "winner_force_t2"], dropna=False)
                .size()
                .rename("circo_count")
                .reset_index()
                .sort_values(["configuration_t2", "circo_count"], ascending=[True, False])
            )
            winner_counts = (
                second_round_case_stats.groupby("winner_force_t2", dropna=False)["circo_count"]
                .sum()
                .reset_index()
                .sort_values("circo_count", ascending=False)
            )
            t2_winner_chart = go.Figure(
                go.Bar(
                    x=winner_counts["circo_count"],
                    y=winner_counts["winner_force_t2"],
                    orientation="h",
                    marker_color=[_force_color(force) for force in winner_counts["winner_force_t2"]],
                )
            )
            t2_winner_chart.update_layout(
                title="Victoires réelles du second tour par force",
                xaxis_title="Nombre de victoires",
                yaxis_title="Force gagnante",
                **PLOT_LAYOUT_THEME,
            )
            st.plotly_chart(t2_winner_chart, width="stretch", config={"displayModeBar": False, "responsive": True})

            st.dataframe(
                second_round_case_stats.rename(
                    columns={
                        "configuration_t2": "Type de cas",
                        "duel_or_triangular_type": "Configuration politique",
                        "winner_force_t2": "Force gagnante T2",
                        "circo_count": "Nombre de cas",
                    }
                ),
                width="stretch",
                hide_index=True,
            )

            duel_cases = (
                summary.loc[summary["configuration_t2"] == "Duel"]
                .groupby(["duel_or_triangular_type", "winner_force_t2", "runner_up_force_t2"], dropna=False)
                .size()
                .rename("circo_count")
                .reset_index()
                .sort_values("circo_count", ascending=False)
            )
            if not duel_cases.empty:
                st.dataframe(
                    duel_cases.rename(
                        columns={
                            "duel_or_triangular_type": "Type de duel",
                            "winner_force_t2": "Force gagnante",
                            "runner_up_force_t2": "Force battue",
                            "circo_count": "Nombre de duels",
                        }
                    ),
                    width="stretch",
                    hide_index=True,
                )

            tri_cases = (
                summary.loc[summary["configuration_t2"] == "Triangulaire"]
                .groupby(["duel_or_triangular_type", "withdrawn_forces", "winner_force_t2"], dropna=False)
                .size()
                .rename("circo_count")
                .reset_index()
                .sort_values("circo_count", ascending=False)
            )
            if not tri_cases.empty:
                st.dataframe(
                    tri_cases.rename(
                        columns={
                            "duel_or_triangular_type": "Type de triangulaire",
                            "withdrawn_forces": "Force retirée avant T2",
                            "winner_force_t2": "Force gagnante T2",
                            "circo_count": "Nombre de triangulaires",
                        }
                    ),
                    width="stretch",
                    hide_index=True,
                )

        force_head_efficiency = force_stats.copy()
        force_head_efficiency["part_tetes_t1"] = _safe_percent(
            force_head_efficiency["tetes_t1"],
            force_head_efficiency["circonscriptions_t1"],
        )
        force_head_efficiency = (
            force_head_efficiency.loc[force_head_efficiency["circonscriptions_t1"] > 0]
            .sort_values(["part_tetes_t1", "tetes_t1"], ascending=[False, False])
            .head(15)
            .sort_values("part_tetes_t1", ascending=True)
        )
        leader_chart = go.Figure(
            go.Bar(
                x=force_head_efficiency["part_tetes_t1"],
                y=force_head_efficiency["Force"],
                orientation="h",
                marker_color=[_force_color(force) for force in force_head_efficiency["Force"]],
                customdata=force_head_efficiency[["tetes_t1", "circonscriptions_t1"]].to_numpy(),
                hovertemplate=(
                    "Force: %{y}<br>"
                    "Part des têtes au T1: %{x:.1f}%<br>"
                    "Têtes au T1: %{customdata[0]}<br>"
                    "Circo avec candidat T1: %{customdata[1]}<extra></extra>"
                ),
            )
        )
        leader_chart.update_layout(
            title="Part des circonscriptions remportées au 1er tour parmi celles où la force était présente",
            xaxis_title="Part des têtes au T1 (%)",
            yaxis_title="Force",
            **PLOT_LAYOUT_THEME,
        )
        leader_chart.update_xaxes(ticksuffix=" %")
        st.plotly_chart(leader_chart, width="stretch", config={"displayModeBar": False, "responsive": True})

        final_configs = (
            filtered.groupby("duel_or_triangular_type", dropna=False)
            .size()
            .rename("circo_count")
            .reset_index()
            .sort_values("circo_count", ascending=False)
            .head(20)
        )
        final_config_chart = go.Figure(
            go.Bar(
                x=final_configs["duel_or_triangular_type"],
                y=final_configs["circo_count"],
                marker_color="#d34a6a",
            )
        )
        final_config_chart.update_layout(
            title="Configurations finales observées au second tour",
            xaxis_title="Configuration réelle",
            yaxis_title="Nombre de circonscriptions",
            **PLOT_LAYOUT_THEME,
        )
        st.plotly_chart(final_config_chart, width="stretch", config={"displayModeBar": False, "responsive": True})

        triangulaires = filtered.loc[filtered["configuration_t2"] == "Triangulaire"].copy()
        if not triangulaires.empty:
            tri_type_counts = (
                triangulaires.groupby("duel_or_triangular_type", dropna=False)
                .size()
                .rename("circo_count")
                .reset_index()
                .sort_values("circo_count", ascending=False)
            )
            tri_type_chart = go.Figure(
                go.Bar(
                    x=tri_type_counts["circo_count"],
                    y=tri_type_counts["duel_or_triangular_type"],
                    orientation="h",
                    marker_color="#7c5ea8",
                )
            )
            tri_type_chart.update_layout(
                title="Triangulaires réelles par combinaison de forces",
                xaxis_title="Nombre de triangulaires",
                yaxis_title="Type de triangulaire",
                **PLOT_LAYOUT_THEME,
            )
            st.plotly_chart(tri_type_chart, width="stretch", config={"displayModeBar": False, "responsive": True})

            tri_choice = st.selectbox(
                "Type de triangulaire détaillé",
                tri_type_counts["duel_or_triangular_type"].tolist(),
                key="analysis_2024_triangular_type_choice",
            )
            tri_detail = triangulaires.loc[triangulaires["duel_or_triangular_type"] == tri_choice].copy()
            st.dataframe(
                tri_detail[
                    [
                        "source_circo_code",
                        "circo_full_label",
                        "leader_force",
                        "leader_share_exprimes",
                        "qualified_forces",
                        "maintained_forces",
                        "withdrawn_forces",
                    ]
                ].rename(
                    columns={
                        "source_circo_code": "Code circonscription",
                        "circo_full_label": "Circonscription",
                        "leader_force": "Force en tête au T1",
                        "leader_share_exprimes": "% du leader au T1",
                        "qualified_forces": "Forces qualifiées",
                        "maintained_forces": "Forces maintenues",
                        "withdrawn_forces": "Force retirée",
                    }
                ),
                width="stretch",
                hide_index=True,
                column_config={
                    "% du leader au T1": st.column_config.NumberColumn("% du leader au T1", format="%.2f %%"),
                },
            )

            withdrawal_rows = candidates.loc[candidates["withdrawn_after_qualification"]].copy()
            if not withdrawal_rows.empty:
                withdrawal_rows = withdrawal_rows.merge(
                    summary[["circo_key", "source_circo_code", "duel_or_triangular_type", "circo_full_label", "maintained_forces", "leader_force"]],
                    on="circo_key",
                    how="left",
                    suffixes=("", "_summary"),
                )
                if "source_circo_code_summary" in withdrawal_rows.columns:
                    withdrawal_rows["source_circo_code"] = withdrawal_rows["source_circo_code"].fillna(withdrawal_rows["source_circo_code_summary"])
                if "circo_full_label_summary" in withdrawal_rows.columns:
                    withdrawal_rows["circo_full_label"] = withdrawal_rows["circo_full_label"].fillna(withdrawal_rows["circo_full_label_summary"])
                withdrawal_rows = withdrawal_rows.drop(
                    columns=["source_circo_code_summary", "circo_full_label_summary"],
                    errors="ignore",
                )
                withdrawal_rows["source_circo_code"] = withdrawal_rows["source_circo_code"].fillna(withdrawal_rows["circo_key"])
                withdrawal_rows["circo_full_label"] = withdrawal_rows["circo_full_label"].fillna(withdrawal_rows["circo_label"])
                withdrawal_counts = (
                    withdrawal_rows.groupby(["analysis_force_label", "duel_or_triangular_type"], dropna=False)
                    .size()
                    .rename("withdrawal_count")
                    .reset_index()
                    .sort_values("withdrawal_count", ascending=False)
                    .head(20)
                )
                withdrawal_chart = go.Figure(
                    go.Bar(
                        x=withdrawal_counts["withdrawal_count"],
                        y=withdrawal_counts["analysis_force_label"] + " -> " + withdrawal_counts["duel_or_triangular_type"],
                        orientation="h",
                        marker_color=[_force_color(force) for force in withdrawal_counts["analysis_force_label"]],
                    )
                )
                withdrawal_chart.update_layout(
                    title="Désistements observés des qualifiés, par force et configuration finale",
                    xaxis_title="Nombre de cas",
                    yaxis_title="Retrait observé",
                    **PLOT_LAYOUT_THEME,
                )
                st.plotly_chart(withdrawal_chart, width="stretch", config={"displayModeBar": False, "responsive": True})

                withdrawal_force_choice = st.selectbox(
                    "Force retirée détaillée",
                    withdrawal_counts["analysis_force_label"].drop_duplicates().tolist(),
                    key="analysis_2024_withdrawal_force_choice",
                )
                withdrawal_detail = (
                    withdrawal_rows.loc[withdrawal_rows["analysis_force_label"] == withdrawal_force_choice]
                    .sort_values(["duel_or_triangular_type", "share_exprimes"], ascending=[True, False])
                    .copy()
                )
                withdrawal_detail["candidat_retiré"] = withdrawal_detail["candidate_name"] + " · " + withdrawal_detail["analysis_force_label"]
                st.dataframe(
                    withdrawal_detail[
                        [
                            "source_circo_code",
                            "circo_full_label",
                            "candidat_retiré",
                            "share_exprimes",
                            "share_inscrits",
                            "leader_force",
                            "maintained_forces",
                            "duel_or_triangular_type",
                        ]
                    ].rename(
                        columns={
                            "source_circo_code": "Code circonscription",
                            "circo_full_label": "Circonscription",
                            "candidat_retiré": "Candidat retiré",
                            "share_exprimes": "% exprimés du retiré au T1",
                            "share_inscrits": "% inscrits du retiré au T1",
                            "leader_force": "Force en tête au T1",
                            "maintained_forces": "Forces restées au T2",
                            "duel_or_triangular_type": "Configuration finale",
                        }
                    ),
                    width="stretch",
                    hide_index=True,
                    column_config={
                        "% exprimés du retiré au T1": st.column_config.NumberColumn("% exprimés du retiré au T1", format="%.2f %%"),
                        "% inscrits du retiré au T1": st.column_config.NumberColumn("% inscrits du retiré au T1", format="%.2f %%"),
                    },
                )

        circo_options = filtered["source_circo_code"].tolist()
        if not circo_options:
            st.warning("Aucune circonscription ne correspond aux filtres.")
            return
        selected_circo = st.selectbox(
            "Circonscription détaillée",
            circo_options,
            key="analysis_2024_force_circo_selected",
            format_func=lambda value: filtered.loc[filtered["source_circo_code"] == value, "circo_full_label"].iloc[0],
        )
        selected_summary = filtered.loc[filtered["source_circo_code"] == selected_circo].iloc[0]
        circo_candidates = (
            candidates.loc[candidates["circo_key"] == selected_summary["circo_key"]]
            .sort_values(["votes", "candidate_rank_panel"], ascending=[False, True])
            .copy()
        )
        circo_candidates["statut"] = circo_candidates.apply(
            lambda row: "Maintenu au second tour"
            if bool(row["maintained_second_round"])
            else ("Qualifié puis retiré" if bool(row["withdrawn_after_qualification"]) else "Éliminé au premier tour"),
            axis=1,
        )

        detail_chart = go.Figure(
            go.Bar(
                x=circo_candidates["votes"],
                y=circo_candidates["candidate_name"] + " · " + circo_candidates["force_label"],
                orientation="h",
                marker_color=[
                    _force_color(force, nuance) if status != "Qualifié puis retiré" else "#9b59b6"
                    for force, nuance, status in zip(
                        circo_candidates["force_label"],
                        circo_candidates["nuance"],
                        circo_candidates["statut"],
                    )
                ],
                text=[f"{value:.1f} %" for value in circo_candidates["share_exprimes"]],
                textposition="outside",
            )
        )
        detail_chart.update_layout(
            title=f"{selected_circo} · candidats du 1er tour et statut au 2d tour",
            xaxis_title="Voix",
            yaxis_title="Candidat",
            **PLOT_LAYOUT_THEME,
        )
        st.plotly_chart(detail_chart, width="stretch", config={"displayModeBar": False, "responsive": True})

        selected_maintained = maintained.loc[maintained["circo_key"] == selected_summary["circo_key"]].copy() if not maintained.empty else pd.DataFrame()
        selected_final = second_round_final.loc[second_round_final["circo_key"] == selected_summary["circo_key"]].copy() if not second_round_final.empty else pd.DataFrame()
        metric1, metric2, metric3, metric4 = st.columns(4)
        metric1.metric("Force en tête au 1er tour", str(selected_summary["leader_force"]), f"{float(selected_summary['leader_share_exprimes']):.1f} %")
        metric2.metric("Configuration T2", str(selected_summary["configuration_t2"]), str(selected_summary["maintained_count"]))
        metric3.metric("Qualifiés retirés", int(selected_summary["withdrawn_count"]))
        metric4.metric("Vainqueur T2", _display_text(selected_summary.get("winner_force_t2")))

        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "Forces qualifiées": _display_text(selected_summary["qualified_forces"], "Aucune"),
                        "Forces restées au T2": _display_text(selected_summary["maintained_forces"], "Aucune"),
                        "Forces retirées": _display_text(selected_summary["withdrawn_forces"], "Aucune"),
                        "Vainqueur réel T2": _display_text(selected_summary.get("winner_force_t2")),
                        "Score vainqueur T2": float(selected_summary.get("winner_share_t2")) if pd.notna(selected_summary.get("winner_share_t2")) else None,
                    }
                ]
            ),
            width="stretch",
            hide_index=True,
            column_config={
                "Score vainqueur T2": st.column_config.NumberColumn("Score vainqueur T2", format="%.2f %%"),
            },
        )

        st.dataframe(
            circo_candidates[
                [
                    "candidate_name",
                    "force_label",
                    "nuance",
                    "votes",
                    "share_exprimes",
                    "share_inscrits",
                    "qualified_for_second_round",
                    "maintained_second_round",
                    "withdrawn_after_qualification",
                    "statut",
                ]
            ].rename(
                columns={
                    "candidate_name": "Candidat",
                    "force_label": "Force",
                    "nuance": "Nuance",
                    "votes": "Voix T1",
                    "share_exprimes": "% exprimés T1",
                    "share_inscrits": "% inscrits T1",
                    "qualified_for_second_round": "Qualifié",
                    "maintained_second_round": "Maintenu T2",
                    "withdrawn_after_qualification": "Retiré après qualification",
                    "statut": "Statut",
                }
            ),
            width="stretch",
            hide_index=True,
            column_config={
                "% exprimés T1": st.column_config.NumberColumn("% exprimés T1", format="%.2f %%"),
                "% inscrits T1": st.column_config.NumberColumn("% inscrits T1", format="%.2f %%"),
            },
        )

        if str(selected_summary["configuration_t2"]) == "Triangulaire":
            st.dataframe(
                circo_candidates.loc[circo_candidates["qualified_for_second_round"]][
                    [
                        "candidate_name",
                        "force_label",
                        "share_exprimes",
                        "share_inscrits",
                        "maintained_second_round",
                        "withdrawn_after_qualification",
                    ]
                ].rename(
                    columns={
                        "candidate_name": "Candidat qualifié",
                        "force_label": "Force",
                        "share_exprimes": "% exprimés T1",
                        "share_inscrits": "% inscrits T1",
                        "maintained_second_round": "Reste au T2",
                        "withdrawn_after_qualification": "Se retire",
                    }
                ),
                width="stretch",
                hide_index=True,
                column_config={
                    "% exprimés T1": st.column_config.NumberColumn("% exprimés T1", format="%.2f %%"),
                    "% inscrits T1": st.column_config.NumberColumn("% inscrits T1", format="%.2f %%"),
                },
            )

        if not selected_maintained.empty:
            st.dataframe(
                selected_maintained[["candidate_name", "force_label", "nuance"]].rename(
                    columns={
                        "candidate_name": "Candidat maintenu au T2",
                        "force_label": "Force",
                        "nuance": "Nuance",
                    }
                ),
                width="stretch",
                hide_index=True,
            )
        if not selected_final.empty:
            round_summary_row = selected_final.iloc[0]
            round_summary = pd.DataFrame(
                [
                    {
                        "Indicateur": "Votes valides",
                        "1er tour": float(round_summary_row["votes_valides_t1"]) if "votes_valides_t1" in round_summary_row and pd.notna(round_summary_row["votes_valides_t1"]) else None,
                        "2d tour": float(round_summary_row["votes_valides_t2"]) if "votes_valides_t2" in round_summary_row and pd.notna(round_summary_row["votes_valides_t2"]) else None,
                    },
                    {
                        "Indicateur": "Votes blancs",
                        "1er tour": float(round_summary_row["votes_blancs_t1"]) if "votes_blancs_t1" in round_summary_row and pd.notna(round_summary_row["votes_blancs_t1"]) else None,
                        "2d tour": float(round_summary_row["votes_blancs_t2"]) if "votes_blancs_t2" in round_summary_row and pd.notna(round_summary_row["votes_blancs_t2"]) else None,
                    },
                    {
                        "Indicateur": "Votes nuls",
                        "1er tour": float(round_summary_row["votes_nuls_t1"]) if "votes_nuls_t1" in round_summary_row and pd.notna(round_summary_row["votes_nuls_t1"]) else None,
                        "2d tour": float(round_summary_row["votes_nuls_t2"]) if "votes_nuls_t2" in round_summary_row and pd.notna(round_summary_row["votes_nuls_t2"]) else None,
                    },
                    {
                        "Indicateur": "Total votants",
                        "1er tour": float(round_summary_row["total_t1"]) if "total_t1" in round_summary_row and pd.notna(round_summary_row["total_t1"]) else None,
                        "2d tour": float(round_summary_row["total_t2"]) if "total_t2" in round_summary_row and pd.notna(round_summary_row["total_t2"]) else None,
                    },
                    {
                        "Indicateur": "Abstentions",
                        "1er tour": float(round_summary_row["abstention_t1"]) if "abstention_t1" in round_summary_row and pd.notna(round_summary_row["abstention_t1"]) else None,
                        "2d tour": float(round_summary_row["abstention_t2"]) if "abstention_t2" in round_summary_row and pd.notna(round_summary_row["abstention_t2"]) else None,
                    },
                    {
                        "Indicateur": "Inscrits",
                        "1er tour": float(round_summary_row["inscrits_participation_t1"]) if "inscrits_participation_t1" in round_summary_row and pd.notna(round_summary_row["inscrits_participation_t1"]) else None,
                        "2d tour": float(round_summary_row["inscrits_participation_t2"]) if "inscrits_participation_t2" in round_summary_row and pd.notna(round_summary_row["inscrits_participation_t2"]) else None,
                    },
                    {
                        "Indicateur": "Participation",
                        "1er tour": float(round_summary_row["participation_pct_t1"]) if "participation_pct_t1" in round_summary_row and pd.notna(round_summary_row["participation_pct_t1"]) else None,
                        "2d tour": float(round_summary_row["participation_pct_t2"]) if "participation_pct_t2" in round_summary_row and pd.notna(round_summary_row["participation_pct_t2"]) else None,
                    },
                    {
                        "Indicateur": "Abstention (%)",
                        "1er tour": float(round_summary_row["abstention_pct_t1"]) if "abstention_pct_t1" in round_summary_row and pd.notna(round_summary_row["abstention_pct_t1"]) else None,
                        "2d tour": float(round_summary_row["abstention_pct_t2"]) if "abstention_pct_t2" in round_summary_row and pd.notna(round_summary_row["abstention_pct_t2"]) else None,
                    },
                ]
            )
            st.dataframe(
                round_summary,
                width="stretch",
                hide_index=True,
                column_config={
                    "1er tour": st.column_config.NumberColumn("1er tour", format="%.2f"),
                    "2d tour": st.column_config.NumberColumn("2d tour", format="%.2f"),
                },
            )

            final_chart = go.Figure(
                go.Bar(
                    x=selected_final["candidate_name"] + " · " + selected_final["force_label"],
                    y=selected_final["share_exprimes_t2"],
                    marker_color=[_force_color(force, nuance) for force, nuance in zip(selected_final["force_label"], selected_final["nuance"])],
                    text=[f"{value:.1f} %" for value in selected_final["share_exprimes_t2"]],
                    textposition="outside",
                )
            )
            final_chart.update_layout(
                title=f"{selected_circo} · résultat réel du second tour",
                xaxis_title="Candidat",
                yaxis_title="Part des exprimés T2 (%)",
                **PLOT_LAYOUT_THEME,
            )
            final_chart.update_yaxes(ticksuffix=" %")
            st.plotly_chart(final_chart, width="stretch", config={"displayModeBar": False, "responsive": True})

            st.dataframe(
                selected_final[["candidate_name", "force_label", "nuance", "voix", "share_exprimes_t2", "rank_t2"]].rename(
                    columns={
                        "candidate_name": "Candidat T2",
                        "force_label": "Force",
                        "nuance": "Nuance",
                        "voix": "Voix T2",
                        "share_exprimes_t2": "% exprimés T2",
                        "rank_t2": "Rang T2",
                    }
                ),
                width="stretch",
                hide_index=True,
                column_config={
                    "% exprimés T2": st.column_config.NumberColumn("% exprimés T2", format="%.2f %%"),
                },
            )
        return

    official = _load_official_general_results()
    circo = _build_official_constituency_results(official)
    if circo.empty:
        st.warning("Je n’ai pas trouvé de résultats officiels 2024 exploitables dans les fichiers envoyés.")
        return

    aggregation_level = str(circo["aggregation_level"].iloc[0]) if "aggregation_level" in circo.columns else "commune"
    if aggregation_level == "circonscription":
        title = "Résultats officiels 2024 par circonscription"
        search_label = "Recherche circonscription / ville / département / numéro / tour"
        search_placeholder = "Exemples : 59, nord, 10e, paris, marseille, 1er tour, circo 3"
        count_label = "Circonscriptions"
    else:
        title = "Résultats officiels 2024 issus des CSV bruts fournis"
        search_label = "Recherche commune / département / code INSEE / bureau / tour"
        search_placeholder = "Exemples : 01004, ambérieu, ain, 0001, 1er tour"
        count_label = "Communes"

    st.caption(
        "Les deux CSV fournis sont identiques. "
        f"Niveau détecté dans ces fichiers pour les législatives 2024 : {aggregation_level}."
    )

    query = st.text_input(
        search_label,
        key="analysis_2024_official_constituency_query",
        placeholder=search_placeholder,
    )
    filtered = circo.copy()
    normalized_query = _normalize_search_text(query)
    if normalized_query:
        tokens = normalized_query.split()
        filtered = filtered.loc[
            filtered["search_blob"].map(lambda blob: all(token in blob for token in tokens) if isinstance(blob, str) else False)
        ].copy()

    election_values = sorted(filtered["id_election"].dropna().astype(str).unique().tolist())
    election_options = ["Tous", *election_values]
    department_options = ["Tous"] + sorted(filtered["libelle_departement"].dropna().astype(str).unique().tolist())
    c1, c2 = st.columns(2)
    selected_election = c1.selectbox(
        "Tour officiel",
        election_options,
        key="analysis_2024_official_constituency_election",
        format_func=lambda value: "Tous" if value == "Tous" else _election_label(value),
    )
    selected_department = c2.selectbox(
        "Département",
        department_options,
        key="analysis_2024_official_constituency_department",
    )

    if selected_election != "Tous":
        filtered = filtered.loc[filtered["id_election"] == selected_election]
    if selected_department != "Tous":
        filtered = filtered.loc[filtered["libelle_departement"] == selected_department]

    col1, col2, col3, col4 = st.columns(4)
    col1.metric(count_label, int(len(filtered)))
    col2.metric("Départements", int(filtered["code_departement"].nunique()) if "code_departement" in filtered.columns else 0)
    col3.metric("Inscrits cumulés", int(filtered["inscrits"].sum()) if "inscrits" in filtered.columns else 0)
    col4.metric("Exprimés cumulés", int(filtered["exprimes"].sum()) if "exprimes" in filtered.columns else 0)

    display = filtered.rename(
        columns={
            "id_election": "Tour",
            "code_departement": "Code département",
            "libelle_departement": "Département",
            "code_circonscription": "N° circonscription",
            "libelle_circonscription": "Libellé circonscription",
            "code_commune": "Code commune",
            "libelle_commune": "Commune",
            "inscrits": "Inscrits",
            "abstentions": "Abstentions",
            "votants": "Votants",
            "blancs": "Blancs",
            "nuls": "Nuls",
            "exprimes": "Exprimés",
            "participation": "Participation",
            "abstention": "Abstention",
            "expression": "Exprimes / votants",
        }
    )
    if "Tour" in display.columns:
        display["Tour"] = display["Tour"].map(_election_label)
    st.markdown(f"**{title}**")
    if aggregation_level == "circonscription":
        unit_label_column = "Libellé circonscription"
    else:
        unit_label_column = "Commune"

    top_units = (
        display.sort_values("Exprimés", ascending=False)
        .head(20)
        .sort_values("Exprimés", ascending=True)
    )
    expressed_chart = go.Figure(
        go.Bar(
            x=top_units["Exprimés"],
            y=top_units[unit_label_column],
            orientation="h",
            marker_color="#5a7bd8",
        )
    )
    expressed_chart.update_layout(
        title=f"Top 20 {aggregation_level}s par votes exprimés",
        xaxis_title="Votes exprimés",
        yaxis_title=aggregation_level.capitalize(),
        **PLOT_LAYOUT_THEME,
    )
    st.plotly_chart(expressed_chart, width="stretch", config={"displayModeBar": False, "responsive": True})

    participation_chart = go.Figure(
        go.Histogram(
            x=display["Participation"],
            nbinsx=24,
            marker_color="#d34a6a",
            opacity=0.85,
        )
    )
    participation_chart.update_layout(
        title=f"Distribution de la participation par {aggregation_level}",
        xaxis_title="Participation (%)",
        yaxis_title=f"Nombre de {aggregation_level}s",
        **PLOT_LAYOUT_THEME,
    )
    participation_chart.update_xaxes(ticksuffix=" %")
    st.plotly_chart(participation_chart, width="stretch", config={"displayModeBar": False, "responsive": True})

    dept_summary = (
        display.groupby("Département", dropna=False)
        .agg(
            exprimes=("Exprimés", "sum"),
            inscrits=("Inscrits", "sum"),
            votants=("Votants", "sum"),
        )
        .reset_index()
    )
    dept_summary["participation"] = _safe_percent(dept_summary["votants"], dept_summary["inscrits"])
    dept_summary = dept_summary.sort_values("exprimes", ascending=False).head(20).sort_values("exprimes", ascending=True)

    dept_chart = go.Figure()
    dept_chart.add_trace(
        go.Bar(
            x=dept_summary["exprimes"],
            y=dept_summary["Département"],
            orientation="h",
            name="Exprimés",
            marker_color="#7c5ea8",
        )
    )
    dept_chart.add_trace(
        go.Scatter(
            x=dept_summary["exprimes"],
            y=dept_summary["Département"],
            mode="markers+text",
            text=[f"{value:.1f} %" for value in dept_summary["participation"]],
            textposition="middle right",
            marker={"size": 8, "color": "#111111"},
            name="Participation",
            hovertemplate="%{y}<br>Participation: %{text}<extra></extra>",
        )
    )
    dept_chart.update_layout(
        title="Départements les plus lourds dans les fichiers fournis",
        xaxis_title="Votes exprimés cumulés",
        yaxis_title="Département",
        **PLOT_LAYOUT_THEME,
    )
    st.plotly_chart(dept_chart, width="stretch", config={"displayModeBar": False, "responsive": True})

    unit_options = sorted(display[unit_label_column].dropna().astype(str).unique().tolist())
    if unit_options:
        selected_unit = st.selectbox(
            f"{aggregation_level.capitalize()} détaillée",
            unit_options,
            key="analysis_2024_official_selected_unit",
        )
        selected_unit_rows = display.loc[display[unit_label_column] == selected_unit].copy()
        if not selected_unit_rows.empty:
            detail_chart = go.Figure()
            for metric, color in [
                ("Inscrits", "#7c5ea8"),
                ("Votants", "#5a7bd8"),
                ("Exprimés", "#d34a6a"),
            ]:
                if metric in selected_unit_rows.columns:
                    detail_chart.add_trace(
                        go.Bar(
                            x=selected_unit_rows["Tour"],
                            y=selected_unit_rows[metric],
                            name=metric,
                            marker_color=color,
                        )
                    )
            detail_chart.update_layout(
                title=f"{selected_unit} · résultats officiels par tour",
                barmode="group",
                xaxis_title="Tour",
                yaxis_title="Votes",
                **PLOT_LAYOUT_THEME,
            )
            st.plotly_chart(detail_chart, width="stretch", config={"displayModeBar": False, "responsive": True})

            turnout_line = go.Figure(
                go.Scatter(
                    x=selected_unit_rows["Tour"],
                    y=selected_unit_rows["Participation"],
                    mode="lines+markers+text",
                    text=[f"{value:.1f} %" for value in selected_unit_rows["Participation"]],
                    textposition="top center",
                    line={"color": "#111111", "width": 2},
                    marker={"size": 8, "color": "#111111"},
                )
            )
            turnout_line.update_layout(
                title=f"{selected_unit} · participation par tour",
                xaxis_title="Tour",
                yaxis_title="Participation (%)",
                **PLOT_LAYOUT_THEME,
            )
            turnout_line.update_yaxes(ticksuffix=" %")
            st.plotly_chart(turnout_line, width="stretch", config={"displayModeBar": False, "responsive": True})


def _render_official_circo_zip_results(frame: pd.DataFrame) -> None:
    working = frame.copy()
    numeric_columns = [
        "Code département",
        "Code circonscription législative",
        "Inscrits",
        "Votants",
        "Abstentions",
        "Exprimés",
        "Blancs",
        "Nuls",
    ]
    for column in numeric_columns:
        if column in working.columns:
            working[column] = pd.to_numeric(working[column], errors="coerce")

    search_blob = (
        working["Code département"].astype("Int64").astype(str).fillna("")
        + " "
        + working["Libellé département"].fillna("").astype(str)
        + " "
        + working["Code circonscription législative"].astype("Int64").astype(str).fillna("")
        + " "
        + working["Libellé circonscription législative"].fillna("").astype(str)
    )
    working["search_blob"] = search_blob.map(_normalize_search_text)

    query = st.text_input(
        "Recherche circonscription / département / numéro",
        key="analysis_2024_zip_circo_query",
        placeholder="Exemples : aisne, 203, 3e circonscription, nord, 10e",
    )
    filtered = working.copy()
    normalized_query = _normalize_search_text(query)
    if normalized_query:
        tokens = normalized_query.split()
        filtered = filtered.loc[
            filtered["search_blob"].map(lambda blob: all(token in blob for token in tokens))
        ].copy()

    department_options = ["Tous"] + sorted(filtered["Libellé département"].dropna().astype(str).unique().tolist())
    selected_department = st.selectbox(
        "Département",
        department_options,
        key="analysis_2024_zip_circo_department",
    )
    if selected_department != "Tous":
        filtered = filtered.loc[filtered["Libellé département"] == selected_department].copy()

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Circonscriptions", int(len(filtered)))
    col2.metric("Départements", int(filtered["Code département"].nunique()))
    col3.metric("Inscrits cumulés", int(filtered["Inscrits"].sum()))
    col4.metric("Exprimés cumulés", int(filtered["Exprimés"].sum()))

    top_circo = filtered.sort_values("Exprimés", ascending=False).head(20).sort_values("Exprimés", ascending=True)
    overview = go.Figure(
        go.Bar(
            x=top_circo["Exprimés"],
            y=top_circo["Libellé département"].astype(str) + " · " + top_circo["Libellé circonscription législative"].astype(str),
            orientation="h",
            marker_color="#5a7bd8",
        )
    )
    overview.update_layout(
        title="Circonscriptions les plus lourdes en votes exprimés",
        xaxis_title="Votes exprimés",
        yaxis_title="Circonscription",
        **PLOT_LAYOUT_THEME,
    )
    st.plotly_chart(overview, width="stretch", config={"displayModeBar": False, "responsive": True})

    filtered["participation_calc"] = _safe_percent(filtered["Votants"], filtered["Inscrits"])
    turnout = go.Figure(
        go.Histogram(
            x=filtered["participation_calc"],
            nbinsx=24,
            marker_color="#d34a6a",
        )
    )
    turnout.update_layout(
        title="Distribution de la participation par circonscription",
        xaxis_title="Participation (%)",
        yaxis_title="Nombre de circonscriptions",
        **PLOT_LAYOUT_THEME,
    )
    turnout.update_xaxes(ticksuffix=" %")
    st.plotly_chart(turnout, width="stretch", config={"displayModeBar": False, "responsive": True})

    filtered["circo_label"] = (
        filtered["Libellé département"].astype(str)
        + " · "
        + filtered["Libellé circonscription législative"].astype(str)
    )
    circo_options = sorted(filtered["circo_label"].dropna().unique().tolist())
    if not circo_options:
        st.warning("Aucune circonscription disponible avec ce filtre.")
        return
    selected_circo = st.selectbox(
        "Circonscription détaillée",
        circo_options,
        index=0,
        key="analysis_2024_zip_circo_selected",
    )
    detail_rows = filtered.loc[filtered["circo_label"] == selected_circo].copy()
    if detail_rows.empty:
        selected_circo = circo_options[0]
        detail_rows = filtered.loc[filtered["circo_label"] == selected_circo].copy()
    if detail_rows.empty:
        st.warning("Impossible de charger le détail de la circonscription sélectionnée.")
        return
    detail = detail_rows.iloc[0]

    candidate_rows = []
    for idx in range(1, 20):
        name = detail.get(f"Nom candidat {idx}")
        first_name = detail.get(f"Prénom candidat {idx}")
        nuance = detail.get(f"Nuance candidat {idx}")
        voix = detail.get(f"Voix {idx}")
        share = detail.get(f"% Voix/exprimés {idx}")
        if pd.isna(name) or pd.isna(voix):
            continue
        candidate_rows.append(
            {
                "candidat": f"{first_name} {name}".strip(),
                "nuance": nuance,
                "voix": pd.to_numeric(voix, errors="coerce"),
                "part": float(str(share).replace("%", "").replace(",", ".")) if pd.notna(share) else 0.0,
                "elu": str(detail.get(f"Elu {idx}") or "").strip().lower() == "élu",
            }
        )
    candidates = pd.DataFrame(candidate_rows).sort_values("voix", ascending=True)
    if not candidates.empty:
        candidate_chart = go.Figure(
            go.Bar(
                x=candidates["voix"],
                y=candidates["candidat"] + " · " + candidates["nuance"].fillna(""),
                orientation="h",
                marker_color=["#d34a6a" if elected else "#5a7bd8" for elected in candidates["elu"]],
                text=[f"{value:.1f} %" for value in candidates["part"]],
                textposition="outside",
            )
        )
        candidate_chart.update_layout(
            title=f"{selected_circo} · résultat candidat par candidat",
            xaxis_title="Voix",
            yaxis_title="Candidat",
            **PLOT_LAYOUT_THEME,
        )
        st.plotly_chart(candidate_chart, width="stretch", config={"displayModeBar": False, "responsive": True})

    totals = go.Figure(
        go.Bar(
            x=["Inscrits", "Votants", "Exprimés", "Abstentions", "Blancs", "Nuls"],
            y=[
                float(detail["Inscrits"]),
                float(detail["Votants"]),
                float(detail["Exprimés"]),
                float(detail["Abstentions"]),
                float(detail["Blancs"]),
                float(detail["Nuls"]),
            ],
            marker_color=["#7c5ea8", "#5a7bd8", "#d34a6a", "#999999", "#d9c2f0", "#bdbdbd"],
        )
    )
    totals.update_layout(
        title=f"{selected_circo} · participation et structure du vote",
        xaxis_title="Indicateur",
        yaxis_title="Voix",
        **PLOT_LAYOUT_THEME,
    )
    st.plotly_chart(totals, width="stretch", config={"displayModeBar": False, "responsive": True})


def _build_2027_first_round_blocs(frame: pd.DataFrame, reference_dir: Path) -> pd.DataFrame:
    first_round = frame.loc[(frame["round"] == "first_round") & (~frame["is_generic_bloc"])].copy()
    if first_round.empty:
        return pd.DataFrame()
    corrected, _context = apply_dynamic_poll_bias_correction(first_round, reference_dir)
    if corrected.empty:
        return pd.DataFrame()

    corrected["publication_date"] = pd.to_datetime(corrected["publication_date"], errors="coerce")
    latest_date = corrected["publication_date"].max()
    if pd.isna(latest_date):
        recent = corrected.copy()
    else:
        recent = corrected.loc[corrected["publication_date"] >= latest_date - pd.Timedelta(days=120)].copy()
        if recent.empty:
            recent = corrected.copy()

    scenario_blocs = (
        recent.groupby(
            ["publication_date", "polling_company", "scenario_name", "broad_bloc"],
            dropna=False,
        )["dynamically_corrected_estimate"]
        .sum()
        .reset_index()
    )
    totals = scenario_blocs.groupby(["publication_date", "polling_company", "scenario_name"], dropna=False)[
        "dynamically_corrected_estimate"
    ].sum().rename("scenario_total")
    scenario_blocs = scenario_blocs.merge(
        totals.reset_index(),
        on=["publication_date", "polling_company", "scenario_name"],
        how="left",
    )
    scenario_blocs["bloc_share_percent"] = _safe_percent(
        scenario_blocs["dynamically_corrected_estimate"],
        scenario_blocs["scenario_total"],
    )
    scenario_blocs["scenario_label"] = scenario_blocs.apply(
        lambda row: f"{row['publication_date']:%d/%m/%Y} · {row['polling_company']} · {row['scenario_name']}",
        axis=1,
    )
    return scenario_blocs.sort_values(["publication_date", "polling_company", "scenario_name", "broad_bloc"]).reset_index(drop=True)


def _build_2027_first_round_forces(frame: pd.DataFrame, reference_dir: Path) -> pd.DataFrame:
    first_round = frame.loc[(frame["round"] == "first_round") & (~frame["is_generic_bloc"])].copy()
    if first_round.empty:
        return pd.DataFrame()
    corrected, _context = apply_dynamic_poll_bias_correction(first_round, reference_dir)
    if corrected.empty:
        return pd.DataFrame()
    corrected["publication_date"] = pd.to_datetime(corrected["publication_date"], errors="coerce")
    latest_date = corrected["publication_date"].max()
    if pd.isna(latest_date):
        recent = corrected.copy()
    else:
        recent = corrected.loc[corrected["publication_date"] >= latest_date - pd.Timedelta(days=120)].copy()
        if recent.empty:
            recent = corrected.copy()
    recent["force_display"] = recent.apply(
        lambda row: f"{row['candidate_name']} ({row['force_label']})" if pd.notna(row.get("candidate_name")) else str(row["force_label"]),
        axis=1,
    )
    recent["scenario_label"] = recent.apply(
        lambda row: f"{row['publication_date']:%d/%m/%Y} · {row['polling_company']} · {row['scenario_name']}",
        axis=1,
    )
    return recent


def _build_2027_second_round_duels(frame: pd.DataFrame) -> pd.DataFrame:
    second_round = frame.loc[(frame["round"] == "second_round") & (~frame["is_generic_bloc"])].copy()
    if second_round.empty:
        return pd.DataFrame()
    second_round["publication_date"] = pd.to_datetime(second_round["publication_date"], errors="coerce")
    latest_date = second_round["publication_date"].max()
    if pd.notna(latest_date):
        second_round = second_round.loc[second_round["publication_date"] >= latest_date - pd.Timedelta(days=180)].copy()
    second_round["candidate_display"] = second_round.apply(
        lambda row: f"{row['candidate_name']} ({row['candidate_party']})" if pd.notna(row.get("candidate_party")) else str(row["candidate_name"]),
        axis=1,
    )
    second_round["broad_bloc"] = second_round.apply(
        lambda row: normalize_broad_bloc(row.get("candidate_party"), row.get("political_family")),
        axis=1,
    )
    grouped = []
    for (publication_date, polling_company, scenario_name), group in second_round.groupby(
        ["publication_date", "polling_company", "scenario_name"],
        dropna=False,
    ):
        ordered = group.sort_values("estimate_percent", ascending=False).reset_index(drop=True)
        if len(ordered.index) != 2:
            continue
        grouped.append(
            {
                "publication_date": publication_date,
                "polling_company": polling_company,
                "scenario_name": scenario_name,
                "candidate_a": ordered.loc[0, "candidate_display"],
                "candidate_b": ordered.loc[1, "candidate_display"],
                "score_a": float(ordered.loc[0, "estimate_percent"]),
                "score_b": float(ordered.loc[1, "estimate_percent"]),
                "margin": float(ordered.loc[0, "estimate_percent"]) - float(ordered.loc[1, "estimate_percent"]),
                "duel_label": f"{ordered.loc[0, 'candidate_display']} vs {ordered.loc[1, 'candidate_display']}",
                "bloc_a": str(ordered.loc[0, "broad_bloc"]),
                "bloc_b": str(ordered.loc[1, "broad_bloc"]),
            }
        )
    return pd.DataFrame(grouped).sort_values(["publication_date", "polling_company", "scenario_name"], ascending=[False, True, True]).reset_index(drop=True)


def _render_2027_duel_type_analysis(forces: pd.DataFrame, duels: pd.DataFrame) -> None:
    st.markdown("**Typologie des duels et triangulaires**")
    if not duels.empty:
        duel_types = duels.copy()
        duel_types["duel_type"] = duel_types.apply(
            lambda row: " vs ".join(sorted([_bloc_label(str(row["bloc_a"])), _bloc_label(str(row["bloc_b"]))])),
            axis=1,
        )
        latest_by_type = (
            duel_types.sort_values(["publication_date", "polling_company"], ascending=[False, True])
            .groupby("duel_type", dropna=False)
            .head(1)
            .sort_values("margin", ascending=True)
        )
        duel_type_chart = go.Figure(
            go.Bar(
                x=latest_by_type["margin"],
                y=latest_by_type["duel_type"],
                orientation="h",
                marker_color="#d34a6a",
                customdata=latest_by_type[["duel_label", "score_a", "score_b"]].to_numpy(),
                hovertemplate="Type: %{y}<br>Duel: %{customdata[0]}<br>Ecart: %{x:.1f} pts<br>A: %{customdata[1]:.1f}%<br>B: %{customdata[2]:.1f}%<extra></extra>",
            )
        )
        duel_type_chart.update_layout(
            title="Dernier point connu par type de duel",
            xaxis_title="Ecart entre les deux finalistes (points)",
            yaxis_title="Type de duel",
            **PLOT_LAYOUT_THEME,
        )
        st.plotly_chart(duel_type_chart, width="stretch", config={"displayModeBar": False, "responsive": True})

    if forces.empty:
        return

    tri_rows = []
    for scenario_label, group in forces.groupby("scenario_label", dropna=False):
        ordered = group.sort_values("dynamically_corrected_estimate", ascending=False).reset_index(drop=True)
        if len(ordered.index) < 3:
            continue
        top_three = ordered.head(3).copy()
        tri_rows.append(
            {
                "scenario_label": scenario_label,
                "triangulaire_type": " / ".join(_bloc_label(str(bloc)) for bloc in top_three["broad_bloc"].tolist()),
                "leader": str(top_three.iloc[0]["force_display"]),
                "second": str(top_three.iloc[1]["force_display"]),
                "third": str(top_three.iloc[2]["force_display"]),
                "leader_score": float(top_three.iloc[0]["dynamically_corrected_estimate"]),
                "second_score": float(top_three.iloc[1]["dynamically_corrected_estimate"]),
                "third_score": float(top_three.iloc[2]["dynamically_corrected_estimate"]),
            }
        )
    triangulaires = pd.DataFrame(tri_rows)
    if triangulaires.empty:
        st.info("Aucune triangulaire exploitable dans les scénarios retenus.")
        return

    tri_counts = (
        triangulaires.groupby("triangulaire_type", dropna=False)
        .size()
        .rename("count")
        .reset_index()
        .sort_values("count", ascending=False)
    )
    tri_count_chart = go.Figure(
        go.Bar(
            x=tri_counts["triangulaire_type"],
            y=tri_counts["count"],
            marker_color="#7c5ea8",
        )
    )
    tri_count_chart.update_layout(
        title="Configurations de triangulaire observées dans les scénarios 2027",
        xaxis_title="Type de triangulaire",
        yaxis_title="Nombre de scénarios",
        **PLOT_LAYOUT_THEME,
    )
    st.plotly_chart(tri_count_chart, width="stretch", config={"displayModeBar": False, "responsive": True})

    tri_choice = st.selectbox(
        "Triangulaire détaillée",
        tri_counts["triangulaire_type"].tolist(),
        key="analysis_2024_projection_triangulaire_choice",
    )
    tri_detail = triangulaires.loc[triangulaires["triangulaire_type"] == tri_choice].copy()
    if not tri_detail.empty:
        tri_detail_chart = go.Figure()
        tri_detail_chart.add_trace(
            go.Bar(
                x=tri_detail["scenario_label"],
                y=tri_detail["leader_score"],
                name="1er",
                marker_color="#d34a6a",
            )
        )
        tri_detail_chart.add_trace(
            go.Bar(
                x=tri_detail["scenario_label"],
                y=tri_detail["second_score"],
                name="2e",
                marker_color="#5a7bd8",
            )
        )
        tri_detail_chart.add_trace(
            go.Bar(
                x=tri_detail["scenario_label"],
                y=tri_detail["third_score"],
                name="3e",
                marker_color="#7c5ea8",
            )
        )
        tri_detail_chart.update_layout(
            title=f"{tri_choice} · scores des trois forces dans les scénarios retenus",
            barmode="group",
            xaxis_title="Scénario",
            yaxis_title="Score corrigé (%)",
            **PLOT_LAYOUT_THEME,
        )
        tri_detail_chart.update_yaxes(ticksuffix=" %")
        st.plotly_chart(tri_detail_chart, width="stretch", config={"displayModeBar": False, "responsive": True})


def _render_2027_force_and_duel_analysis(frame: pd.DataFrame, reference_dir: Path) -> None:
    forces = _build_2027_first_round_forces(frame, reference_dir)
    duels = _build_2027_second_round_duels(frame)
    if forces.empty:
        st.info("Aucune base 2027 exploitable au niveau force.")
        return

    scenario_options = (
        forces[["publication_date", "scenario_label"]]
        .drop_duplicates()
        .sort_values(["publication_date", "scenario_label"], ascending=[False, True])["scenario_label"]
        .tolist()
    )
    selected_scenario = st.selectbox(
        "Scénario 2027 détaillé par force",
        scenario_options,
        key="analysis_2024_projection_force_scenario",
    )
    selected = (
        forces.loc[forces["scenario_label"] == selected_scenario]
        .sort_values("dynamically_corrected_estimate", ascending=False)
        .reset_index(drop=True)
    )
    if selected.empty:
        return

    force_chart = go.Figure(
        go.Bar(
            x=selected["force_display"],
            y=selected["dynamically_corrected_estimate"],
            marker_color=[_bloc_color(bloc) for bloc in selected["broad_bloc"]],
            text=[f"{value:.1f} %" for value in selected["dynamically_corrected_estimate"]],
            textposition="outside",
        )
    )
    force_chart.update_layout(
        title="Projection 2027 · premier tour détaillé par force / candidat",
        xaxis_title="Force",
        yaxis_title="Score corrigé (%)",
        **PLOT_LAYOUT_THEME,
    )
    force_chart.update_yaxes(ticksuffix=" %")
    st.plotly_chart(force_chart, width="stretch", config={"displayModeBar": False, "responsive": True})

    top_three = selected.head(3).copy()
    if not top_three.empty:
        tri_chart = go.Figure(
            go.Pie(
                labels=top_three["force_display"],
                values=top_three["dynamically_corrected_estimate"],
                hole=0.45,
                marker={"colors": [_bloc_color(bloc) for bloc in top_three["broad_bloc"]]},
            )
        )
        tri_chart.update_layout(
            title="Configuration à trois forces dominante dans le scénario retenu",
            **PLOT_LAYOUT_THEME,
        )
        st.plotly_chart(tri_chart, width="stretch", config={"displayModeBar": False, "responsive": True})

    if duels.empty:
        st.info("Aucun duel 2027 exploitable dans les sondages bruts.")
        return

    latest_by_duel = (
        duels.sort_values(["publication_date", "polling_company"])
        .groupby("duel_label", dropna=False)
        .head(1)
        .copy()
        .sort_values("margin", ascending=True)
    )
    duel_overview = go.Figure(
        go.Bar(
            x=latest_by_duel["margin"],
            y=latest_by_duel["duel_label"],
            orientation="h",
            marker_color=["#d34a6a" if value >= 0 else "#5a7bd8" for value in latest_by_duel["margin"]],
            customdata=latest_by_duel[["score_a", "score_b", "polling_company", "publication_date"]].to_numpy(),
            hovertemplate="%{y}<br>Ecart: %{x:.1f} pts<br>A: %{customdata[0]:.1f}%<br>B: %{customdata[1]:.1f}%<br>Institut: %{customdata[2]}<br>Date: %{customdata[3]|%d/%m/%Y}<extra></extra>",
        )
    )
    duel_overview.update_layout(
        title="Tous les duels 2027 mesurés · dernier point connu",
        xaxis_title="Ecart entre les deux finalistes (points)",
        yaxis_title="Duel",
        **PLOT_LAYOUT_THEME,
    )
    st.plotly_chart(duel_overview, width="stretch", config={"displayModeBar": False, "responsive": True})

    duel_choice = st.selectbox(
        "Duel détaillé",
        latest_by_duel["duel_label"].tolist(),
        key="analysis_2024_projection_duel_detail_choice",
    )
    duel_detail = duels.loc[duels["duel_label"] == duel_choice].sort_values("publication_date").copy()
    if not duel_detail.empty:
        timeline = go.Figure()
        timeline.add_trace(
            go.Scatter(
                x=duel_detail["publication_date"],
                y=duel_detail["score_a"],
                mode="lines+markers",
                name=duel_detail["candidate_a"].iloc[0],
                line={"color": "#d34a6a", "width": 3},
            )
        )
        timeline.add_trace(
            go.Scatter(
                x=duel_detail["publication_date"],
                y=duel_detail["score_b"],
                mode="lines+markers",
                name=duel_detail["candidate_b"].iloc[0],
                line={"color": "#5a7bd8", "width": 3},
            )
        )
        timeline.update_layout(
            title=f"{duel_choice} · évolution mesurée",
            xaxis_title="Date de publication",
            yaxis_title="Score (%)",
            **PLOT_LAYOUT_THEME,
        )
        timeline.update_yaxes(ticksuffix=" %")
        st.plotly_chart(timeline, width="stretch", config={"displayModeBar": False, "responsive": True})

    _render_2027_duel_type_analysis(forces, duels)


def _render_2027_projection_from_2024_logic(frame: pd.DataFrame, reference_dir: Path) -> None:
    scenario_blocs = _build_2027_first_round_blocs(frame, reference_dir)
    if scenario_blocs.empty:
        st.info("Aucune base 2027 exploitable pour projeter le premier tour et les reports du second tour.")
        return

    scenario_options = (
        scenario_blocs[["publication_date", "scenario_label"]]
        .drop_duplicates()
        .sort_values(["publication_date", "scenario_label"], ascending=[False, True])["scenario_label"]
        .tolist()
    )
    selected_scenario = st.selectbox(
        "Scénario 2027 retenu pour l’estimation",
        scenario_options,
        key="analysis_2024_projection_2027_scenario",
    )
    selected = scenario_blocs.loc[scenario_blocs["scenario_label"] == selected_scenario].copy()
    if selected.empty:
        st.warning("Le scénario 2027 sélectionné est vide.")
        return

    selected["Bloc"] = selected["broad_bloc"].map(_bloc_label)
    selected = selected.sort_values("bloc_share_percent", ascending=False).reset_index(drop=True)
    top_two_blocs = selected["broad_bloc"].head(2).tolist()
    default_duel = f"{_bloc_label(top_two_blocs[0])} vs {_bloc_label(top_two_blocs[1])}" if len(top_two_blocs) == 2 else None

    first_round_chart = go.Figure(
        go.Bar(
            x=selected["Bloc"],
            y=selected["bloc_share_percent"],
            marker_color=[_bloc_color(bloc) for bloc in selected["broad_bloc"]],
            customdata=selected[["polling_company", "publication_date"]].to_numpy(),
            hovertemplate="Bloc: %{x}<br>Score projeté T1: %{y:.1f}%<br>Institut: %{customdata[0]}<br>Date: %{customdata[1]|%d/%m/%Y}<extra></extra>",
        )
    )
    first_round_chart.update_layout(
        title="Premier tour 2027 par bloc",
        xaxis_title="Bloc",
        yaxis_title="Part (%)",
        **PLOT_LAYOUT_THEME,
    )
    first_round_chart.update_yaxes(ticksuffix=" %")
    st.plotly_chart(first_round_chart, width="stretch", config={"displayModeBar": False, "responsive": True})

    duel_options = []
    if len(top_two_blocs) == 2:
        duel_options.append(default_duel)
    duel_options.extend(
        [
            "Gauche / NFP vs RN",
            "Centre / Ensemble vs RN",
            "Droite / LR vs RN",
            "Gauche / NFP vs Centre / Ensemble",
        ]
    )
    duel_options = list(dict.fromkeys([option for option in duel_options if option is not None]))
    selected_duel = st.selectbox(
        "Duel final projeté",
        duel_options,
        key="analysis_2024_projection_2027_duel",
    )
    if selected_duel == default_duel and len(top_two_blocs) == 2:
        bloc_a, bloc_b = top_two_blocs[0], top_two_blocs[1]
    else:
        reverse_map = {label: blocs for label, blocs in DUEL_OPTION_TO_BLOCS.items()}
        bloc_a, bloc_b = reverse_map.get(selected_duel, (top_two_blocs[0], top_two_blocs[1]))

    transfer_rows: list[dict[str, object]] = []
    for row in selected.itertuples(index=False):
        transfer_map = get_second_round_coalition_2024_transfer_map(str(row.broad_bloc), bloc_a, bloc_b)
        transfer_rows.append(
            {
                "source_bloc": str(row.broad_bloc),
                "source_share": float(row.bloc_share_percent),
                "to_a_points": float(row.bloc_share_percent) * float(transfer_map.get(bloc_a, 0.0)),
                "to_b_points": float(row.bloc_share_percent) * float(transfer_map.get(bloc_b, 0.0)),
            }
        )
    transfer_frame = pd.DataFrame(transfer_rows)
    score_a = float(transfer_frame["to_a_points"].sum())
    score_b = float(transfer_frame["to_b_points"].sum())
    total_duel = score_a + score_b
    if total_duel > 0:
        duel_a = score_a / total_duel * 100.0
        duel_b = score_b / total_duel * 100.0
    else:
        duel_a = 0.0
        duel_b = 0.0

    col1, col2, col3 = st.columns(3)
    col1.metric("Bloc en tête au T1", _bloc_label(str(selected.iloc[0]["broad_bloc"])), f"{float(selected.iloc[0]['bloc_share_percent']):.1f} %")
    col2.metric("Finaliste A projeté", _bloc_label(bloc_a), f"{duel_a:.1f} %")
    col3.metric("Finaliste B projeté", _bloc_label(bloc_b), f"{duel_b:.1f} %")

    runoff_chart = go.Figure()
    runoff_chart.add_trace(
        go.Bar(
            x=transfer_frame["source_bloc"].map(_bloc_label),
            y=transfer_frame["to_a_points"],
            name=_bloc_label(bloc_a),
            marker_color=_bloc_color(bloc_a),
        )
    )
    runoff_chart.add_trace(
        go.Bar(
            x=transfer_frame["source_bloc"].map(_bloc_label),
            y=transfer_frame["to_b_points"],
            name=_bloc_label(bloc_b),
            marker_color=_bloc_color(bloc_b),
        )
    )
    runoff_chart.update_layout(
        title=f"Projection 2027 · reports estimés vers le duel {_bloc_label(bloc_a)} vs {_bloc_label(bloc_b)}",
        barmode="stack",
        xaxis_title="Bloc source du premier tour",
        yaxis_title="Points reportés",
        **PLOT_LAYOUT_THEME,
    )
    st.plotly_chart(runoff_chart, width="stretch", config={"displayModeBar": False, "responsive": True})

    duel_chart = go.Figure(
        go.Bar(
            x=[_bloc_label(bloc_a), _bloc_label(bloc_b)],
            y=[duel_a, duel_b],
            marker_color=[_bloc_color(bloc_a), _bloc_color(bloc_b)],
            text=[f"{duel_a:.1f} %", f"{duel_b:.1f} %"],
            textposition="outside",
        )
    )
    duel_chart.update_layout(
        title="Projection 2027 · second tour final estimé",
        xaxis_title="Finaliste",
        yaxis_title="Part (%)",
        **PLOT_LAYOUT_THEME,
    )
    duel_chart.update_yaxes(ticksuffix=" %")
    st.plotly_chart(duel_chart, width="stretch", config={"displayModeBar": False, "responsive": True})


def _render_official_dataset() -> None:
    official = _load_official_general_results()
    if official.empty:
        st.warning("Je n’ai pas trouvé de fichier officiel `general_results*.csv` exploitable localement.")
        return

    official["search_blob"] = official.apply(_build_official_search_blob, axis=1)
    query = st.text_input(
        "Recherche libre dans le dataset officiel 2024",
        key="analysis_2024_official_dataset_query",
        placeholder="Exemples : 1er tour, nord, 59, nice, 6, paris, circonscription, bureau",
    )
    filtered = official.copy()
    normalized_query = _normalize_search_text(query)
    if normalized_query:
        tokens = normalized_query.split()
        filtered = filtered.loc[
            filtered["search_blob"].map(lambda blob: all(token in blob for token in tokens) if isinstance(blob, str) else False)
        ].copy()

    election_values = sorted(filtered["id_election"].dropna().astype(str).unique().tolist())
    election_options = ["Tous", *election_values]
    department_options = ["Tous"] + sorted(filtered["libelle_departement"].dropna().astype(str).unique().tolist())
    level_options = ["Tous", "Bureaux de vote", "Communes", "Circonscriptions"]
    c1, c2, c3 = st.columns(3)
    selected_election = c1.selectbox(
        "Tour officiel",
        election_options,
        key="analysis_2024_official_dataset_election",
        format_func=lambda value: "Tous" if value == "Tous" else _election_label(value),
    )
    selected_department = c2.selectbox("Département", department_options, key="analysis_2024_official_dataset_department")
    selected_level = c3.selectbox("Niveau", level_options, key="analysis_2024_official_dataset_level")

    if selected_election != "Tous":
        filtered = filtered.loc[filtered["id_election"] == selected_election]
    if selected_department != "Tous":
        filtered = filtered.loc[filtered["libelle_departement"] == selected_department]
    if selected_level == "Bureaux de vote":
        filtered = filtered.loc[filtered["code_bv"].notna()]
    elif selected_level == "Communes":
        filtered = filtered.loc[filtered["code_commune"].notna() & filtered["code_bv"].isna()]
    elif selected_level == "Circonscriptions":
        filtered = filtered.loc[filtered["code_circonscription"].notna() & filtered["code_commune"].isna()]

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Lignes officielles", int(len(filtered)))
    col2.metric("Départements", int(filtered["code_departement"].nunique()) if "code_departement" in filtered.columns else 0)
    col3.metric("Communes", int(filtered["code_commune"].nunique()) if "code_commune" in filtered.columns else 0)
    col4.metric("Circonscriptions", int(filtered["code_circonscription"].dropna().nunique()) if "code_circonscription" in filtered.columns else 0)

    display = filtered.drop(columns=["search_blob"]).copy()
    if "id_election" in display.columns:
        display["id_election"] = display["id_election"].map(_election_label)
    st.dataframe(
        display,
        width="stretch",
        hide_index=True,
    )


def _compute_mapbox_view(frame: pd.DataFrame) -> tuple[dict[str, float], float]:
    mapped = frame.dropna(subset=["latitude", "longitude"]).copy()
    if mapped.empty:
        return {"lat": 46.6, "lon": 2.1}, 4.2
    lat_min = float(mapped["latitude"].min())
    lat_max = float(mapped["latitude"].max())
    lon_min = float(mapped["longitude"].min())
    lon_max = float(mapped["longitude"].max())
    center = {"lat": (lat_min + lat_max) / 2.0, "lon": (lon_min + lon_max) / 2.0}
    span = max(lat_max - lat_min, lon_max - lon_min)
    if span > 40:
        zoom = 1.2
    elif span > 20:
        zoom = 2.1
    elif span > 10:
        zoom = 3.0
    elif span > 5:
        zoom = 4.0
    elif span > 2.5:
        zoom = 5.0
    else:
        zoom = 6.0
    return center, zoom


def _find_next_line(lines: list[str], start_idx: int, pattern: str) -> int | None:
    for idx in range(start_idx, len(lines)):
        if re.search(pattern, lines[idx], flags=re.IGNORECASE):
            return idx
    return None


def _parse_local_constituency_blocks() -> pd.DataFrame:
    visual_rows = _load_local_2024_visual_rows()
    if visual_rows.empty:
        return pd.DataFrame()

    ordered = visual_rows.sort_values(["page", "visual_row"]).reset_index(drop=True)
    constituency_pattern = re.compile(r"^\d+(?:re|e)\s+circonscription\s+", flags=re.IGNORECASE)
    stop_patterns = re.compile(r"^Projections sur second tour|^Projections en sièges", flags=re.IGNORECASE)

    blocks: list[tuple[str, list[str]]] = []
    current_name: str | None = None
    current_lines: list[str] = []
    for row in ordered.itertuples(index=False):
        text = str(row.row_text).strip()
        if not text:
            continue
        if stop_patterns.search(text):
            if current_name and current_lines:
                blocks.append((current_name, current_lines))
            current_name = None
            current_lines = []
            continue
        if constituency_pattern.match(text):
            if current_name and current_lines:
                blocks.append((current_name, current_lines))
            current_name = text
            current_lines = []
            continue
        if current_name:
            current_lines.append(text)
    if current_name and current_lines:
        blocks.append((current_name, current_lines))

    rows: list[dict[str, object]] = []
    for constituency_name, lines in blocks:
        first_round_idx = _find_next_line(lines, 0, r"^Premier tour$")
        second_round_idx = _find_next_line(lines, 0, r"^Second tour$")
        if first_round_idx is None:
            continue
        first_round_end = second_round_idx if second_round_idx is not None else len(lines)
        first_round_lines = lines[first_round_idx + 1:first_round_end]
        first_sondeur_idx = next((idx for idx, line in enumerate(first_round_lines) if "Sondeur Date Échantillon" in line), None)
        if first_sondeur_idx is None:
            continue
        first_header_lines = first_round_lines[:first_sondeur_idx]
        first_results_idx = next((idx for idx, line in enumerate(first_round_lines) if "30 juin 2024" in line and "%" in line), None)
        first_results_line = first_round_lines[first_results_idx] if first_results_idx is not None else ""
        first_poll_line = ""
        if first_results_idx is not None:
            first_poll_line = next(
                (
                    line
                    for idx, line in enumerate(first_round_lines)
                    if idx > first_results_idx and "Ifop" not in line and re.search(r"\d{1,2}(?:-\d{1,2})?\s+juin", line) and "%" in line
                ),
                "",
            )
        first_results_percentages = _extract_percentages(first_results_line)
        first_poll_percentages = _extract_percentages(first_poll_line)
        expected_count = len(first_results_percentages) or len(first_poll_percentages)
        first_round_tokens = _extract_party_tokens(first_header_lines, expected_count)

        if first_results_percentages and first_round_tokens:
            results_by_bloc = _aggregate_to_blocs(first_round_tokens, first_results_percentages)
            poll_by_bloc = _aggregate_to_blocs(first_round_tokens, first_poll_percentages) if first_poll_percentages else {}
            winning_token = first_round_tokens[first_results_percentages.index(max(first_results_percentages))]
            winning_bloc = _token_to_bloc(winning_token)
            department = _department_from_constituency(constituency_name)
            lat, lon = DEPARTMENT_CENTROIDS.get(department, (None, None))
            row = {
                "constituency_name": constituency_name,
                "department_name": department,
                "latitude": lat,
                "longitude": lon,
                "winning_label": winning_token,
                "winning_bloc": winning_bloc,
                "local_source_note": SECOND_ROUND_LOCAL_NOTES.get(constituency_name, "Circonscription locale présente dans les sources du repo."),
            }
            for bloc in FIVE_BLOC_ORDER:
                row[f"result_{bloc}"] = results_by_bloc.get(bloc, 0.0)
                row[f"poll_{bloc}"] = poll_by_bloc.get(bloc, 0.0) if poll_by_bloc else 0.0
            rows.append(row)

        if second_round_idx is not None and rows:
            second_round_lines = lines[second_round_idx + 1:]
            second_sondeur_idx = next((idx for idx, line in enumerate(second_round_lines) if "Sondeur Date Échantillon" in line), None)
            if second_sondeur_idx is not None:
                second_header_lines = second_round_lines[:second_sondeur_idx]
                second_tokens = _extract_party_tokens(second_header_lines, 6)
                triad_line = next((line for line in second_round_lines if re.fullmatch(r"(?:\d+(?:,\d+)?\s*%\s*){2,4}", line.strip())), "")
                duel_line = next((line for line in second_round_lines if re.search(r"-\s*\d+(?:,\d+)?\s*%\s+\d+(?:,\d+)?\s*%", line)), "")
                triad_percentages = _extract_percentages(triad_line)
                duel_percentages = _extract_percentages(duel_line)
                if not duel_percentages:
                    direct_duel_line = next(
                        (
                            line
                            for line in second_round_lines
                            if "Ifop" in line and len(_extract_percentages(line)) == 2
                        ),
                        "",
                    )
                    duel_percentages = _extract_percentages(direct_duel_line)
                if triad_percentages:
                    for idx, percentage in enumerate(triad_percentages[:3]):
                        rows[-1][f"second_round_config_{idx + 1}_label"] = second_tokens[idx] if idx < len(second_tokens) else f"Option {idx + 1}"
                        rows[-1][f"second_round_config_{idx + 1}_value"] = percentage
                if duel_percentages:
                    rows[-1]["second_round_duel_a"] = duel_percentages[0]
                    rows[-1]["second_round_duel_b"] = duel_percentages[1]
                    duel_labels = [token for token in second_tokens if token not in {"RN"}]
                    rows[-1]["second_round_duel_a_label"] = duel_labels[0] if duel_labels else "Bloc A"
                    rows[-1]["second_round_duel_b_label"] = "RN"

    frame = pd.DataFrame(rows)
    if frame.empty:
        return frame
    return frame.drop_duplicates(subset=["constituency_name"]).sort_values("constituency_name").reset_index(drop=True)


def _build_national_bloc_frame(reference_dir: Path) -> pd.DataFrame:
    results = load_legislative_2024_results(reference_dir)
    if results.empty:
        return pd.DataFrame()
    frame = results.copy()
    frame["bloc_label"] = frame["bloc_label"].replace({"left": "gauche", "centre": "centre", "right": "droite", "far_right": "extrême_droite", "regionalist": "autres"})
    frame = (
        frame.groupby(["election_round", "bloc_label"], dropna=False)["percent_expressed"]
        .sum()
        .reset_index()
    )
    return frame.loc[frame["bloc_label"].isin(FIVE_BLOC_ORDER)].copy()


def _build_transfer_logic_frame(reference_dir: Path) -> pd.DataFrame:
    first_round = _build_national_bloc_frame(reference_dir)
    if first_round.empty:
        return pd.DataFrame()
    first_round_map = (
        first_round.loc[first_round["election_round"] == "first_round"]
        .set_index("bloc_label")["percent_expressed"]
        .to_dict()
    )
    rows: list[dict[str, object]] = []
    for duel_label, (bloc_a, bloc_b) in DUEL_OPTION_TO_BLOCS.items():
        for source_bloc in FIVE_BLOC_ORDER:
            transfer_map = get_second_round_coalition_2024_transfer_map(source_bloc, bloc_a, bloc_b)
            source_weight = float(first_round_map.get(source_bloc, 0.0))
            rows.append(
                {
                    "duel_label": duel_label,
                    "source_bloc": source_bloc,
                    "target_a_bloc": bloc_a,
                    "target_b_bloc": bloc_b,
                    "source_weight": source_weight,
                    "to_a_weight": float(transfer_map.get(bloc_a, 0.0)),
                    "to_b_weight": float(transfer_map.get(bloc_b, 0.0)),
                    "to_a_points": source_weight * float(transfer_map.get(bloc_a, 0.0)),
                    "to_b_points": source_weight * float(transfer_map.get(bloc_b, 0.0)),
                }
            )
    return pd.DataFrame(rows)


def _render_national_blocs(reference_dir: Path) -> None:
    bloc_frame = _build_national_bloc_frame(reference_dir)
    seats = load_legislative_2024_seats(reference_dir)
    if bloc_frame.empty or seats.empty:
        st.info("Les données nationales 2024 ne sont pas disponibles.")
        return

    first_round = bloc_frame.loc[bloc_frame["election_round"] == "first_round"].copy()
    second_round = bloc_frame.loc[bloc_frame["election_round"] == "second_round"].copy()
    seat_round = seats.loc[seats["election_round"] == "second_round"].copy()

    comparison = (
        first_round.rename(columns={"percent_expressed": "first_round_share"})
        .merge(
            second_round.rename(columns={"percent_expressed": "second_round_share"})[["bloc_label", "second_round_share"]],
            on="bloc_label",
            how="outer",
        )
        .merge(
            seat_round[["bloc_label", "seat_share_percent", "seats"]],
            on="bloc_label",
            how="left",
        )
        .fillna(0.0)
    )
    comparison["Bloc"] = comparison["bloc_label"].map(_bloc_label)

    figure = go.Figure()
    for column, name, color in [
        ("first_round_share", "Premier tour 2024", "#d34a6a"),
        ("second_round_share", "Second tour 2024", "#5a7bd8"),
        ("seat_share_percent", "Part des sièges", "#7c5ea8"),
    ]:
        figure.add_trace(
            go.Bar(
                x=comparison["Bloc"],
                y=comparison[column],
                name=name,
                marker_color=color,
            )
        )
    figure.update_layout(
        title="Législatives 2024 · 5 blocs · voix premier tour, voix second tour et part des sièges",
        barmode="group",
        xaxis_title="Bloc",
        yaxis_title="Part (%)",
        **PLOT_LAYOUT_THEME,
    )
    figure.update_yaxes(ticksuffix=" %")
    st.plotly_chart(figure, width="stretch", config={"displayModeBar": False, "responsive": True})

    st.dataframe(
        comparison[["Bloc", "first_round_share", "second_round_share", "seat_share_percent", "seats"]].rename(
            columns={
                "first_round_share": "Premier tour 2024",
                "second_round_share": "Second tour 2024",
                "seat_share_percent": "Part des sièges",
                "seats": "Sièges",
            }
        ),
        width="stretch",
        hide_index=True,
        column_config={
            "Premier tour 2024": st.column_config.NumberColumn("Premier tour 2024", format="%.2f %%"),
            "Second tour 2024": st.column_config.NumberColumn("Second tour 2024", format="%.2f %%"),
            "Part des sièges": st.column_config.NumberColumn("Part des sièges", format="%.2f %%"),
            "Sièges": st.column_config.NumberColumn("Sièges", format="%d"),
        },
    )


def _render_transfer_logic(reference_dir: Path) -> None:
    transfer_frame = _build_transfer_logic_frame(reference_dir)
    if transfer_frame.empty:
        st.info("Aucune logique de report 2024 disponible.")
        return

    duel_label = st.selectbox("Duel de référence pour 2027", list(DUEL_OPTION_TO_BLOCS.keys()), key="analysis_2024_projection_duel")
    duel_frame = transfer_frame.loc[transfer_frame["duel_label"] == duel_label].copy()
    bloc_a = str(duel_frame["target_a_bloc"].iloc[0])
    bloc_b = str(duel_frame["target_b_bloc"].iloc[0])

    heatmap = go.Figure(
        data=go.Heatmap(
            z=duel_frame[["to_a_weight", "to_b_weight"]].to_numpy(),
            x=[_bloc_label(bloc_a), _bloc_label(bloc_b)],
            y=duel_frame["source_bloc"].map(_bloc_label),
            colorscale="RdBu",
            zmin=0.0,
            zmax=1.0,
            text=[[f"{value:.2f}" for value in row] for row in duel_frame[["to_a_weight", "to_b_weight"]].to_numpy()],
            texttemplate="%{text}",
            hovertemplate="Bloc source: %{y}<br>Destination: %{x}<br>Poids: %{z:.2f}<extra></extra>",
        )
    )
    heatmap.update_layout(
        title=f"Logique de report retenue pour 2027 · {duel_label}",
        xaxis_title="Bloc bénéficiaire",
        yaxis_title="Bloc source du premier tour",
        **PLOT_LAYOUT_THEME,
    )
    st.plotly_chart(heatmap, width="stretch", config={"displayModeBar": False, "responsive": True})

    sankey = go.Figure(
        data=[
            go.Sankey(
                node={
                    "pad": 18,
                    "thickness": 16,
                    "label": [_bloc_label(bloc) for bloc in FIVE_BLOC_ORDER] + [_bloc_label(bloc_a), _bloc_label(bloc_b)],
                    "color": [_bloc_color(bloc) for bloc in FIVE_BLOC_ORDER] + [_bloc_color(bloc_a), _bloc_color(bloc_b)],
                },
                link={
                    "source": list(range(len(FIVE_BLOC_ORDER))) + list(range(len(FIVE_BLOC_ORDER))),
                    "target": [len(FIVE_BLOC_ORDER)] * len(FIVE_BLOC_ORDER) + [len(FIVE_BLOC_ORDER) + 1] * len(FIVE_BLOC_ORDER),
                    "value": duel_frame["to_a_points"].tolist() + duel_frame["to_b_points"].tolist(),
                    "color": [_bloc_color(bloc_a)] * len(FIVE_BLOC_ORDER) + [_bloc_color(bloc_b)] * len(FIVE_BLOC_ORDER),
                },
            )
        ]
    )
    sankey.update_layout(
        title=f"Redistribution pondérée des 5 blocs · {duel_label}",
        **PLOT_LAYOUT_THEME,
    )
    st.plotly_chart(sankey, width="stretch", config={"displayModeBar": False, "responsive": True})

    duel_summary = (
        duel_frame[["source_bloc", "source_weight", "to_a_weight", "to_b_weight", "to_a_points", "to_b_points"]]
        .rename(
            columns={
                "source_bloc": "Bloc source",
                "source_weight": "Poids au 1er tour",
                "to_a_weight": f"Vers {_bloc_label(bloc_a)}",
                "to_b_weight": f"Vers {_bloc_label(bloc_b)}",
                "to_a_points": f"Contribution {_bloc_label(bloc_a)}",
                "to_b_points": f"Contribution {_bloc_label(bloc_b)}",
            }
        )
    )
    duel_summary["Bloc source"] = duel_summary["Bloc source"].map(_bloc_label)
    st.dataframe(
        duel_summary,
        width="stretch",
        hide_index=True,
        column_config={
            "Poids au 1er tour": st.column_config.NumberColumn("Poids au 1er tour", format="%.2f"),
            f"Vers {_bloc_label(bloc_a)}": st.column_config.NumberColumn(f"Vers {_bloc_label(bloc_a)}", format="%.2f"),
            f"Vers {_bloc_label(bloc_b)}": st.column_config.NumberColumn(f"Vers {_bloc_label(bloc_b)}", format="%.2f"),
            f"Contribution {_bloc_label(bloc_a)}": st.column_config.NumberColumn(f"Contribution {_bloc_label(bloc_a)}", format="%.2f"),
            f"Contribution {_bloc_label(bloc_b)}": st.column_config.NumberColumn(f"Contribution {_bloc_label(bloc_b)}", format="%.2f"),
        },
    )

    survey_match = NATIONAL_DUEL_SURVEYS.loc[NATIONAL_DUEL_SURVEYS["duel_label"] == duel_label].copy()
    if not survey_match.empty:
        survey_row = survey_match.iloc[0]
        survey_table = pd.DataFrame(
            [
                {
                    "Hypothèse locale type": duel_label,
                    _bloc_label(str(survey_row["source_a"])): float(survey_row["score_a"]),
                    _bloc_label(str(survey_row["source_b"])): float(survey_row["score_b"]),
                    "Ne sait pas / autre": float(survey_row["undecided"]),
                    "Source": str(survey_row["source_note"]),
                }
            ]
        )
        st.markdown("**Point d’appui sondé dans les sources locales 2024**")
        st.dataframe(
            survey_table,
            width="stretch",
            hide_index=True,
            column_config={
                _bloc_label(str(survey_row["source_a"])): st.column_config.NumberColumn(_bloc_label(str(survey_row["source_a"])), format="%.1f %%"),
                _bloc_label(str(survey_row["source_b"])): st.column_config.NumberColumn(_bloc_label(str(survey_row["source_b"])), format="%.1f %%"),
                "Ne sait pas / autre": st.column_config.NumberColumn("Ne sait pas / autre", format="%.1f %%"),
            },
        )


def _render_constituency_map(local_frame: pd.DataFrame) -> None:
    mapped = local_frame.dropna(subset=["latitude", "longitude"]).copy()
    if mapped.empty:
        st.info("Aucune localisation locale exploitable dans les sources du repo.")
        return

    mapped["marker_size"] = mapped["result_extrême_droite"].clip(lower=18.0) * 0.7
    mapped["hover_label"] = mapped.apply(
        lambda row: (
            f"{row['constituency_name']}<br>"
            f"Gauche / NFP: {row['result_gauche']:.1f}%<br>"
            f"Centre / Ensemble: {row['result_centre']:.1f}%<br>"
            f"Droite / LR: {row['result_droite']:.1f}%<br>"
            f"RN et alliés: {row['result_extrême_droite']:.1f}%"
        ),
        axis=1,
    )
    center, zoom = _compute_mapbox_view(mapped)
    figure = go.Figure(
        go.Scattermapbox(
            lon=mapped["longitude"],
            lat=mapped["latitude"],
            text=mapped["constituency_name"],
            customdata=mapped[["hover_label", "department_name"]].to_numpy(),
            mode="markers+text",
            textposition="top center",
            marker={
                "size": mapped["marker_size"],
                "color": mapped["result_extrême_droite"],
                "colorscale": "Reds",
                "showscale": True,
                "colorbar": {"title": "RN 1er tour"},
                "opacity": 0.88,
            },
            hovertemplate="%{customdata[0]}<br>Département: %{customdata[1]}<extra></extra>",
        )
    )
    layout = dict(PLOT_LAYOUT_THEME)
    layout["margin"] = {**PLOT_LAYOUT_THEME.get("margin", {}), "t": 70, "r": 20, "l": 20, "b": 10}
    figure.update_layout(
        title="Carte interactive des circonscriptions locales présentes dans les sources 2024 du repo",
        mapbox={
            "style": "open-street-map",
            "center": center,
            "zoom": zoom,
        },
        **layout,
    )
    st.plotly_chart(figure, width="stretch", config={"displayModeBar": False, "responsive": True})


def _render_constituency_detail(local_frame: pd.DataFrame) -> None:
    if local_frame.empty:
        st.info("Aucune circonscription locale n’a pu être relue dans les sources du repo.")
        return

    search_query = st.text_input(
        "Recherche permissive circonscription / ville / région / département / numéro",
        key="analysis_2024_local_constituency_query",
        placeholder="Exemples : nord, 10, 59, nice, alpes maritimes, seine saint denis, calvados",
    )
    filtered = _filter_constituencies(local_frame, search_query)
    if filtered.empty:
        st.warning("Aucune circonscription locale ne correspond à cette recherche.")
        return

    st.caption(
        f"{len(filtered)} circonscription(s) locale(s) trouvée(s). "
        "La carte accepte déjà les outremers si ces circonscriptions existent dans les données locales ; "
        "pour l’instant le repo ne contient pas encore le fond exhaustif complet."
    )
    _render_constituency_map(filtered)

    shortlist = (
        filtered[["constituency_name", "department_name", "winning_label"]]
        .rename(columns={"constituency_name": "Circonscription", "department_name": "Département", "winning_label": "Étiquette en tête"})
        .sort_values(["Département", "Circonscription"])
        .reset_index(drop=True)
    )
    st.dataframe(shortlist, width="stretch", hide_index=True)

    selected_constituency = filtered.iloc[0]["constituency_name"]
    if len(filtered) > 1:
        radio_options = filtered["constituency_name"].tolist()
        selected_constituency = st.radio(
            "Circonscription détaillée",
            radio_options,
            index=0,
            key="analysis_2024_local_constituency_choice",
            format_func=lambda value: f"{value} · {filtered.loc[filtered['constituency_name'] == value, 'department_name'].iloc[0]}",
        )
    row = filtered.loc[filtered["constituency_name"] == selected_constituency].iloc[0]

    first_round_chart = go.Figure()
    first_round_chart.add_trace(
        go.Bar(
            x=[_bloc_label(bloc) for bloc in FIVE_BLOC_ORDER],
            y=[float(row[f"result_{bloc}"]) for bloc in FIVE_BLOC_ORDER],
            name="Résultat 1er tour",
            marker_color="#d34a6a",
        )
    )
    first_round_chart.add_trace(
        go.Bar(
            x=[_bloc_label(bloc) for bloc in FIVE_BLOC_ORDER],
            y=[float(row.get(f"poll_{bloc}", 0.0)) for bloc in FIVE_BLOC_ORDER],
            name="Sondage local",
            marker_color="#5a7bd8",
        )
    )
    first_round_chart.update_layout(
        title=f"{selected_constituency} · premier tour 2024 · résultat vs sondage local",
        barmode="group",
        xaxis_title="Bloc",
        yaxis_title="Part (%)",
        **PLOT_LAYOUT_THEME,
    )
    first_round_chart.update_yaxes(ticksuffix=" %")
    st.plotly_chart(first_round_chart, width="stretch", config={"displayModeBar": False, "responsive": True})

    second_round_labels: list[str] = []
    second_round_values: list[float] = []
    for idx in range(1, 4):
        label = row.get(f"second_round_config_{idx}_label")
        value = row.get(f"second_round_config_{idx}_value")
        if pd.notna(label) and pd.notna(value):
            second_round_labels.append(str(label))
            second_round_values.append(float(value))
    duel_a = row.get("second_round_duel_a")
    duel_b = row.get("second_round_duel_b")
    if second_round_labels or pd.notna(duel_a) or pd.notna(duel_b):
        second_round_chart = go.Figure()
        if second_round_labels:
            second_round_chart.add_trace(
                go.Bar(
                    x=second_round_labels,
                    y=second_round_values,
                    name="Configuration 2nd tour locale",
                    marker_color="#7c5ea8",
                )
            )
        if pd.notna(duel_a) and pd.notna(duel_b):
            second_round_chart.add_trace(
                go.Bar(
                    x=[str(row.get("second_round_duel_a_label", "Bloc A")), str(row.get("second_round_duel_b_label", "Bloc B"))],
                    y=[float(duel_a), float(duel_b)],
                    name="Duel après désistement",
                    marker_color="#f2a65a",
                )
            )
        second_round_chart.update_layout(
            title=f"{selected_constituency} · second tour local · configuration et duel après désistement",
            barmode="group",
            xaxis_title="Option locale",
            yaxis_title="Part (%)",
            **PLOT_LAYOUT_THEME,
        )
        second_round_chart.update_yaxes(ticksuffix=" %")
        st.plotly_chart(second_round_chart, width="stretch", config={"displayModeBar": False, "responsive": True})

    detail_table = pd.DataFrame(
        [
            {
                "Circonscription": selected_constituency,
                "Département": row["department_name"],
                "Bloc vainqueur 1er tour": _bloc_label(str(row["winning_bloc"])),
                "Étiquette en tête": row["winning_label"],
                "Note": row["local_source_note"],
            }
        ]
    )
    st.dataframe(detail_table, width="stretch", hide_index=True)


def render_analysis_2024_projection_logic_page(frame: pd.DataFrame) -> None:
    st.subheader("Analyse 2024 par circonscription et par force politique pour la logique 2027")

    official = _load_official_general_results()
    official_circo = _build_official_constituency_results(official)
    official_force_summary, _official_force_candidates, _official_t2_maintained = _build_official_2024_circo_force_analysis()
    presidential_projection_2027 = _build_2027_first_round_force_projection(_official_force_candidates, official_force_summary)
    coalition_projection_2027 = _build_2027_first_round_coalition_projection(_official_force_candidates, official_force_summary)
    bloc_projection_2027 = _build_2027_first_round_bloc_projection(_official_force_candidates, official_force_summary)
    _withdrawal_target_matrix, _against_matrix, _anti_target_matrix, duel_presidential_base = _build_withdrawal_and_runoff_analysis(
        official_force_summary,
        _official_force_candidates,
    )
    runoff_projection_2027 = _build_2027_runoff_projection_from_2024(
        presidential_projection_2027,
        _anti_target_matrix,
        duel_presidential_base,
    )
    has_real_second_round_results = (
        not official_force_summary.empty
        and "winner_force_t2" in official_force_summary.columns
        and official_force_summary["winner_force_t2"].notna().any()
    )

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Circonscriptions T1 chargées", int(len(official_force_summary)) if not official_force_summary.empty else 0)
    col2.metric("Triangulaires réelles", int((official_force_summary["configuration_t2"] == "Triangulaire").sum()) if not official_force_summary.empty else 0)
    col3.metric("Désistements qualifiés", int(official_force_summary["withdrawn_count"].sum()) if not official_force_summary.empty else 0)
    col4.metric("Lignes agrégées officielles", int(len(official_circo)))

    st.markdown("**1. Projection présidentielle 2027 issue de l’analyse 2024**")
    if not presidential_projection_2027.empty:
        top_projection = presidential_projection_2027.head(8).copy()
        presidential_projection_display = presidential_projection_2027.copy()
        presidential_projection_display["Force_affichee"] = presidential_projection_display["Force"].map(_projection_force_display_label)
        st.caption(
            "Lecture présidentielle retenue : on raisonne ici d’abord par forces politiques réelles. "
            "Les blocs restent uniquement descriptifs pour aider la lecture, mais ils ne pilotent plus le classement ni les duels."
        )
        st.caption(
            "Forces les mieux placées au 1er tour 2027 estimé après correction de couverture : "
            + ", ".join(
                f"{_projection_force_display_label(row.Force)} ({float(row.socle_projete_2027_t1):.1f}%)"
                for row in top_projection.itertuples(index=False)
            )
        )
        lead1, lead2, lead3 = st.columns(3)
        lead1.metric("Force 1 estimée", _projection_force_display_label(top_projection.iloc[0]["Force"]), f"{float(top_projection.iloc[0]['socle_projete_2027_t1']):.1f} %")
        if len(top_projection) > 1:
            lead2.metric("Force 2 estimée", _projection_force_display_label(top_projection.iloc[1]["Force"]), f"{float(top_projection.iloc[1]['socle_projete_2027_t1']):.1f} %")
        if len(top_projection) > 2:
            lead3.metric("Force 3 estimée", _projection_force_display_label(top_projection.iloc[2]["Force"]), f"{float(top_projection.iloc[2]['socle_projete_2027_t1']):.1f} %")

        first_round_force_chart = go.Figure(
            go.Bar(
                x=presidential_projection_display["Force_affichee"],
                y=presidential_projection_display["socle_projete_2027_t1"],
                marker_color=[_force_color(force) for force in presidential_projection_display["Force"]],
                text=[f"{value:.1f} %" for value in presidential_projection_display["socle_projete_2027_t1"]],
                textposition="outside",
                customdata=presidential_projection_display[["Bloc", "taux_couverture"]].to_numpy(),
                hovertemplate=(
                    "Force: %{x}<br>"
                    "Socle estimé: %{y:.2f}%<br>"
                    "Bloc descriptif: %{customdata[0]}<br>"
                    "Couverture 2024: %{customdata[1]:.2f}%<extra></extra>"
                ),
            )
        )
        first_round_force_chart.update_layout(
            title="Socle présidentiel 2027 estimé par force politique",
            xaxis_title="Force politique",
            yaxis_title="Socle estimé (%)",
            **PLOT_LAYOUT_THEME,
        )
        first_round_force_chart.update_yaxes(ticksuffix=" %")
        st.plotly_chart(first_round_force_chart, width="stretch", config={"displayModeBar": False, "responsive": True})

        if not coalition_projection_2027.empty:
            top_coalitions = coalition_projection_2027.head(6).copy()
            coalition_projection_display = coalition_projection_2027.copy()
            st.caption(
                "Lecture parallèle par coalition : "
                + ", ".join(
                    f"{str(row.Force)} ({float(row.socle_projete_2027_t1):.1f}%)"
                    for row in top_coalitions.itertuples(index=False)
                )
            )
            coalition1, coalition2, coalition3 = st.columns(3)
            coalition1.metric("Coalition 1 estimée", str(top_coalitions.iloc[0]["Force"]), f"{float(top_coalitions.iloc[0]['socle_projete_2027_t1']):.1f} %")
            if len(top_coalitions) > 1:
                coalition2.metric("Coalition 2 estimée", str(top_coalitions.iloc[1]["Force"]), f"{float(top_coalitions.iloc[1]['socle_projete_2027_t1']):.1f} %")
            if len(top_coalitions) > 2:
                coalition3.metric("Coalition 3 estimée", str(top_coalitions.iloc[2]["Force"]), f"{float(top_coalitions.iloc[2]['socle_projete_2027_t1']):.1f} %")

            first_round_coalition_chart = go.Figure(
                go.Bar(
                    x=coalition_projection_display["Force"],
                    y=coalition_projection_display["socle_projete_2027_t1"],
                    marker_color=[_bloc_color(_force_to_bloc_key(force)) for force in coalition_projection_display["Force"]],
                    text=[f"{value:.1f} %" for value in coalition_projection_display["socle_projete_2027_t1"]],
                    textposition="outside",
                    customdata=coalition_projection_display[["Bloc", "taux_couverture"]].to_numpy(),
                    hovertemplate=(
                        "Coalition: %{x}<br>"
                        "Socle estimé: %{y:.2f}%<br>"
                        "Bloc descriptif: %{customdata[0]}<br>"
                        "Couverture 2024: %{customdata[1]:.2f}%<extra></extra>"
                    ),
                )
            )
            first_round_coalition_chart.update_layout(
                title="Socle présidentiel 2027 estimé par coalition",
                xaxis_title="Coalition",
                yaxis_title="Socle estimé (%)",
                **PLOT_LAYOUT_THEME,
            )
            first_round_coalition_chart.update_yaxes(ticksuffix=" %")
            st.plotly_chart(first_round_coalition_chart, width="stretch", config={"displayModeBar": False, "responsive": True})

        st.dataframe(
            presidential_projection_display[
                [
                    "Force_affichee",
                    "Bloc",
                    "socle_projete_2027_t1",
                    "taux_couverture",
                    "score_national_couvert_t1",
                    "presence_nationalisee_t1",
                    "facteur_couverture_2027",
                    "facteur_representativite_2027",
                    "correctif_representation_force_2027",
                    "taux_tete_t1",
                    "taux_qualification_t2",
                    "taux_maintien_parmi_qualifies",
                    "taux_retrait_parmi_qualifies",
                ]
            ].rename(
                columns={
                    "Force_affichee": "Force politique",
                    "Bloc": "Bloc descriptif",
                    "socle_projete_2027_t1": "Socle présidentiel T1 estimé",
                    "taux_couverture": "Couverture 2024",
                    "score_national_couvert_t1": "Score national couvert T1",
                    "presence_nationalisee_t1": "Présence nationalisée T1",
                    "facteur_couverture_2027": "Facteur de couverture",
                    "facteur_representativite_2027": "Facteur de représentativité",
                    "correctif_representation_force_2027": "Correctif de représentation",
                    "taux_tete_t1": "Têtes au T1",
                    "taux_qualification_t2": "Qualification T2",
                    "taux_maintien_parmi_qualifies": "Maintien parmi qualifiés",
                    "taux_retrait_parmi_qualifies": "Retrait parmi qualifiés",
                }
            ),
            width="stretch",
            hide_index=True,
            column_config={
                "Socle présidentiel T1 estimé": st.column_config.NumberColumn("Socle présidentiel T1 estimé", format="%.2f %%"),
                "Couverture 2024": st.column_config.NumberColumn("Couverture 2024", format="%.2f %%"),
                "Score national couvert T1": st.column_config.NumberColumn("Score national couvert T1", format="%.2f %%"),
                "Présence nationalisée T1": st.column_config.NumberColumn("Présence nationalisée T1", format="%.2f %%"),
                "Facteur de couverture": st.column_config.NumberColumn("Facteur de couverture", format="%.3f"),
                "Facteur de représentativité": st.column_config.NumberColumn("Facteur de représentativité", format="%.3f"),
                "Correctif de représentation": st.column_config.NumberColumn("Correctif de représentation", format="%.3f"),
                "Têtes au T1": st.column_config.NumberColumn("Têtes au T1", format="%.2f %%"),
                "Qualification T2": st.column_config.NumberColumn("Qualification T2", format="%.2f %%"),
                "Maintien parmi qualifiés": st.column_config.NumberColumn("Maintien parmi qualifiés", format="%.2f %%"),
                "Retrait parmi qualifiés": st.column_config.NumberColumn("Retrait parmi qualifiés", format="%.2f %%"),
            },
        )
        if not coalition_projection_2027.empty:
            coalition_display = coalition_projection_2027.copy()
            st.dataframe(
                coalition_display[
                    [
                        "Force",
                        "Niveau",
                        "Bloc",
                        "socle_projete_2027_t1",
                        "taux_couverture",
                        "score_national_couvert_t1",
                    ]
                ].rename(
                    columns={
                        "Force": "Coalition",
                        "Niveau": "Niveau",
                        "Bloc": "Bloc descriptif",
                        "socle_projete_2027_t1": "Socle présidentiel T1 estimé",
                        "taux_couverture": "Couverture 2024",
                        "score_national_couvert_t1": "Score national couvert T1",
                    }
                ),
                width="stretch",
                hide_index=True,
                column_config={
                    "Socle présidentiel T1 estimé": st.column_config.NumberColumn("Socle présidentiel T1 estimé", format="%.2f %%"),
                    "Couverture 2024": st.column_config.NumberColumn("Couverture 2024", format="%.2f %%"),
                    "Score national couvert T1": st.column_config.NumberColumn("Score national couvert T1", format="%.2f %%"),
                },
            )
        if not bloc_projection_2027.empty:
            with st.expander("Lecture descriptive complémentaire par bloc", expanded=False):
                st.dataframe(
                    bloc_projection_2027[
                        ["Force", "socle_projete_2027_t1", "taux_couverture", "score_national_couvert_t1"]
                    ].rename(
                        columns={
                            "Force": "Bloc",
                            "socle_projete_2027_t1": "Socle présidentiel T1 estimé",
                            "taux_couverture": "Couverture 2024",
                            "score_national_couvert_t1": "Score national couvert T1",
                        }
                    ),
                    width="stretch",
                    hide_index=True,
                    column_config={
                        "Socle présidentiel T1 estimé": st.column_config.NumberColumn("Socle présidentiel T1 estimé", format="%.2f %%"),
                        "Couverture 2024": st.column_config.NumberColumn("Couverture 2024", format="%.2f %%"),
                        "Score national couvert T1": st.column_config.NumberColumn("Score national couvert T1", format="%.2f %%"),
                    },
                )
    if not runoff_projection_2027.empty:
        st.caption(
            "Projection présidentielle 2027 du second tour : les autres forces ne sont pas réparties comme un simple report neutre. "
            "Elles sont redistribuées selon la logique de barrage observée en 2024, c’est-à-dire d’abord contre un adversaire. "
            "La couverture des finalistes continue aussi de peser à ce stade."
        )
        force_order_frame = presidential_projection_2027.loc[
            presidential_projection_2027["Force"].map(_is_runoff_projectable_force),
            ["Force", "socle_projete_2027_t1"],
        ].copy()
        force_order_frame["Force_affichee"] = force_order_frame["Force"].map(_projection_force_display_label)
        force_order_frame["Coalition"] = force_order_frame["Force"].map(_force_to_coalition_label)
        force_order_frame = force_order_frame.sort_values("socle_projete_2027_t1", ascending=False)
        force_catalog = (
            force_order_frame.drop_duplicates(subset=["Force_affichee"], keep="first")
            .reset_index(drop=True)
        )
        duel_force_set = {
            _projection_force_display_label(force)
            for force in pd.concat(
                [runoff_projection_2027["force_a"], runoff_projection_2027["force_b"]],
                ignore_index=True,
            ).dropna().astype(str)
        }
        force_catalog = force_catalog.loc[force_catalog["Force_affichee"].isin(duel_force_set)].copy()
        duel_forces = force_catalog["Force_affichee"].tolist()
        default_force_a = _projection_force_display_label(str(runoff_projection_2027.iloc[0]["force_a"]))
        default_force_b = _projection_force_display_label(str(runoff_projection_2027.iloc[0]["force_b"]))
        selector_a, selector_b = st.columns(2)
        selected_force_a = selector_a.selectbox(
            "Finaliste A",
            duel_forces,
            index=duel_forces.index(default_force_a) if default_force_a in duel_forces else 0,
            key="analysis_2024_projected_runoff_force_a",
        )
        selected_force_a_raw = force_catalog.loc[force_catalog["Force_affichee"] == selected_force_a, "Force"].iloc[0]
        force_b_options = [
            row.Force_affichee
            for row in force_catalog.itertuples(index=False)
            if _are_runoff_finalists_compatible(selected_force_a_raw, row.Force)
        ]
        if not force_b_options:
            force_b_options = [force for force in duel_forces if force != selected_force_a]
        default_force_b_index = force_b_options.index(default_force_b) if default_force_b in force_b_options else 0
        selected_force_b = selector_b.selectbox(
            "Finaliste B",
            force_b_options,
            index=default_force_b_index,
            key="analysis_2024_projected_runoff_force_b",
        )
        duel_mask = (
            (
                runoff_projection_2027["force_a"].map(_projection_force_display_label).eq(selected_force_a)
                & runoff_projection_2027["force_b"].map(_projection_force_display_label).eq(selected_force_b)
            )
            | (
                runoff_projection_2027["force_a"].map(_projection_force_display_label).eq(selected_force_b)
                & runoff_projection_2027["force_b"].map(_projection_force_display_label).eq(selected_force_a)
            )
        )
        selected_duel_frame = runoff_projection_2027.loc[duel_mask].copy()
        if selected_duel_frame.empty:
            st.warning("Aucune estimation disponible pour cette combinaison de finalistes.")
            return
        selected_duel_projection = selected_duel_frame.sort_values(
            ["duels_historiques_directs", "ecart_estime"],
            ascending=[False, False],
        ).iloc[0]

        col1, col2, col3 = st.columns(3)
        col1.metric("Duel retenu", str(selected_duel_projection["duel_label"]))
        col2.metric("Gagnant estimé", _projection_force_display_label(selected_duel_projection["gagnant_estime"]), f"{float(selected_duel_projection['ecart_estime']):.1f} pts")
        col3.metric("Duels 2024 comparables", int(selected_duel_projection["duels_historiques_directs"]))

        projected_runoff_chart = go.Figure(
            go.Bar(
                x=[
                    _projection_force_display_label(selected_duel_projection["force_a"]),
                    _projection_force_display_label(selected_duel_projection["force_b"]),
                ],
                y=[float(selected_duel_projection["score_final_estime_a"]), float(selected_duel_projection["score_final_estime_b"])],
                marker_color=[_force_color(str(selected_duel_projection["force_a"])), _force_color(str(selected_duel_projection["force_b"]))],
                text=[
                    f"{float(selected_duel_projection['score_final_estime_a']):.1f} %",
                    f"{float(selected_duel_projection['score_final_estime_b']):.1f} %",
                ],
                textposition="outside",
            )
        )
        projected_runoff_chart.update_layout(
            title="Projection 2027 · second tour estimé avec logique de barrage",
            xaxis_title="Finaliste",
            yaxis_title="Part estimée (%)",
            **PLOT_LAYOUT_THEME,
        )
        projected_runoff_chart.update_yaxes(ticksuffix=" %")
        st.plotly_chart(projected_runoff_chart, width="stretch", config={"displayModeBar": False, "responsive": True})

        st.dataframe(
            runoff_projection_2027.assign(
                force_a=runoff_projection_2027["force_a"].map(_projection_force_display_label),
                force_b=runoff_projection_2027["force_b"].map(_projection_force_display_label),
                gagnant_estime=runoff_projection_2027["gagnant_estime"].map(_projection_force_display_label),
            )[
                [
                    "duel_label",
                    "gagnant_estime",
                    "facteur_couverture_a",
                    "facteur_couverture_b",
                    "facteur_representativite_a",
                    "facteur_representativite_b",
                    "score_final_estime_a",
                    "score_final_estime_b",
                    "score_estime_barrage_a",
                    "score_estime_barrage_b",
                    "score_historique_duel_a",
                    "duels_historiques_directs",
                    "poids_historique_duel",
                    "ecart_estime",
                ]
            ].rename(
                columns={
                    "duel_label": "Duel",
                    "gagnant_estime": "Gagnant estimé",
                    "facteur_couverture_a": "Couverture A",
                    "facteur_couverture_b": "Couverture B",
                    "facteur_representativite_a": "Représentativité A",
                    "facteur_representativite_b": "Représentativité B",
                    "score_final_estime_a": "Score final A",
                    "score_final_estime_b": "Score final B",
                    "score_estime_barrage_a": "Score barrage A",
                    "score_estime_barrage_b": "Score barrage B",
                    "score_historique_duel_a": "Référence duel 2024 pour A",
                    "duels_historiques_directs": "Duels 2024 comparables",
                    "poids_historique_duel": "Poids du correctif historique",
                    "ecart_estime": "Écart estimé",
                }
            ),
            width="stretch",
            hide_index=True,
            column_config={
                "Couverture A": st.column_config.NumberColumn("Couverture A", format="%.3f"),
                "Couverture B": st.column_config.NumberColumn("Couverture B", format="%.3f"),
                "Représentativité A": st.column_config.NumberColumn("Représentativité A", format="%.3f"),
                "Représentativité B": st.column_config.NumberColumn("Représentativité B", format="%.3f"),
                "Score final A": st.column_config.NumberColumn("Score final A", format="%.2f %%"),
                "Score final B": st.column_config.NumberColumn("Score final B", format="%.2f %%"),
                "Score barrage A": st.column_config.NumberColumn("Score barrage A", format="%.2f %%"),
                "Score barrage B": st.column_config.NumberColumn("Score barrage B", format="%.2f %%"),
                "Référence duel 2024 pour A": st.column_config.NumberColumn("Référence duel 2024 pour A", format="%.2f %%"),
                "Poids du correctif historique": st.column_config.NumberColumn("Poids du correctif historique", format="%.2f"),
                "Écart estimé": st.column_config.NumberColumn("Écart estimé", format="%.2f pts"),
            },
        )
    if has_real_second_round_results and not duel_presidential_base.empty:
        top_duels = duel_presidential_base.head(5).copy()
        st.caption(
            "Rapports de force de second tour pour la présidentielle : "
            + ", ".join(
                f"{_projection_force_display_label(row.Force)} contre {_projection_force_display_label(row.Adversaire)} ({float(row.taux_de_victoire):.1f}% de victoires observées)"
                for row in top_duels.itertuples(index=False)
            )
        )
    else:
        st.caption(
            "La logique présidentielle de second tour reste préparée, mais les résultats T2 réels ne sont pas encore "
            "assez propres dans cette session pour afficher une hiérarchie finale fiable."
        )

    st.markdown("**2. Données 2024 détaillées · qualifiés, maintiens, triangulaires et désistements par force**")
    _render_official_constituency_results()
