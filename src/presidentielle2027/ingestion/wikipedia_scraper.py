from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from io import StringIO
from pathlib import Path

import pandas as pd
import requests
from bs4 import BeautifulSoup
from sqlalchemy import select
from sqlalchemy.orm import Session

from presidentielle2027.db.models import IngestionLog, Source
from presidentielle2027.ingestion.source_registry import SourceDefinition, get_default_sources
from presidentielle2027.ingestion.wiki_api import fetch_wikipedia_page_snapshot


@dataclass
class WikipediaIngestionArtifact:
    source_name: str
    source_url: str
    html_path: Path
    metadata_path: Path
    cache_path: Path | None
    csv_paths: list[Path]
    table_count: int
    unchanged: bool = False


# Bump when the way tables are extracted from the HTML changes (for example the French
# decimal-comma fix): older snapshots then stop being reused and are re-extracted once.
TABLE_EXTRACTION_VERSION = 2


def _slugify(value: str) -> str:
    return "".join(char.lower() if char.isalnum() else "-" for char in value).strip("-")


def _html_fingerprint(html: str) -> str:
    """Hash of the page markup without HTML comments (render ids, parser-cache stamps)."""
    return hashlib.sha256(re.sub(r"<!--.*?-->", "", html, flags=re.DOTALL).encode("utf-8")).hexdigest()


def _find_reusable_snapshot(
    raw_dir: Path,
    slug: str,
    metadata: Mapping[str, object],
    html: str,
) -> tuple[Path, Path, list[Path]] | None:
    """Return the latest stored snapshot when it is the same page revision, else None.

    Reusing it keeps one snapshot per distinct Wikipedia revision, so an hourly refresh
    does not add ~25 identical files each time while provenance is preserved.
    """
    pattern = re.compile(rf"^{re.escape(slug)}-(\d{{8}}T\d{{6}}Z)\.json$")
    candidates = sorted(
        (path for path in raw_dir.glob(f"{slug}-*.json") if pattern.match(path.name)),
        key=lambda path: path.name,
    )
    if not candidates:
        return None
    metadata_path = candidates[-1]
    stamp = pattern.match(metadata_path.name).group(1)  # type: ignore[union-attr]
    html_path = raw_dir / f"{slug}-{stamp}.html"
    csv_paths = sorted(raw_dir.glob(f"{slug}-{stamp}-table-*.csv"))
    try:
        stored = json.loads(metadata_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(stored, dict) or not html_path.exists() or not csv_paths:
        return None
    if stored.get("extraction_version") != metadata["extraction_version"]:
        return None
    revision = metadata.get("revision_id")
    if revision is not None:
        same_page = stored.get("revision_id") == revision
    else:
        same_page = stored.get("revision_id") is None and _html_fingerprint(
            html_path.read_text(encoding="utf-8")
        ) == _html_fingerprint(html)
    return (html_path, metadata_path, csv_paths) if same_page else None


def fetch_wikipedia_tables(
    source: SourceDefinition,
    raw_dir: Path,
    cache_path: Path | None = None,
    timeout: int = 30,
) -> WikipediaIngestionArtifact:
    raw_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    slug = _slugify(source.source_name)
    html_path = raw_dir / f"{slug}-{timestamp}.html"
    metadata_path = raw_dir / f"{slug}-{timestamp}.json"

    try:
        snapshot = fetch_wikipedia_page_snapshot(source.source_url, timeout=timeout)
        html = snapshot.html
        title = snapshot.display_title or source.source_name
        metadata = {
            "title": snapshot.title,
            "display_title": snapshot.display_title,
            "page_id": snapshot.page_id,
            "wikidata_item_id": snapshot.wikidata_item_id,
            "revision_id": snapshot.revision_id,
            "source_url": source.source_url,
            "fetch_method": "mediawiki_api",
        }
    except (requests.RequestException, ValueError):
        response = requests.get(source.source_url, timeout=timeout)
        response.raise_for_status()
        html = response.text
        soup = BeautifulSoup(html, "lxml")
        title = soup.title.text.strip() if soup.title else source.source_name
        metadata = {
            "title": source.source_name,
            "display_title": title,
            "page_id": None,
            "wikidata_item_id": None,
            "revision_id": None,
            "source_url": source.source_url,
            "fetch_method": "direct_html_fallback",
        }

    metadata["extraction_version"] = TABLE_EXTRACTION_VERSION
    if cache_path is not None:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(html, encoding="utf-8")
    reusable = _find_reusable_snapshot(raw_dir, slug, metadata, html)
    if reusable is not None:
        reused_html, reused_metadata, reused_csvs = reusable
        return WikipediaIngestionArtifact(
            source_name=title,
            source_url=source.source_url,
            html_path=reused_html,
            metadata_path=reused_metadata,
            cache_path=cache_path,
            csv_paths=reused_csvs,
            table_count=len(reused_csvs),
            unchanged=True,
        )
    html_path.write_text(html, encoding="utf-8")
    metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    # French polling tables use commas as decimal separators.  pandas treats
    # commas as thousands separators by default, silently turning ``1,5``
    # into ``15`` (notably for Nicolas Dupont-Aignan's scores).
    tables = pd.read_html(StringIO(html), decimal=",", thousands=None)
    csv_paths: list[Path] = []
    for index, frame in enumerate(tables, start=1):
        csv_path = raw_dir / f"{slug}-{timestamp}-table-{index:02d}.csv"
        frame.to_csv(csv_path, index=False)
        csv_paths.append(csv_path)

    return WikipediaIngestionArtifact(
        source_name=title,
        source_url=source.source_url,
        html_path=html_path,
        metadata_path=metadata_path,
        cache_path=cache_path,
        csv_paths=csv_paths,
        table_count=len(csv_paths),
    )


def ingest_wikipedia_sources(
    session: Session,
    raw_dir: Path,
    wikipedia_cache_dir: Path | None = None,
) -> list[WikipediaIngestionArtifact]:
    artifacts: list[WikipediaIngestionArtifact] = []
    for source_def in get_default_sources():
        cache_path = None
        if wikipedia_cache_dir is not None and source_def.source_name == "wikipedia_fr_2027_polls":
            cache_path = wikipedia_cache_dir / "presidentielle_2027.html"
        artifact = fetch_wikipedia_tables(source_def, raw_dir=raw_dir, cache_path=cache_path)
        source = session.scalar(select(Source).where(Source.source_url == source_def.source_url))
        if source is None:
            source = Source(
                source_name=source_def.source_name,
                source_url=source_def.source_url,
                source_type=source_def.source_type,
                language=source_def.language,
            )
            session.add(source)
            session.flush()
        source.raw_storage_path = str(artifact.html_path)
        source.last_fetched_at = datetime.now(timezone.utc)
        session.add(
            IngestionLog(
                source_id=source.id,
                action="ingest_wikipedia",
                status="success",
                details={
                    "table_count": artifact.table_count,
                    "html_path": str(artifact.html_path),
                    "metadata_path": str(artifact.metadata_path),
                    "cache_path": str(artifact.cache_path) if artifact.cache_path else None,
                    "unchanged": artifact.unchanged,
                    "csv_paths": [str(path) for path in artifact.csv_paths],
                },
                message=(
                    f"Ingested {artifact.table_count} tables from {source_def.source_name}"
                    + (" (page revision unchanged, existing snapshot reused)." if artifact.unchanged else ".")
                ),
            )
        )
        artifacts.append(artifact)
    session.commit()
    return artifacts
