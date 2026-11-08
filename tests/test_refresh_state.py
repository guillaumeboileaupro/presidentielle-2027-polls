from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from presidentielle2027.ingestion.refresh_state import (
    RefreshInProgressError,
    is_refresh_running,
    read_refresh_status,
    refresh_lock,
    seconds_since,
    write_refresh_status,
)


def test_refresh_lock_is_exclusive_and_released(tmp_path: Path) -> None:
    lock = tmp_path / "state" / "refresh.lock"

    with refresh_lock(lock):
        assert is_refresh_running(lock)
        with pytest.raises(RefreshInProgressError), refresh_lock(lock):
            pass

    assert not is_refresh_running(lock)
    with refresh_lock(lock):
        pass


def test_status_keeps_last_good_dataset_while_running_or_failing(tmp_path: Path) -> None:
    path = tmp_path / "state" / "refresh_status.json"
    write_refresh_status(
        path,
        state="ok",
        last_success_at="2026-09-24T10:00:00+00:00",
        persisted_rows=3306,
        dataset_sha256="abc",
    )

    running = write_refresh_status(path, state="running", started_at="2026-09-24T11:00:00+00:00")
    failed = write_refresh_status(path, state="error", error="ConnectionError: offline")

    assert running.dataset_sha256 == "abc"
    assert failed.state == "error"
    assert failed.dataset_sha256 == "abc"
    assert failed.persisted_rows == 3306
    assert failed.last_success_at == "2026-09-24T10:00:00+00:00"
    assert read_refresh_status(path) == failed
    assert not list(path.parent.glob("*.tmp"))


def test_missing_or_corrupt_status_is_ignored(tmp_path: Path) -> None:
    path = tmp_path / "refresh_status.json"
    assert read_refresh_status(path) is None
    path.write_text("{not json", encoding="utf-8")
    assert read_refresh_status(path) is None
    path.write_text('["a list"]', encoding="utf-8")
    assert read_refresh_status(path) is None
    path.write_text('{"state": "ok", "unknown_future_field": 1}', encoding="utf-8")
    assert read_refresh_status(path).state == "ok"  # type: ignore[union-attr]


def test_seconds_since() -> None:
    now = datetime(2026, 9, 24, 12, 0, tzinfo=timezone.utc)
    earlier = (now - timedelta(minutes=5)).isoformat()
    assert seconds_since(earlier, now=now) == pytest.approx(300)
    assert seconds_since(None) is None
    assert seconds_since("garbage") is None
