from __future__ import annotations

import inspect

import pandas as pd

from presidentielle2027.dashboard import app, live_app
from presidentielle2027.dashboard.metadata import (
    build_frame_completeness_summary,
    meaningful_value_mask,
)
from presidentielle2027.dashboard.table_views import (
    clean_user_facing_frame,
    rename_user_facing_columns,
    user_facing_value,
)
from presidentielle2027.dashboard.views import analysis_2022, first_round_raw, sources_metadata


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


def test_historical_2022_overview_uses_true_local_regression() -> None:
    function_source = inspect.getsource(analysis_2022.render_analysis_2022_page)

    assert 'method="loess"' in function_source
    assert "ajustement polynomial et résultat final" not in function_source


def test_user_facing_tables_translate_technical_fields_and_values() -> None:
    frame = pd.DataFrame(
        {
            "publication_date": [pd.Timestamp("2026-07-29")],
            "sample_size": [1000],
            "political_family": ["centre_gauche"],
            "collection_method": ["online"],
        }
    )

    displayed = clean_user_facing_frame(rename_user_facing_columns(frame))

    assert displayed.columns.tolist() == ["Publication", "Échantillon", "Famille politique", "Collecte"]
    assert displayed.loc[0, "Publication"] == "29/07/2026"
    assert displayed.loc[0, "Famille politique"] == "Centre-gauche"
    assert displayed.loc[0, "Collecte"] == "En ligne"


def test_metadata_page_does_not_display_raw_technical_field_names() -> None:
    function_source = inspect.getsource(sources_metadata.render_sources_metadata_page)

    assert '"Champ technique"' not in function_source
    assert 'drop(columns="field"' in function_source


def test_metadata_coverage_treats_placeholder_values_as_missing() -> None:
    frame = pd.DataFrame(
        {
            "collection_method": ["unknown", "N/A", "online", None],
            "publication_date": pd.to_datetime(
                ["2026-01-01", None, "2026-01-03", "2026-01-04"]
            ),
        }
    )

    summary = build_frame_completeness_summary(frame).set_index("field")

    assert summary.loc["collection_method", "filled_count"] == 1
    assert summary.loc["collection_method", "missing_count"] == 3
    assert summary.loc["collection_method", "coverage_percent"] == 25.0
    assert summary.loc["publication_date", "filled_count"] == 3
    assert meaningful_value_mask(pd.Series(["non disponible", "Ifop"])).tolist() == [
        False,
        True,
    ]


def test_metadata_quality_table_has_field_state_round_and_pollster_filters() -> None:
    function_source = inspect.getsource(sources_metadata._render_metadata_quality_explorer)

    assert '"Champ à contrôler"' in function_source
    assert '"État du champ"' in function_source
    assert '"Tour"' in function_source
    assert '"Institut"' in function_source
    assert "meaningful_value_mask" in function_source


def test_navigation_follows_analysis_workflow_and_keeps_sources_last() -> None:
    labels = [config["label"] for config in app.PAGE_CONFIG]

    assert labels[:3] == [
        "Sondages 2027 - premier tour brut",
        "Sondages 2027 - second tour brut",
        "Barres d’erreur brutes",
    ]
    assert labels.index("Biais calculés") < labels.index("Projection corrigée 2027")
    assert labels[-1] == "Sources et métadonnées"


def test_metadata_page_is_split_into_navigable_sections() -> None:
    function_source = inspect.getsource(sources_metadata.render_sources_metadata_page)

    assert '"Vue d’ensemble"' in function_source
    assert '"Contrôle qualité"' in function_source
    assert '"Instituts et sources"' in function_source
    assert '"Archives brutes"' in function_source


def test_unknown_internal_identifiers_get_a_readable_fallback() -> None:
    frame = pd.DataFrame(
        {
            "new_internal_keyword": ["untranslated_status_code"],
        }
    )

    displayed = clean_user_facing_frame(rename_user_facing_columns(frame))

    assert displayed.columns.tolist() == ["New internal keyword"]
    assert displayed.iloc[0, 0] == "Untranslated status code"
    assert user_facing_value("centre_gauche") == "Centre-gauche"


def test_live_dashboard_installs_the_global_text_guard() -> None:
    function_source = inspect.getsource(live_app.main)

    assert "install_user_facing_text_guard()" in function_source


def test_official_results_are_flagged_separately_from_polls() -> None:
    frame = pd.DataFrame(
        {
            "poll_id": ["poll-1", "RAW-FR-RÉSULTATS-06-010"],
            "polling_company": ["Ifop", "Résultats"],
            "scenario_name": ["Hypothèse", "Résultats officiels"],
            "candidate_name": ["Candidat A", "Candidat A"],
            "candidate_party": ["TEST", "TEST"],
            "political_family": ["centre", "centre"],
            "publication_date": ["2022-04-01", "2022-04-10"],
            "fieldwork_start_date": ["2022-03-31", "2022-04-10"],
            "fieldwork_end_date": ["2022-04-01", "2022-04-10"],
            "estimate_percent": [20.0, 25.0],
            "sample_size": [1000, 1000000],
        }
    )

    prepared = app.prepare_dashboard_frame(frame)

    assert prepared["is_official_result"].tolist() == [False, True]


def test_dashboard_excludes_official_results_from_regular_renderers() -> None:
    function_source = inspect.getsource(app.main)

    assert 'page != "Sources et métadonnées"' in function_source
    assert '~frame["is_official_result"]' in function_source


def test_historical_second_round_smoothing_uses_polls_only() -> None:
    function_source = inspect.getsource(analysis_2022.render_analysis_2022_page)

    assert "second_round_polls" in function_source
    assert "ordered = second_round_polls.sort_values" in function_source
