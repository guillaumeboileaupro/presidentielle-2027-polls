from presidentielle2027.ingestion.pdf_collector import download_pdf
from presidentielle2027.ingestion.source_registry import get_default_sources
from presidentielle2027.ingestion.wikipedia_scraper import ingest_wikipedia_sources

__all__ = ["download_pdf", "get_default_sources", "ingest_wikipedia_sources"]

