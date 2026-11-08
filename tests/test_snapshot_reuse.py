from __future__ import annotations

import json
from pathlib import Path

import pytest

from presidentielle2027.ingestion import wikipedia_scraper
from presidentielle2027.ingestion.source_registry import SourceDefinition
from presidentielle2027.ingestion.wikipedia_scraper import (
    TABLE_EXTRACTION_VERSION,
    _html_fingerprint,
    fetch_wikipedia_tables,
)

PAGE = "<table><tr><th>Sondeur</th><th>Score</th></tr><tr><td>Ifop</td><td>1,5</td></tr></table>"
SOURCE = SourceDefinition("wikipedia_fr_2027_polls", "https://fr.wikipedia.org/wiki/Test", "wikipedia", "fr")


def _serve(monkeypatch: pytest.MonkeyPatch, *, revision: int | None, html: str = PAGE) -> None:
    snapshot = type(
        "Snapshot",
        (),
        {
            "html": html,
            "title": "Page de test",
            "display_title": "Page de test",
            "page_id": 1,
            "wikidata_item_id": "Q1",
            "revision_id": revision,
        },
    )()
    monkeypatch.setattr(wikipedia_scraper, "fetch_wikipedia_page_snapshot", lambda *a, **k: snapshot)


def _files(raw_dir: Path) -> set[str]:
    return {path.name for path in raw_dir.iterdir()}


def test_unchanged_revision_reuses_snapshot_instead_of_writing_new_files(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    raw_dir = tmp_path / "raw"
    _serve(monkeypatch, revision=100)

    first = fetch_wikipedia_tables(SOURCE, raw_dir)
    files_after_first = _files(raw_dir)
    second = fetch_wikipedia_tables(SOURCE, raw_dir)

    assert not first.unchanged
    assert second.unchanged
    assert _files(raw_dir) == files_after_first
    assert second.html_path == first.html_path
    assert second.csv_paths == first.csv_paths
    assert second.table_count == first.table_count == 1


def test_new_revision_writes_a_new_snapshot_and_keeps_the_old_one(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    raw_dir = tmp_path / "raw"
    _serve(monkeypatch, revision=100)
    first = fetch_wikipedia_tables(SOURCE, raw_dir)
    monkeypatch.setattr(
        wikipedia_scraper,
        "datetime",
        type("D", (), {"now": staticmethod(lambda tz=None: __import__("datetime").datetime(2030, 1, 1, tzinfo=tz))}),
    )

    _serve(monkeypatch, revision=101)
    second = fetch_wikipedia_tables(SOURCE, raw_dir)

    assert not second.unchanged
    assert second.html_path != first.html_path
    assert first.html_path.exists() and first.csv_paths[0].exists()


def test_snapshot_from_an_older_extraction_version_is_not_reused(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A snapshot extracted before the decimal-comma fix must be re-extracted once."""
    raw_dir = tmp_path / "raw"
    _serve(monkeypatch, revision=100)
    first = fetch_wikipedia_tables(SOURCE, raw_dir)
    metadata = json.loads(first.metadata_path.read_text(encoding="utf-8"))
    assert metadata["extraction_version"] == TABLE_EXTRACTION_VERSION
    del metadata["extraction_version"]
    first.metadata_path.write_text(json.dumps(metadata), encoding="utf-8")
    monkeypatch.setattr(
        wikipedia_scraper,
        "datetime",
        type("D", (), {"now": staticmethod(lambda tz=None: __import__("datetime").datetime(2031, 1, 1, tzinfo=tz))}),
    )

    second = fetch_wikipedia_tables(SOURCE, raw_dir)

    assert not second.unchanged
    assert second.csv_paths != first.csv_paths


def test_incomplete_snapshot_without_tables_is_not_reused(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    raw_dir = tmp_path / "raw"
    _serve(monkeypatch, revision=100)
    first = fetch_wikipedia_tables(SOURCE, raw_dir)
    for csv_path in first.csv_paths:
        csv_path.unlink()
    monkeypatch.setattr(
        wikipedia_scraper,
        "datetime",
        type("D", (), {"now": staticmethod(lambda tz=None: __import__("datetime").datetime(2032, 1, 1, tzinfo=tz))}),
    )

    assert not fetch_wikipedia_tables(SOURCE, raw_dir).unchanged


def test_html_fingerprint_ignores_render_comments() -> None:
    a = "<p>same</p><!-- Render ID 1 -->"
    b = "<p>same</p><!-- Render ID 2 -->"
    assert _html_fingerprint(a) == _html_fingerprint(b)
    assert _html_fingerprint(a) != _html_fingerprint("<p>different</p>")
