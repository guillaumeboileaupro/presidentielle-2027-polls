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

    page = st.radio(
        "Vue",
        [
            "Sources et métadonnées",
            "Sondages 2027 - premier tour brut",
            "Sondages 2027 - second tour brut",
            "Barres d’erreur brutes",
            "Analyse historique 2022",
            "Comparaison 2022 sondages vs résultat",
            "Analyse législatives 2024",
            "Biais calculés",
            "Projection corrigée 2027",
            "Dataset corrigé 2027",
            "Scénarios exploratoires",
        ],
        horizontal=True,
    )
    if page == "Sources et métadonnées":
        render_sources_metadata_page(frame)
    elif page == "Sondages 2027 - premier tour brut":
        render_first_round_raw_page(frame)
    elif page == "Sondages 2027 - second tour brut":
        render_second_round_raw_page(frame)
    elif page == "Barres d’erreur brutes":
        render_error_bars_raw_page(frame)
    elif page == "Analyse historique 2022":
        render_analysis_2022_page()
    elif page == "Comparaison 2022 sondages vs résultat":
        render_analysis_2022_comparison_page()
    elif page == "Analyse législatives 2024":
        render_analysis_2024_page()
    elif page == "Biais calculés":
        render_biases_page(frame)
    elif page == "Projection corrigée 2027":
        render_dynamic_bias_page(frame)
    elif page == "Scénarios exploratoires":
        render_projection_scenarios_page(frame)
    else:
        render_corrected_dataset_page(frame)


if __name__ == "__main__":
    main()
