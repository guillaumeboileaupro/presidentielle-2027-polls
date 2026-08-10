from __future__ import annotations

from pathlib import Path

import pandas as pd

from presidentielle2027.config import Settings
from presidentielle2027.db.session import get_session_factory
from presidentielle2027.ingestion.pipeline import run_periodic_refresh_pipeline, run_refresh_pipeline


class DummySession:
    def close(self) -> None:
        return None


class DummySessionFactory:
    def __call__(self) -> DummySession:
        return DummySession()


def test_run_periodic_refresh_pipeline_respects_max_runs(monkeypatch, tmp_path: Path) -> None:
    settings = Settings(
        DATABASE_URL=f"sqlite:///{tmp_path / 'test.sqlite3'}",
        AUTO_INGEST_INTERVAL_MINUTES=5,
    )
    calls: list[int] = []
    sleeps: list[float] = []

    def fake_run_refresh_pipeline(*, settings, session_factory):  # type: ignore[no-untyped-def]
        calls.append(1)
        return type(
            "Summary",
            (),
            {
                "normalized_input": Path("in.csv"),
                "normalized_output": Path("out.csv"),
                "coverage_output": Path("coverage.csv"),
                "averages_output": Path("averages.csv"),
                "persisted_rows": 12,
            },
        )()

    monkeypatch.setattr(
        "presidentielle2027.ingestion.pipeline.run_refresh_pipeline",
        fake_run_refresh_pipeline,
    )

    executed_runs = run_periodic_refresh_pipeline(
        settings=settings,
        session_factory=DummySessionFactory(),
        interval_minutes=5,
        max_runs=2,
        sleep_fn=sleeps.append,
    )

    assert executed_runs == 2
    assert len(calls) == 2
    assert sleeps == [300]


def test_run_periodic_refresh_pipeline_retries_after_failure(monkeypatch, tmp_path: Path) -> None:
    settings = Settings(DATABASE_URL=f"sqlite:///{tmp_path / 'test.sqlite3'}")
    calls: list[int] = []
    sleeps: list[float] = []

    def flaky_refresh(*, settings, session_factory):  # type: ignore[no-untyped-def]
        calls.append(1)
        if len(calls) == 1:
            raise ConnectionError("temporary network failure")
        return type(
            "Summary",
            (),
            {
                "normalized_input": Path("in.csv"),
                "normalized_output": Path("out.csv"),
                "coverage_output": Path("coverage.csv"),
                "averages_output": Path("averages.csv"),
                "persisted_rows": 12,
            },
        )()

    monkeypatch.setattr("presidentielle2027.ingestion.pipeline.run_refresh_pipeline", flaky_refresh)

    executed_runs = run_periodic_refresh_pipeline(
        settings=settings,
        session_factory=DummySessionFactory(),
        interval_minutes=1,
        max_runs=2,
        sleep_fn=sleeps.append,
    )

    assert executed_runs == 2
    assert len(calls) == 2
    assert sleeps == [60]


def test_run_refresh_pipeline_writes_outputs(monkeypatch, tmp_path: Path) -> None:
    raw_dir = tmp_path / "data" / "raw"
    processed_dir = tmp_path / "data" / "processed"
    exports_dir = tmp_path / "data" / "exports"
    raw_dir.mkdir(parents=True)
    processed_dir.mkdir(parents=True)
    exports_dir.mkdir(parents=True)

    settings = Settings(
        DATABASE_URL=f"sqlite:///{tmp_path / 'test.sqlite3'}",
        AUTO_INGEST_INTERVAL_MINUTES=5,
    )
    settings.raw_dir = raw_dir
    settings.processed_dir = processed_dir
    settings.exports_dir = exports_dir

    normalized_frame = pd.DataFrame(
        [
            {
                "poll_id": "poll-1",
                "source_url": "https://example.org/poll-1",
                "source_name": "test",
                "polling_company": "Ifop",
                "commissioner": None,
                "media_partner": None,
                "fieldwork_start_date": "2026-05-01",
                "fieldwork_end_date": "2026-05-02",
                "publication_date": "2026-05-03",
                "sample_size": 1000,
                "population": "registered_voters",
                "collection_method": "online",
                "quota_method": "true",
                "round": "first_round",
                "scenario_name": "Scenario test",
                "candidate_name": "Jordan Bardella",
                "candidate_party": "RN",
                "political_family": "droite_nationale",
                "estimate_percent": 35.0,
                "lower_bound_percent": None,
                "upper_bound_percent": None,
                "margin_of_error": None,
                "undecided_percent": None,
                "abstention_estimate": None,
                "registered_voters_basis": True,
                "raw_text_context": "Jordan Bardella 35; Édouard Philippe 18",
                "extraction_confidence": 0.9,
            },
            {
                "poll_id": "poll-1",
                "source_url": "https://example.org/poll-1",
                "source_name": "test",
                "polling_company": "Ifop",
                "commissioner": None,
                "media_partner": None,
                "fieldwork_start_date": "2026-05-01",
                "fieldwork_end_date": "2026-05-02",
                "publication_date": "2026-05-03",
                "sample_size": 1000,
                "population": "registered_voters",
                "collection_method": "online",
                "quota_method": "true",
                "round": "first_round",
                "scenario_name": "Scenario test",
                "candidate_name": "Édouard Philippe",
                "candidate_party": "Horizons",
                "political_family": "centre_droit",
                "estimate_percent": 18.0,
                "lower_bound_percent": None,
                "upper_bound_percent": None,
                "margin_of_error": None,
                "undecided_percent": None,
                "abstention_estimate": None,
                "registered_voters_basis": True,
                "raw_text_context": "Jordan Bardella 35; Édouard Philippe 18",
                "extraction_confidence": 0.9,
            },
        ]
    )
    input_csv = processed_dir / "wikipedia_2027_polls_normalized_v2.csv"
    normalized_frame.to_csv(input_csv, index=False)

    monkeypatch.setattr(
        "presidentielle2027.ingestion.pipeline.ingest_wikipedia_sources",
        lambda **kwargs: [],
    )
    monkeypatch.setattr(
        "presidentielle2027.ingestion.pipeline.generate_wiki_datasets",
        lambda *args, **kwargs: None,
    )

    summary = run_refresh_pipeline(
        settings=settings,
        session_factory=get_session_factory(settings.database_url),
    )

    assert summary.normalized_output == input_csv
    assert summary.coverage_output.exists()
    assert summary.averages_output.exists()
    assert summary.persisted_rows == 2
