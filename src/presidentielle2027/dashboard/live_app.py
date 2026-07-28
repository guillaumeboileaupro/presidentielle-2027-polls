from __future__ import annotations

import pandas as pd
import streamlit as st

from presidentielle2027.dashboard import app as dashboard_app
from presidentielle2027.dashboard.data_quality import repair_scaled_first_round_scenarios
from presidentielle2027.dashboard.views.first_round_raw import render_first_round_raw_page
from presidentielle2027.dashboard.views.wikipedia_2027 import render_candidate_trace_chart


@st.cache_data(show_spinner=False)
def _prepare_first_round_frame(frame: pd.DataFrame) -> pd.DataFrame:
    return repair_scaled_first_round_scenarios(frame)


def _render_first_round_with_candidate_chart(frame: pd.DataFrame) -> None:
    repaired_frame = _prepare_first_round_frame(frame)
    render_first_round_raw_page(repaired_frame)
    if st.checkbox(
        "Afficher aussi les courbes par candidat",
        value=False,
        key="show_first_round_candidate_chart",
    ):
        render_candidate_trace_chart(repaired_frame)


def main() -> None:
    for config in dashboard_app.PAGE_CONFIG:
        if config["label"] == "Sondages 2027 - premier tour brut":
            config["renderer"] = _render_first_round_with_candidate_chart
            break
    dashboard_app.main()


if __name__ == "__main__":
    main()
