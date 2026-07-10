from __future__ import annotations

from datetime import date
from pathlib import Path
import re
import warnings

import pandas as pd
import streamlit as st
from sqlalchemy.exc import SQLAlchemyError

from presidentielle2027.analytics.polling_average import load_results_dataframe
from presidentielle2027.analytics.trends import smooth_candidate_trends
from presidentielle2027.config import get_settings
from presidentielle2027.db.session import get_engine
from presidentielle2027.dashboard.views.analysis_2022 import render_analysis_2022_comparison_page, render_analysis_2022_page
from presidentielle2027.dashboard.views.analysis_2024 import render_analysis_2024_page
from presidentielle2027.dashboard.views.analysis_2024_projection_logic import render_analysis_2024_projection_logic_page
from presidentielle2027.dashboard.views.biases import render_biases_page
from presidentielle2027.dashboard.views.corrected_dataset import render_corrected_dataset_page
from presidentielle2027.dashboard.views.error_bars_raw import render_error_bars_raw_page
from presidentielle2027.dashboard.views.dynamic_bias import render_dynamic_bias_page
from presidentielle2027.dashboard.views.first_round_raw import render_first_round_raw_page
from presidentielle2027.dashboard.views.projection_scenarios import render_projection_scenarios_page
from presidentielle2027.dashboard.views.second_round_raw import render_second_round_raw_page
from presidentielle2027.dashboard.views.sources_metadata import render_sources_metadata_page
from presidentielle2027.dashboard.party_assets import render_app_header
from presidentielle2027.dashboard.styles import apply_browser_chrome_overrides, apply_dashboard_styles
from presidentielle2027.extraction.canonicalization import canonicalize_candidate_fields, is_generic_bloc_label
from presidentielle2027.extraction.excel_parser import raw_wikipedia_2027_tables_to_normalized_dataframe


warnings.filterwarnings(
    "ignore",
    message="remove second argument of ws_handler",
    category=DeprecationWarning,
    module="websockets\\.legacy\\.server",
)


