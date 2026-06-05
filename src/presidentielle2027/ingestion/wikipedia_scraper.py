from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import json

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
    csv_paths: list[Path]
    table_count: int


def _slugify(value: str) -> str:
    return "".join(char.lower() if char.isalnum() else "-" for char in value).strip("-")


def fetch_wikipedia_tables(
    source: SourceDefinition,
    raw_dir: Path,
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

    html_path.write_text(html, encoding="utf-8")
    metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    tables = pd.read_html(html)
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
        csv_paths=csv_paths,
        table_count=len(csv_paths),
    )


def ingest_wikipedia_sources(session: Session, raw_dir: Path) -> list[WikipediaIngestionArtifact]:
    artifacts: list[WikipediaIngestionArtifact] = []
    for source_def in get_default_sources():
        artifact = fetch_wikipedia_tables(source_def, raw_dir=raw_dir)
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
                    "csv_paths": [str(path) for path in artifact.csv_paths],
                },
                message=f"Ingested {artifact.table_count} tables from {source_def.source_name}.",
            )
        )
        artifacts.append(artifact)
    session.commit()
    return artifacts
