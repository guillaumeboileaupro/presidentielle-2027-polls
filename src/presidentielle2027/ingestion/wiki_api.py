from __future__ import annotations

from dataclasses import dataclass
from html import unescape
from urllib.parse import unquote, urlparse

import requests


@dataclass(frozen=True)
class WikipediaPageSnapshot:
    title: str
    display_title: str
    html: str
    page_id: int | None
    wikidata_item_id: str | None
    revision_id: int | None


def extract_wikipedia_title(source_url: str) -> str:
    parsed = urlparse(source_url)
    path = unquote(parsed.path)
    marker = "/wiki/"
    if marker not in path:
        raise ValueError(f"Impossible d'extraire le titre Wikipédia depuis l'URL: {source_url}")
    return path.split(marker, maxsplit=1)[1].replace("_", " ")


def _api_base_url(source_url: str) -> str:
    parsed = urlparse(source_url)
    return f"{parsed.scheme}://{parsed.netloc}/w/api.php"


def fetch_wikipedia_page_snapshot(source_url: str, timeout: int = 30) -> WikipediaPageSnapshot:
    title = extract_wikipedia_title(source_url)
    api_url = _api_base_url(source_url)
    headers = {"User-Agent": "presidentielle2027-polls/0.1 (+wiki-api-ingestion)"}

    metadata_response = requests.get(
        api_url,
        params={
            "action": "query",
            "prop": "info|pageprops",
            "titles": title,
            "inprop": "url",
            "format": "json",
            "formatversion": "2",
        },
        timeout=timeout,
        headers=headers,
    )
    metadata_response.raise_for_status()
    metadata_payload = metadata_response.json()
    pages = metadata_payload.get("query", {}).get("pages", [])
    if not pages:
        raise ValueError(f"Aucune page retournée par l'API Wikipédia pour {title!r}.")

    page = pages[0]
    if page.get("missing"):
        raise ValueError(f"La page Wikipédia {title!r} est absente.")

    parse_response = requests.get(
        api_url,
        params={
            "action": "parse",
            "page": title,
            "prop": "text|displaytitle|revid",
            "format": "json",
            "formatversion": "2",
        },
        timeout=timeout,
        headers=headers,
    )
    parse_response.raise_for_status()
    parse_payload = parse_response.json().get("parse", {})

    return WikipediaPageSnapshot(
        title=title,
        display_title=unescape(parse_payload.get("displaytitle") or page.get("title") or title),
        html=parse_payload.get("text", ""),
        page_id=page.get("pageid"),
        wikidata_item_id=page.get("pageprops", {}).get("wikibase_item"),
        revision_id=parse_payload.get("revid"),
    )