PAGE_CONFIG = [
    {
        "label": "Sources et métadonnées",
        "renderer": render_sources_metadata_page,
        "help": """
### Sources et métadonnées

Cette vue documente les fichiers utilisés, leur niveau de transformation et leur statut d'import.

- `observé` : donnée lue dans une source publique.
- `reconstruit` : donnée réorganisée ou rapprochée automatiquement.
- `corrigé` : donnée ajustée par une méthode de redressement.

Commencer ici si vous voulez vérifier l'origine d'un chiffre avant d'interpréter une projection.
""",
    },
    {
        "label": "Sondages 2027 - premier tour brut",
        "renderer": render_first_round_raw_page,
        "help": """
### Premier tour brut

Cette page montre les intentions de vote non redressées par l'historique électoral.

- les courbes résument la dynamique des sondages publiés ;
- les tableaux conservent la granularité source ;
- les valeurs restent dépendantes du mode de collecte et du terrain disponible.

Lire cette vue comme un état descriptif des sondages, pas comme une prévision ferme.
""",
    },
    {
        "label": "Sondages 2027 - second tour brut",
        "renderer": render_second_round_raw_page,
        "help": """
### Second tour brut

Cette vue regroupe les duels testés par les instituts sans correction méthodologique additionnelle.

- chaque duel dépend fortement de l'offre de candidats ;
- les écarts faibles doivent être lus avec prudence ;
- l'absence de duel ne signifie pas qu'il est impossible, seulement qu'il n'est pas mesuré ici.
""",
    },
    {
        "label": "Barres d’erreur brutes",
        "renderer": render_error_bars_raw_page,
        "help": """
### Barres d’erreur brutes

La page visualise l'incertitude statistique déclarée autour des mesures publiées.

- une barre courte ne supprime pas les biais de questionnaire ou d'échantillon ;
- une barre longue signale qu'un écart apparent peut être peu robuste ;
- comparer les recouvrements aide à éviter les surinterprétations.
""",
    },
    {
        "label": "Analyse historique 2022",
        "renderer": lambda _frame: render_analysis_2022_page(),
        "help": """
### Analyse historique 2022

Cette page reconstitue le comportement des sondages de la présidentielle 2022 pour servir de point de comparaison.

- elle aide à mesurer les biais récurrents ;
- elle ne doit pas être plaquée mécaniquement sur 2027 ;
- elle sert surtout de base de calibration et d'audit.
""",
    },
    {
        "label": "Comparaison 2022 sondages vs résultat",
        "renderer": lambda _frame: render_analysis_2022_comparison_page(),
        "help": """
### Comparaison 2022

Ici, les dernières mesures disponibles sont confrontées au résultat réellement obtenu.

- la page isole les écarts finaux ;
- elle montre quels candidats étaient surestimés ou sous-estimés ;
- elle sert de repère pour juger la fiabilité des corrections utilisées ailleurs.
""",
    },
    {
        "label": "Législatives 2024 - sondages et blocs",
        "renderer": lambda _frame: render_analysis_2024_page(),
        "help": """
### Législatives 2024 - sondages et blocs

Cette vue reste centrée sur les sondages nationaux 2024, les blocs et les sièges.

- les violons montrent la dispersion des mesures dans le temps ;
- les graphiques sièges vs résultat servent à visualiser les erreurs d'atterrissage ;
- l'objectif est d'ancrer les corrections dans un précédent plus proche de 2027 que 2022.

Cette page n'est pas la page d'analyse détaillée circonscription par circonscription.
""",
    },
    {
        "label": "Législatives 2024 - circonscriptions et logique 2027",
        "renderer": lambda frame: render_analysis_2024_projection_logic_page(frame),
        "help": """
### Législatives 2024 - circonscriptions et logique 2027

Cette vue est la page d'analyse détaillée par circonscription et par force politique.

- premier tour relu circonscription par circonscription ;
- qualifiés, maintiens et désistements au second tour ;
- lecture par force politique, y compris à l'intérieur du NFP ;
- base de travail pour la logique de projection 2027.
""",
    },
    {
        "label": "Biais calculés",
        "renderer": render_biases_page,
        "help": """
### Biais calculés

Cette page synthétise les écarts estimés entre les sondages publiés et les résultats observés de référence.

- un biais positif signifie qu'un bloc a tendance à être corrigé à la hausse ;
- un biais négatif signifie qu'il a tendance à être ramené vers le bas ;
- ces coefficients dépendent des hypothèses retenues dans les pages historiques.
""",
    },
    {
        "label": "Projection corrigée 2027",
        "renderer": render_dynamic_bias_page,
        "help": """
### Projection corrigée 2027

Cette vue applique les redressements retenus aux sondages 2027 pour produire une lecture corrigée.

- la correction ne transforme pas un sondage en certitude ;
- elle transpose des biais passés avec des pondérations explicites ;
- il faut toujours relire les hypothèses avant d'utiliser le résultat.
""",
    },
    {
        "label": "Dataset corrigé 2027",
        "renderer": render_corrected_dataset_page,
        "help": """
### Dataset corrigé 2027

Cette page expose le jeu de données corrigé, ses colonnes de calcul et les audits associés.

- utile pour vérifier les transformations ligne par ligne ;
- utile aussi pour exporter ou reproduire les calculs ;
- si un chiffre vous surprend, c'est la bonne page pour remonter sa chaîne de construction.
""",
    },
    {
        "label": "Scénarios exploratoires",
        "renderer": render_projection_scenarios_page,
        "help": """
### Scénarios exploratoires

Cette vue teste des hypothèses alternatives plutôt qu'un scénario central unique.

- les sorties montrent une sensibilité aux paramètres ;
- elles servent à comparer des variantes, pas à annoncer un verdict ;
- il faut les lire comme des stress tests politiques et méthodologiques.
""",
    },
]


def _page_slug(label: str) -> str:
    slug = label.lower()
    slug = slug.replace("é", "e").replace("è", "e").replace("ê", "e").replace("à", "a").replace("ù", "u").replace("ô", "o")
    slug = re.sub(r"[^a-z0-9]+", "-", slug).strip("-")
    return slug or "page"


@st.cache_data(show_spinner=False)
def load_dashboard_data() -> pd.DataFrame:
    settings = get_settings()
    normalized_v2_path = settings.processed_dir / "wikipedia_2027_polls_normalized_v2.csv"
    normalized_path = settings.processed_dir / "wikipedia_2027_polls_normalized.csv"
    sample_path = settings.processed_dir / "sample_polls.csv"
    base_frame = pd.DataFrame()
    try:
        frame = load_results_dataframe(get_engine())
        if not frame.empty:
            base_frame = frame
    except SQLAlchemyError:
        base_frame = pd.DataFrame()
    if base_frame.empty and normalized_v2_path.exists():
        base_frame = pd.read_csv(normalized_v2_path)
    if base_frame.empty and normalized_path.exists():
        base_frame = pd.read_csv(normalized_path)
    if base_frame.empty:
        base_frame = pd.read_csv(sample_path)

    raw_frame = raw_wikipedia_2027_tables_to_normalized_dataframe(settings.raw_dir)
    return _merge_dashboard_with_latest_raw_frame(base_frame, raw_frame)


