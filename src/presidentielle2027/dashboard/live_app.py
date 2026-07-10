from __future__ import annotations

from pathlib import Path

import streamlit as st

from presidentielle2027.config import get_settings
from presidentielle2027.dashboard import app as dashboard_app
from presidentielle2027.dashboard.data_quality import repair_scaled_first_round_scenarios
from presidentielle2027.dashboard.party_assets import render_app_header
from presidentielle2027.dashboard.styles import apply_browser_chrome_overrides, apply_dashboard_styles
from presidentielle2027.dashboard.views.wikipedia_2027 import render_wikipedia_2027_page
from presidentielle2027.db.session import get_session_factory
from presidentielle2027.ingestion.pipeline import run_refresh_pipeline


PAGE_CONFIG = [
    {
        "label": "Sondages 2027",
        "renderer": render_wikipedia_2027_page,
        "help": """
### Sondages 2027

Cette page reprend la lecture attendue des sondages 2027 avec deux graphiques distincts :

- évolution par parti politique ;
- évolution par candidat.

Les données Wikipédia sont rafraîchies au démarrage de l'application avant l'affichage.
""",
    },
    *dashboard_app.PAGE_CONFIG,
]


@st.cache_resource(show_spinner=False)
def _refresh_wikipedia_once_per_app_start() -> str:
    settings = get_settings()
    summary = run_refresh_pipeline(
        settings=settings,
        session_factory=get_session_factory(),
    )
    dashboard_app.load_dashboard_data.clear()
    dashboard_app.prepare_dashboard_frame.clear()
    return (
        f"Données Wikipédia actualisées : {summary.persisted_rows} lignes persistées · "
        f"source normalisée {summary.normalized_output.name}"
    )


def main() -> None:
    page_icon = Path(__file__).parent / "assets" / "favicon-neutral.svg"
    st.set_page_config(page_title="Présidentielle 2027", page_icon=str(page_icon), layout="wide")

    with st.spinner("Actualisation des sondages Wikipédia 2027..."):
        try:
            refresh_status = _refresh_wikipedia_once_per_app_start()
        except Exception as exc:
            st.error(f"Actualisation Wikipédia impossible : {exc}")
            st.stop()

    apply_dashboard_styles()
    apply_browser_chrome_overrides()
    st.markdown(render_app_header(), unsafe_allow_html=True)
    st.caption(refresh_status)

    raw_frame = dashboard_app.load_dashboard_data()
    repaired_frame = repair_scaled_first_round_scenarios(raw_frame)
    frame = dashboard_app.prepare_dashboard_frame(repaired_frame)
    if frame.empty:
        st.warning("Aucune donnée disponible.")
        return

    page_labels = [config["label"] for config in PAGE_CONFIG]
    page_lookup = {config["label"]: config for config in PAGE_CONFIG}
    slug_to_label = {dashboard_app._page_slug(config["label"]): config["label"] for config in PAGE_CONFIG}
    requested_page = page_labels[0]

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
        page_slug = dashboard_app._page_slug(page)
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
