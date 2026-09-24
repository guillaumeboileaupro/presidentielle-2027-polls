from __future__ import annotations

from pathlib import Path

import requests

from presidentielle2027.ingestion.source_registry import SourceDefinition
from presidentielle2027.ingestion.wiki_api import (
    extract_wikipedia_title,
    fetch_wikipedia_html,
    fetch_wikipedia_page_snapshot,
)
from presidentielle2027.ingestion.wikipedia_scraper import fetch_wikipedia_tables


class DummyResponse:
    def __init__(self, payload: dict[str, object]) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, object]:
        return self._payload


def test_extract_wikipedia_title() -> None:
    url = "https://fr.wikipedia.org/wiki/Liste_de_sondages_sur_l%27%C3%A9lection_pr%C3%A9sidentielle_fran%C3%A7aise_de_2027"
    assert extract_wikipedia_title(url) == "Liste de sondages sur l'élection présidentielle française de 2027"


def test_fetch_wikipedia_page_snapshot(monkeypatch) -> None:
    responses = [
        DummyResponse(
            {
                "query": {
                    "pages": [
                        {
                            "pageid": 123,
                            "title": "Liste de sondages sur l'élection présidentielle française de 2027",
                            "pageprops": {"wikibase_item": "Q123"},
                        }
                    ]
                }
            }
        ),
        DummyResponse(
            {
                "parse": {
                    "displaytitle": "Liste de sondages sur l&#x27;élection présidentielle française de 2027",
                    "text": "<table><tr><td>ok</td></tr></table>",
                    "revid": 456,
                }
            }
        ),
    ]

    def fake_get(*args, **kwargs):  # type: ignore[no-untyped-def]
        return responses.pop(0)

    monkeypatch.setattr(requests, "get", fake_get)

    snapshot = fetch_wikipedia_page_snapshot(
        "https://fr.wikipedia.org/wiki/Liste_de_sondages_sur_l%27%C3%A9lection_pr%C3%A9sidentielle_fran%C3%A7aise_de_2027"
    )

    assert snapshot.page_id == 123
    assert snapshot.wikidata_item_id == "Q123"
    assert snapshot.revision_id == 456
    assert snapshot.html == "<table><tr><td>ok</td></tr></table>"
    assert snapshot.display_title == "Liste de sondages sur l'élection présidentielle française de 2027"


def test_fetch_wikipedia_html_returns_response_text(monkeypatch) -> None:
    class HtmlResponse:
        text = "<html>ok</html>"

        def raise_for_status(self) -> None:
            return None

    captured_kwargs: dict[str, object] = {}

    def fake_get(url: str, **kwargs: object) -> HtmlResponse:
        captured_kwargs.update(kwargs)
        return HtmlResponse()

    monkeypatch.setattr(requests, "get", fake_get)

    html = fetch_wikipedia_html("https://fr.wikipedia.org/wiki/Test", timeout=5)

    assert html == "<html>ok</html>"
    assert captured_kwargs["timeout"] == 5
    assert "User-Agent" in captured_kwargs["headers"]


def test_fetch_wikipedia_tables_refreshes_stable_cache(monkeypatch, tmp_path: Path) -> None:
    snapshot = type(
        "Snapshot",
        (),
        {
            "html": "<table><tr><th>Sondeur</th></tr><tr><td>Ifop</td></tr></table>",
            "title": "Page de test",
            "display_title": "Page de test",
            "page_id": 123,
            "wikidata_item_id": "Q123",
            "revision_id": 456,
        },
    )()
    monkeypatch.setattr(
        "presidentielle2027.ingestion.wikipedia_scraper.fetch_wikipedia_page_snapshot",
        lambda *args, **kwargs: snapshot,
    )
    source = SourceDefinition("wikipedia_fr_2027_polls", "https://fr.wikipedia.org/wiki/Test", "wikipedia", "fr")
    cache_path = tmp_path / "wikipedia_html" / "presidentielle_2027.html"

    artifact = fetch_wikipedia_tables(source, tmp_path / "raw", cache_path=cache_path)

    assert artifact.cache_path == cache_path
    assert cache_path.read_text(encoding="utf-8") == snapshot.html
    assert artifact.table_count == 1


def test_fetch_wikipedia_tables_preserves_french_decimal_commas(monkeypatch, tmp_path: Path) -> None:
    snapshot = type(
        "Snapshot",
        (),
        {
            "html": "<table><tr><th>Candidat</th></tr><tr><td>1,5</td></tr></table>",
            "title": "Page de test",
            "display_title": "Page de test",
            "page_id": 123,
            "wikidata_item_id": "Q123",
            "revision_id": 456,
        },
    )()
    monkeypatch.setattr(
        "presidentielle2027.ingestion.wikipedia_scraper.fetch_wikipedia_page_snapshot",
        lambda *args, **kwargs: snapshot,
    )
    source = SourceDefinition("wikipedia_fr_2027_polls", "https://fr.wikipedia.org/wiki/Test", "wikipedia", "fr")

    artifact = fetch_wikipedia_tables(source, tmp_path / "raw")

    assert artifact.csv_paths[0].read_text(encoding="utf-8").splitlines()[1] == "1.5"