def _merge_dashboard_with_latest_raw_frame(base_frame: pd.DataFrame, raw_frame: pd.DataFrame) -> pd.DataFrame:
    if base_frame.empty:
        return raw_frame
    if raw_frame.empty:
        return base_frame

    cleaned_base = base_frame.copy()
    if "poll_id" in cleaned_base.columns:
        raw_poll_mask = cleaned_base["poll_id"].fillna("").astype(str).str.startswith(("RAW-FR-", "RAW-SR-"))
        cleaned_base = cleaned_base.loc[~raw_poll_mask].copy()

    merged = pd.concat([cleaned_base, raw_frame], ignore_index=True, sort=False)
    merged = merged.drop_duplicates(
        subset=[
            "round",
            "polling_company",
            "fieldwork_start_date",
            "fieldwork_end_date",
            "scenario_name",
            "candidate_name",
        ],
        keep="last",
    )
    return merged


@st.cache_data(show_spinner=False)
def prepare_dashboard_frame(frame: pd.DataFrame) -> pd.DataFrame:
    working = frame.copy()
    canonical = working.apply(
        lambda row: canonicalize_candidate_fields(
            row.get("candidate_name"),
            row.get("candidate_party"),
            row.get("political_family"),
        ),
        axis=1,
        result_type="expand",
    )
    canonical.columns = ["candidate_name", "candidate_party", "political_family"]
    working[["candidate_name", "candidate_party", "political_family"]] = canonical
    working["is_generic_bloc"] = working["candidate_name"].map(is_generic_bloc_label)
    working["publication_date"] = pd.to_datetime(working["publication_date"], errors="coerce")
    working["fieldwork_start_date"] = pd.to_datetime(working.get("fieldwork_start_date"), errors="coerce")
    working["fieldwork_end_date"] = pd.to_datetime(working.get("fieldwork_end_date"), errors="coerce")
    working["estimate_percent"] = pd.to_numeric(working["estimate_percent"], errors="coerce")
    working["sample_size"] = pd.to_numeric(working.get("sample_size"), errors="coerce")
    working = smooth_candidate_trends(working)
    return working


def main() -> None:
    page_icon = Path(__file__).parent / "assets" / "favicon-neutral.svg"
    st.set_page_config(page_title="Présidentielle 2027", page_icon=str(page_icon), layout="wide")
    apply_dashboard_styles()
    apply_browser_chrome_overrides()
    st.markdown(render_app_header(), unsafe_allow_html=True)

    frame = prepare_dashboard_frame(load_dashboard_data())
    if frame.empty:
        st.warning("Aucune donnée disponible.")
        return

    page_labels = [config["label"] for config in PAGE_CONFIG]
    page_lookup = {config["label"]: config for config in PAGE_CONFIG}
    slug_to_label = {_page_slug(config["label"]): config["label"] for config in PAGE_CONFIG}
    default_page = page_labels[0]
    requested_page = default_page
    query_params = {}
    if hasattr(st, "query_params"):
        query_params = dict(st.query_params)
    elif hasattr(st, "experimental_get_query_params"):
        query_params = st.experimental_get_query_params()
    page_param = query_params.get("page")
    if isinstance(page_param, list):
        page_param = page_param[0] if page_param else None
    if page_param in slug_to_label:
        requested_page = slug_to_label[page_param]

    nav_col, help_col = st.columns([16, 1.4])
    with nav_col:
        page = st.radio(
            "Vue",
            page_labels,
            horizontal=True,
            index=page_labels.index(requested_page),
            key="dashboard_page_radio",
            label_visibility="collapsed",
        )
        page_slug = _page_slug(page)
        if hasattr(st, "query_params"):
            if st.query_params.get("page") != page_slug:
                st.query_params["page"] = page_slug
        elif hasattr(st, "experimental_set_query_params"):
            current_page_param = query_params.get("page")
            if isinstance(current_page_param, list):
                current_page_param = current_page_param[0] if current_page_param else None
            if current_page_param != page_slug:
                st.experimental_set_query_params(page=page_slug)
    with help_col:
        with st.popover("?", help="Aide pour la vue active", use_container_width=True):
            st.markdown(page_lookup[page]["help"])

    page_lookup[page]["renderer"](frame)


if __name__ == "__main__":
    main()
