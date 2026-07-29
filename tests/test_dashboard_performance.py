from __future__ import annotations

import inspect

import pandas as pd

from presidentielle2027.dashboard import app, live_app
from presidentielle2027.dashboard.views import first_round_raw


def test_dashboard_startup_does_not_run_ingestion_pipeline() -> None:
    module_source = inspect.getsource(live_app)

    assert "run_refresh_pipeline" not in module_source
    assert "load_dashboard_data.clear" not in module_source
    assert "prepare_dashboard_frame.clear" not in module_source


def test_dashboard_preparation_does_not_precompute_all_trends() -> None:
    function_source = inspect.getsource(app.prepare_dashboard_frame)

    assert "smooth_candidate_trends" not in function_source


def test_candidate_chart_is_deferred_by_default() -> None:
    function_source = inspect.getsource(live_app._render_first_round_with_candidate_chart)

    assert "value=False" in function_source
    assert function_source.index("st.checkbox") < function_source.index("render_candidate_trace_chart")


def test_first_round_curves_are_cached_and_plot_payload_is_bounded() -> None:
    function_source = inspect.getsource(first_round_raw._cached_trend_curve)

    assert "dense_points=300" in function_source
    assert hasattr(first_round_raw._cached_trend_curve, "clear")


def test_detailed_poll_table_is_deferred_by_default() -> None:
    function_source = inspect.getsource(first_round_raw.render_first_round_raw_page)

    checkbox_position = function_source.index('"Afficher le tableau détaillé des sondages"')
    table_position = function_source.index("render_poll_results_table(detailed)")
    assert checkbox_position < table_position
    assert "value=False" in function_source[checkbox_position:table_position]


def test_latest_raw_first_round_replaces_stale_v2_database_rows() -> None:
    base = pd.DataFrame(
        {
            "poll_id": ["V2-FR-OLD-001"],
            "round": ["first_round"],
            "source_name": [None],
            "scenario_name": ["ancien"],
            "candidate_name": ["Jean-Luc Mélenchon"],
            "polling_company": ["Ifop"],
            "fieldwork_start_date": ["2026-01-01"],
            "fieldwork_end_date": ["2026-01-02"],
            "estimate_percent": [1.5],
        }
    )
    raw = base.assign(
        poll_id="RAW-FR-IFOP-01-001",
        source_name="wikipedia_fr_raw_tables",
        scenario_name="corrigé",
        estimate_percent=15.0,
    )

    merged = app._merge_dashboard_with_latest_raw_frame(base, raw)

    assert merged["poll_id"].tolist() == ["RAW-FR-IFOP-01-001"]
    assert merged["estimate_percent"].tolist() == [15.0]
