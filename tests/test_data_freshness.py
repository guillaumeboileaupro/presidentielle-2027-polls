from __future__ import annotations

import os
from pathlib import Path

from presidentielle2027.config import Settings
from presidentielle2027.dashboard.data_freshness import dashboard_data_version, describe_refresh
from presidentielle2027.ingestion.refresh_state import (
    lock_path,
    refresh_lock,
    status_path,
    write_refresh_status,
)


def _settings(tmp_path: Path, **kwargs: object) -> Settings:
    settings = Settings(DATABASE_URL=f"sqlite:///{tmp_path / 'polls.sqlite3'}", **kwargs)  # type: ignore[arg-type]
    settings.interim_dir = tmp_path / "interim"
    settings.processed_dir = tmp_path / "processed"
    return settings


def test_version_follows_the_dataset_hash_not_the_refresh_time(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    target = status_path(settings.interim_dir)

    write_refresh_status(target, state="ok", dataset_sha256="aaa", finished_at="2026-09-24T10:00:00+00:00")
    first = dashboard_data_version(settings)
    write_refresh_status(target, state="ok", dataset_sha256="aaa", finished_at="2026-09-24T11:00:00+00:00")
    unchanged_data = dashboard_data_version(settings)
    write_refresh_status(target, state="ok", dataset_sha256="bbb", finished_at="2026-09-24T12:00:00+00:00")
    changed_data = dashboard_data_version(settings)
    write_refresh_status(target, state="error", error="offline")
    after_failure = dashboard_data_version(settings)

    assert first == unchanged_data == "aaa"
    assert changed_data == after_failure == "bbb"


def test_version_falls_back_to_file_state_before_any_refresh(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    assert dashboard_data_version(settings) == "no-data"

    settings.processed_dir.mkdir(parents=True)
    csv = settings.processed_dir / "wikipedia_2027_polls_normalized_v2.csv"
    csv.write_text("a\n1\n", encoding="utf-8")
    before = dashboard_data_version(settings)
    csv.write_text("a\n1\n2\n", encoding="utf-8")
    os.utime(csv, ns=(1, 2_000_000_000))

    assert before != "no-data"
    assert dashboard_data_version(settings) != before


def test_status_sentence_covers_each_state(tmp_path: Path) -> None:
    enabled = _settings(tmp_path, AUTO_INGEST_WITH_DASHBOARD=True)
    disabled = _settings(tmp_path / "off", AUTO_INGEST_WITH_DASHBOARD=False)
    assert "en attente" in describe_refresh(enabled)
    assert "désactivée" in describe_refresh(disabled)

    target = status_path(enabled.interim_dir)
    write_refresh_status(
        target,
        state="ok",
        last_success_at="2026-09-24T21:00:00+00:00",
        dataset_sha256="x",
    )
    ok = describe_refresh(enabled)
    assert "collectées le" in ok and "toutes les 60 min" in ok

    write_refresh_status(target, state="error", error="ConnectionError: offline")
    failed = describe_refresh(enabled)
    assert "en échec" in failed and "ConnectionError: offline" in failed
    assert "datent de la collecte du" in failed  # last good data is still what is displayed

    with refresh_lock(lock_path(enabled.interim_dir)):
        # lock still held but the run already reported its outcome: not "running" anymore
        assert "en cours" not in describe_refresh(enabled)
        write_refresh_status(target, state="running")
        assert "en cours" in describe_refresh(enabled)

    # a crashed run leaves state=running behind, but no live process holds the lock
    assert "en cours" not in describe_refresh(enabled)
