from pathlib import Path

import pytest
from sqlalchemy import select

from presidentielle2027.db.init_db import init_database
from presidentielle2027.db.models import Poll, PollResult, PollScenario
from presidentielle2027.db.session import get_session_factory
from presidentielle2027.extraction.normalizer import normalize_csv_file, normalize_to_database


def test_database_roundtrip(tmp_path) -> None:
    database_url = f"sqlite:///{tmp_path / 'test.sqlite3'}"
    init_database(database_url)
    session = get_session_factory(database_url)()
    records = normalize_csv_file(Path("data/processed/sample_polls.csv"))
    try:
        inserted = normalize_to_database(records, session)
        assert inserted > 0
        assert session.scalar(select(Poll).limit(1)) is not None
        assert session.scalar(select(PollResult).limit(1)) is not None
    finally:
        session.close()


def test_database_import_updates_duplicate_candidate_within_same_batch(tmp_path) -> None:
    database_url = f"sqlite:///{tmp_path / 'duplicates.sqlite3'}"
    init_database(database_url)
    session = get_session_factory(database_url)()
    records = normalize_csv_file(Path("data/processed/sample_polls.csv"))
    duplicate = records[0].model_copy(update={"estimate_percent": 42.0})

    try:
        persisted = normalize_to_database([records[0], duplicate], session)
        results = session.scalars(select(PollResult)).all()

        assert persisted == 2
        assert len(results) == 1
        assert results[0].estimate_percent == 42.0
    finally:
        session.close()


def test_database_snapshot_replacement_removes_stale_poll_and_scenario_rows(tmp_path) -> None:
    database_url = f"sqlite:///{tmp_path / 'snapshot.sqlite3'}"
    init_database(database_url)
    session = get_session_factory(database_url)()
    records = normalize_csv_file(Path("data/processed/sample_polls.csv"))
    source_records = [record for record in records if record.source_url == records[0].source_url]
    stale = records[0].model_copy(
        update={"poll_id": "stale-poll", "scenario_name": "stale-scenario"}
    )

    try:
        normalize_to_database([*source_records, stale], session)
        normalize_to_database(
            source_records,
            session,
            replace_source_snapshot=True,
        )

        assert session.scalar(select(Poll).where(Poll.poll_id == "stale-poll")) is None
        assert session.scalar(
            select(PollScenario).where(PollScenario.scenario_name == "stale-scenario")
        ) is None
        assert len(session.scalars(select(PollResult)).all()) == len(source_records)
    finally:
        session.close()


def test_database_full_replacement_is_exact_snapshot(tmp_path) -> None:
    database_url = f"sqlite:///{tmp_path / 'full-snapshot.sqlite3'}"
    init_database(database_url)
    session = get_session_factory(database_url)()
    records = normalize_csv_file(Path("data/processed/sample_polls.csv"))
    stale = records[0].model_copy(
        update={
            "poll_id": "stale-other-source",
            "source_url": "https://stale.example/poll",
        }
    )

    try:
        normalize_to_database([stale], session)
        normalize_to_database(records, session, replace_all_polls=True)

        poll_ids = set(session.scalars(select(Poll.poll_id)).all())
        assert poll_ids == {record.poll_id for record in records}
        assert len(session.scalars(select(PollResult)).all()) == len(records)
    finally:
        session.close()


def test_database_full_replacement_refuses_empty_snapshot(tmp_path) -> None:
    database_url = f"sqlite:///{tmp_path / 'empty-snapshot.sqlite3'}"
    init_database(database_url)
    session = get_session_factory(database_url)()
    records = normalize_csv_file(Path("data/processed/sample_polls.csv"))

    try:
        normalize_to_database(records, session)
        stored_before = len(session.scalars(select(Poll)).all())
        assert stored_before > 0

        with pytest.raises(ValueError, match="empty record set"):
            normalize_to_database([], session, replace_all_polls=True)

        assert len(session.scalars(select(Poll)).all()) == stored_before
        assert len(session.scalars(select(PollResult)).all()) == len(records)
    finally:
        session.close()
