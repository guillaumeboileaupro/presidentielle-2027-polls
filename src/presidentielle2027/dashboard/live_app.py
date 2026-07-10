from __future__ import annotations

from presidentielle2027.config import get_settings
from presidentielle2027.dashboard import app as dashboard_app
from presidentielle2027.dashboard.views.first_round_raw import render_first_round_raw_page
from presidentielle2027.dashboard.views.wikipedia_2027 import render_candidate_trace_chart
from presidentielle2027.db.session import get_session_factory
from presidentielle2027.ingestion.pipeline import run_refresh_pipeline


def _render_first_round_with_candidate_chart(frame) -> None:
    render_first_round_raw_page(frame)
    render_candidate_trace_chart(frame)


def _refresh_wikipedia_before_dashboard() -> None:
    settings = get_settings()
    run_refresh_pipeline(
        settings=settings,
        session_factory=get_session_factory(),
    )
    dashboard_app.load_dashboard_data.clear()
    dashboard_app.prepare_dashboard_frame.clear()


def main() -> None:
    _refresh_wikipedia_before_dashboard()
    for config in dashboard_app.PAGE_CONFIG:
        if config["label"] == "Sondages 2027 - premier tour brut":
            config["renderer"] = _render_first_round_with_candidate_chart
            break
    dashboard_app.main()


if __name__ == "__main__":
    main()
