from __future__ import annotations

from typing import Any

import requests

from presidentielle2027.ingestion.wiki_api import extract_wikipedia_title, fetch_wikipedia_page_snapshot


class DummyResponse:
    def __init__(self, payload: dict[str, Any]) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, Any]:
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
