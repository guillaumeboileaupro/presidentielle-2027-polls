from __future__ import annotations

import pandas as pd
import streamlit as st

from presidentielle2027.dashboard import app as dashboard_app
from presidentielle2027.dashboard.views.first_round_raw import render_first_round_raw_page
from presidentielle2027.dashboard.views.wikipedia_2027 import render_candidate_trace_chart


def _render_first_round_with_candidate_chart(frame: pd.DataFrame) -> None:
    render_first_round_raw_page(frame)
    if st.checkbox(
        "Afficher aussi les courbes par candidat",
        value=False,
        key="show_first_round_candidate_chart",
    ):
        render_candidate_trace_chart(frame)


def main() -> None:
    for config in dashboard_app.PAGE_CONFIG:
        if config["label"] == "Sondages 2027 - premier tour brut":
            config["renderer"] = _render_first_round_with_candidate_chart
            break
    dashboard_app.main()


if __name__ == "__main__":
    main()
