from __future__ import annotations

from pathlib import Path

import pandas as pd

from presidentielle2027.config import Settings
from presidentielle2027.db.session import get_session_factory
from presidentielle2027.ingestion.pipeline import (
    run_periodic_refresh_pipeline,
    run_refresh_pipeline,
)


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
    settings.interim_dir = tmp_path / "data" / "interim"

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
    legacy_csv = processed_dir / "wikipedia_2027_polls_normalized.csv"
    assert legacy_csv.exists()
    assert pd.read_csv(legacy_csv)["poll_id"].tolist() == normalized_frame["poll_id"].tolist()
    assert summary.coverage_output.exists()
    assert summary.averages_output.exists()
    assert summary.persisted_rows == 2


# --- automatic refresh: lock, status, offline start, retry and launch-time gating -------------


def _settings_in(tmp_path: Path, **kwargs: object) -> Settings:
    settings = Settings(DATABASE_URL=f"sqlite:///{tmp_path / 'test.sqlite3'}", **kwargs)  # type: ignore[arg-type]
    settings.interim_dir = tmp_path / "interim"
    return settings


def _summary(path: Path) -> object:
    return type(
        "Summary",
        (),
        {
            "normalized_input": path,
            "normalized_output": path,
            "coverage_output": path,
            "averages_output": path,
            "persisted_rows": 7,
        },
    )()


def test_refresh_records_success_and_failure_in_the_status_file(monkeypatch, tmp_path: Path) -> None:
    from presidentielle2027.ingestion import pipeline
    from presidentielle2027.ingestion.refresh_state import (
        is_refresh_running,
        lock_path,
        read_refresh_status,
        status_path,
    )

    settings = _settings_in(tmp_path)
    dataset = tmp_path / "dataset.csv"
    dataset.write_text("a,b\n1,2\n", encoding="utf-8")
    outcomes: list[object] = [_summary(dataset), ConnectionError("offline")]

    def fake_locked(*, settings, session_factory):  # type: ignore[no-untyped-def]
        outcome = outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    monkeypatch.setattr(pipeline, "_run_refresh_locked", fake_locked)

    pipeline.run_refresh_pipeline(settings=settings, session_factory=DummySessionFactory())
    ok = read_refresh_status(status_path(settings.interim_dir))
    assert ok.state == "ok" and ok.persisted_rows == 7 and ok.dataset_sha256  # type: ignore[union-attr]

    try:
        pipeline.run_refresh_pipeline(settings=settings, session_factory=DummySessionFactory())
    except ConnectionError:
        pass
    failed = read_refresh_status(status_path(settings.interim_dir))
    assert failed.state == "error" and "ConnectionError" in failed.error  # type: ignore[union-attr, operator]
    assert failed.dataset_sha256 == ok.dataset_sha256  # type: ignore[union-attr]
    assert not is_refresh_running(lock_path(settings.interim_dir))


def test_refresh_refuses_to_run_twice_at_the_same_time(monkeypatch, tmp_path: Path) -> None:
    import pytest

    from presidentielle2027.ingestion import pipeline
    from presidentielle2027.ingestion.refresh_state import (
        RefreshInProgressError,
        lock_path,
        refresh_lock,
    )

    settings = _settings_in(tmp_path)
    monkeypatch.setattr(pipeline, "_run_refresh_locked", lambda **kw: pytest.fail("must not run"))

    with refresh_lock(lock_path(settings.interim_dir)), pytest.raises(RefreshInProgressError):
        pipeline.run_refresh_pipeline(settings=settings, session_factory=DummySessionFactory())


def test_network_exit_from_dataset_generation_is_a_retryable_error(monkeypatch, tmp_path: Path) -> None:
    """make_wiki_datasets calls SystemExit on network errors; that used to kill the scraper."""
    import pytest

    from presidentielle2027.ingestion import pipeline

    settings = _settings_in(tmp_path)
    monkeypatch.setattr(pipeline, "init_database", lambda url: None)
    monkeypatch.setattr(pipeline, "ingest_wikipedia_sources", lambda **kw: [])

    def offline(out_dir, cache_dir):  # type: ignore[no-untyped-def]
        raise SystemExit(2)

    monkeypatch.setattr(pipeline, "generate_wiki_datasets", offline)

    with pytest.raises(RuntimeError, match="exit code 2"):
        pipeline._run_refresh_locked(settings=settings, session_factory=DummySessionFactory())


def test_periodic_refresh_survives_offline_start_and_retries_soon(monkeypatch, tmp_path: Path) -> None:
    from presidentielle2027.ingestion import pipeline

    settings = _settings_in(tmp_path)
    attempts: list[int] = []
    sleeps: list[float] = []

    def offline_then_online(*, settings, session_factory):  # type: ignore[no-untyped-def]
        attempts.append(1)
        if len(attempts) == 1:
            raise RuntimeError("Wikipedia dataset generation failed (exit code 2).")
        return _summary(tmp_path)

    monkeypatch.setattr(pipeline, "run_refresh_pipeline", offline_then_online)

    pipeline.run_periodic_refresh_pipeline(
        settings=settings,
        session_factory=DummySessionFactory(),
        interval_minutes=60,
        max_runs=2,
        sleep_fn=sleeps.append,
    )

    assert len(attempts) == 2
    assert sleeps == [5 * 60]  # retry in 5 minutes, not after the full hour


def test_periodic_refresh_skips_a_run_when_another_process_is_refreshing(monkeypatch, tmp_path: Path) -> None:
    from presidentielle2027.ingestion import pipeline
    from presidentielle2027.ingestion.refresh_state import RefreshInProgressError

    settings = _settings_in(tmp_path)
    sleeps: list[float] = []

    def busy(*, settings, session_factory):  # type: ignore[no-untyped-def]
        raise RefreshInProgressError("busy")

    monkeypatch.setattr(pipeline, "run_refresh_pipeline", busy)

    executed = pipeline.run_periodic_refresh_pipeline(
        settings=settings,
        session_factory=DummySessionFactory(),
        interval_minutes=30,
        max_runs=2,
        sleep_fn=sleeps.append,
    )

    assert executed == 2
    assert sleeps == [30 * 60]


def test_launch_waits_for_recent_data_but_refreshes_immediately_when_stale(monkeypatch, tmp_path: Path) -> None:
    from datetime import datetime, timedelta, timezone

    from presidentielle2027.ingestion import pipeline
    from presidentielle2027.ingestion.refresh_state import status_path, write_refresh_status

    settings = _settings_in(tmp_path)
    monkeypatch.setattr(pipeline, "run_refresh_pipeline", lambda **kw: _summary(tmp_path))

    def first_sleep(minutes_ago: float | None) -> list[float]:
        target = status_path(settings.interim_dir)
        target.unlink(missing_ok=True)
        if minutes_ago is not None:
            moment = datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)
            write_refresh_status(target, state="ok", last_success_at=moment.isoformat(timespec="seconds"))
        sleeps: list[float] = []
        pipeline.run_periodic_refresh_pipeline(
            settings=settings,
            session_factory=DummySessionFactory(),
            interval_minutes=60,
            max_runs=1,
            sleep_fn=sleeps.append,
            min_age_minutes=10,
        )
        return sleeps

    recent = first_sleep(2)
    assert len(recent) == 1 and 470 <= recent[0] <= 480  # 10 min minus the 2 min already elapsed
    assert first_sleep(30) == []  # stale: refresh right away
    assert first_sleep(None) == []  # never refreshed: refresh right away
