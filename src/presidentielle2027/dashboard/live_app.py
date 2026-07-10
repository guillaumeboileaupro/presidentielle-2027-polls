from __future__ import annotations

import pandas as pd
import streamlit as st
from sqlalchemy.exc import SQLAlchemyError

from presidentielle2027.analytics.polling_average import load_results_dataframe
from presidentielle2027.config import get_settings
from presidentielle2027.dashboard import app as dashboard_app
from presidentielle2027.dashboard.views.wikipedia_overview import render_wikipedia_overview_page
from presidentielle2027.dashboard.wiki_refresh import (
    WIKIPEDIA_NORMALIZED_FILENAME,
    refresh_wikipedia_2027_dataset,
)
from presidentielle2027.db.session import get_engine


WIKIPEDIA_PAGE = {
    "label": "Sondages 2027",
    "renderer": render_wikipedia_overview_page,
    "help": """
### Sondages 2027

Vue de référence en deux graphiques : évolution par parti politique puis évolution par candidat.

Les données Wikipédia françaises sont rafraîchies au lancement de l'application. Les points représentent les mesures publiées et les courbes une tendance lissée descriptive.
""",
}


@st.cache_data(show_spinner=False)
def load_live_dashboard_data() -> pd.DataFrame:
    settings = get_settings()
    live_path = settings.processed_dir / WIKIPEDIA_NORMALIZED_FILENAME
    if live_path.exists():
        return pd.read_csv(live_path)

    normalized_v2_path = settings.processed_dir / "wikipedia_2027_polls_normalized_v2.csv"
    normalized_path = settings.processed_dir / "wikipedia_2027_polls_normalized.csv"
    sample_path = settings.processed_dir / "sample_polls.csv"
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


def _refresh_live_data() -> str | None:
    settings = get_settings()
    try:
        refresh_wikipedia_2027_dataset(
            raw_dir=settings.raw_dir,
            processed_dir=settings.processed_dir,
        )
        load_live_dashboard_data.clear()
        return None
    except Exception as exc:  # noqa: BLE001 - keep the last auditable local snapshot available
        return str(exc)


def main() -> None:
    refresh_error = _refresh_live_data()
    if not any(config["label"] == WIKIPEDIA_PAGE["label"] for config in dashboard_app.PAGE_CONFIG):
        dashboard_app.PAGE_CONFIG.insert(0, WIKIPEDIA_PAGE)
    dashboard_app.load_dashboard_data = load_live_dashboard_data
    dashboard_app.main()
    if refresh_error:
        st.warning(
            "La mise à jour Wikipédia au lancement a échoué. "
            f"Le dernier snapshot local est utilisé. Détail : {refresh_error}"
        )


if __name__ == "__main__":
    main()
