from __future__ import annotations

from dataclasses import dataclass

from presidentielle2027.config import get_settings


@dataclass(frozen=True)
class SourceDefinition:
    source_name: str
    source_url: str
    source_type: str
    language: str


def get_default_sources() -> list[SourceDefinition]:
    settings = get_settings()
    return [
        SourceDefinition(
            source_name="wikipedia_fr_2027_polls",
            source_url=settings.wikipedia_fr_url,
            source_type="wikipedia",
            language="fr",
        ),
        SourceDefinition(
            source_name="wikipedia_en_2027_polls",
            source_url=settings.wikipedia_en_url,
            source_type="wikipedia",
            language="en",
        ),
    ]

