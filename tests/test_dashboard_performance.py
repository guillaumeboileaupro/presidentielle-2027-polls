from __future__ import annotations

import inspect

from presidentielle2027.dashboard import app, live_app


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
