from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd
import streamlit as st
from sqlalchemy.exc import SQLAlchemyError

from presidentielle2027.analytics.polling_average import load_results_dataframe
from presidentielle2027.analytics.trends import smooth_candidate_trends
from presidentielle2027.config import get_settings
from presidentielle2027.db.session import get_engine
from presidentielle2027.dashboard.views.analysis_2022 import render_analysis_2022_comparison_page, render_analysis_2022_page
from presidentielle2027.dashboard.views.analysis_2024 import render_analysis_2024_page
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
        "label": "Analyse législatives 2024",
        "renderer": lambda _frame: render_analysis_2024_page(),
        "help": """
### Législatives 2024

Cette vue traite 2024 comme une boussole récente sur les écarts entre sondages, blocs et sièges.

- les violons montrent la dispersion des mesures dans le temps ;
- les graphiques sièges vs résultat servent à visualiser les erreurs d'atterrissage ;
- l'objectif est d'ancrer les corrections dans un précédent plus proche de 2027 que 2022.
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


@st.cache_data(show_spinner=False)
def load_dashboard_data() -> pd.DataFrame:
    normalized_v2_path = get_settings().processed_dir / "wikipedia_2027_polls_normalized_v2.csv"
    normalized_path = get_settings().processed_dir / "wikipedia_2027_polls_normalized.csv"
    sample_path = get_settings().processed_dir / "sample_polls.csv"
    try:
        frame = load_results_dataframe(get_engine())
        if not frame.empty:
            return frame
    except SQLAlchemyError:
        pass
    if normalized_v2_path.exists():
        return pd.read_csv(normalized_v2_path)
    if normalized_path.exists():
        return pd.read_csv(normalized_path)
    return pd.read_csv(sample_path)


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

    nav_col, help_col = st.columns([16, 1.4])
    with nav_col:
        page = st.radio(
            "Vue",
            page_labels,
            horizontal=True,
            key="dashboard_page",
            label_visibility="collapsed",
        )
    with help_col:
        with st.popover("?", help="Aide pour la vue active", use_container_width=True):
            st.markdown(page_lookup[page]["help"])

    page_lookup[page]["renderer"](frame)


if __name__ == "__main__":
    main()
