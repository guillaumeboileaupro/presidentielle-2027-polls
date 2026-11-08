"""What the dashboard knows about the automatic refresh: data version and status text."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError

from presidentielle2027.config import Settings
from presidentielle2027.ingestion.refresh_state import (
    is_refresh_running,
    lock_path,
    read_refresh_status,
    status_path,
)


def _sqlite_file(database_url: str) -> Path | None:
    try:
        url = make_url(database_url)
    except ArgumentError:
        return None
    if url.get_backend_name() != "sqlite" or not url.database or url.database == ":memory:":
        return None
    return Path(url.database)


def dashboard_data_version(settings: Settings) -> str:
    """A string that changes exactly when the displayed dataset changes.

    Used as the cache key of the dashboard data, so a refresh that produced new data
    shows up without restarting the app, while a refresh that changed nothing (same
    dataset hash) keeps every cached figure.
    """
    status = read_refresh_status(status_path(settings.interim_dir))
    if status is not None and status.dataset_sha256:
        return status.dataset_sha256
    candidates = [
        _sqlite_file(settings.database_url),
        settings.processed_dir / "wikipedia_2027_polls_normalized_v2.csv",
        settings.processed_dir / "wikipedia_2027_polls_normalized.csv",
        settings.processed_dir / "sample_polls.csv",
    ]
    parts = []
    for path in candidates:
        if path is not None and path.exists():
            info = path.stat()
            parts.append(f"{path.name}:{info.st_mtime_ns}:{info.st_size}")
    return "|".join(parts) or "no-data"


def _local(timestamp: str | None) -> str | None:
    if not timestamp:
        return None
    try:
        moment = datetime.fromisoformat(timestamp)
    except ValueError:
        return None
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment.astimezone().strftime("%d/%m/%Y à %H:%M")


def describe_refresh(settings: Settings) -> str:
    """One French sentence on the state of the automatic Wikipedia collection."""
    status = read_refresh_status(status_path(settings.interim_dir))
    last_success = _local(status.last_success_at) if status is not None else None
    displayed = (
        f"les données affichées datent de la collecte du {last_success}"
        if last_success
        else "les données affichées sont celles déjà présentes sur ce poste"
    )
    # The lock is still held for an instant after the final status is written, so a
    # finished refresh must not be reported as running.
    lock_held = is_refresh_running(lock_path(settings.interim_dir))
    if lock_held and (status is None or status.state == "running"):
        return f"Collecte Wikipédia en cours : {displayed}."
    if status is None:
        if settings.auto_ingest_with_dashboard:
            return f"Collecte Wikipédia automatique en attente : {displayed}."
        return (
            "Collecte Wikipédia automatique désactivée (AUTO_INGEST_WITH_DASHBOARD=false) : "
            f"{displayed}."
        )
    if status.state == "error":
        return (
            f"Dernière collecte Wikipédia en échec ({status.error}) : {displayed}. "
            "Nouvelle tentative automatique."
        )
    if last_success:
        return (
            f"Données Wikipédia collectées le {last_success} ; "
            f"nouvelle vérification automatique toutes les {settings.auto_ingest_interval_minutes} min."
        )
    return f"Collecte Wikipédia : {displayed}."
