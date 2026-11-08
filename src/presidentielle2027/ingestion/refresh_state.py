"""Shared state of the automatic refresh: a process lock and a small status file.

The scraper runs as a background process next to the dashboard, so both need a
way to talk without importing each other: the lock prevents two refreshes from
writing the same database and CSV files, and the status file tells the dashboard
whether a refresh is running, when data last changed, and what went wrong.
"""

from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import asdict, dataclass, fields
from datetime import datetime, timezone
from pathlib import Path

try:
    import fcntl
except ImportError:  # pragma: no cover - non-POSIX platforms run without a lock
    fcntl = None  # type: ignore[assignment]

STATUS_FILENAME = "refresh_status.json"
LOCK_FILENAME = "refresh.lock"


class RefreshInProgressError(RuntimeError):
    """Raised when another process already holds the refresh lock."""


@dataclass(frozen=True)
class RefreshStatus:
    state: str = "unknown"  # running | ok | error
    started_at: str | None = None
    finished_at: str | None = None
    last_success_at: str | None = None
    persisted_rows: int | None = None
    dataset_sha256: str | None = None
    error: str | None = None


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def status_path(state_dir: Path) -> Path:
    return state_dir / STATUS_FILENAME


def lock_path(state_dir: Path) -> Path:
    return state_dir / LOCK_FILENAME


def read_refresh_status(path: Path) -> RefreshStatus | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(payload, dict):
        return None
    known = {field.name for field in fields(RefreshStatus)}
    return RefreshStatus(**{key: value for key, value in payload.items() if key in known})


def write_refresh_status(path: Path, **updates: object) -> RefreshStatus:
    """Merge ``updates`` into the stored status and replace the file atomically.

    ``last_success_at``, ``persisted_rows`` and ``dataset_sha256`` describe the last
    good dataset, so they are carried over while a refresh is running or has failed.
    """
    previous = read_refresh_status(path) or RefreshStatus()
    merged = RefreshStatus(**{**asdict(previous), **updates})
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f"{path.name}.{os.getpid()}.tmp")
    temporary.write_text(json.dumps(asdict(merged), ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(temporary, path)
    return merged


@contextmanager
def refresh_lock(path: Path) -> Iterator[None]:
    """Hold the exclusive refresh lock, or raise ``RefreshInProgressError``.

    The lock belongs to the process, so it disappears with it: a crashed scraper
    cannot leave a stale lock behind.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+") as handle:
        if fcntl is not None:
            try:
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError as exc:
                raise RefreshInProgressError("Another refresh is already running.") from exc
        yield


def is_refresh_running(path: Path) -> bool:
    """True when a live process currently holds the refresh lock."""
    try:
        with refresh_lock(path):
            return False
    except RefreshInProgressError:
        return True


def seconds_since(timestamp: str | None, *, now: datetime | None = None) -> float | None:
    if not timestamp:
        return None
    try:
        moment = datetime.fromisoformat(timestamp)
    except ValueError:
        return None
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return ((now or datetime.now(timezone.utc)) - moment).total_seconds()


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()
