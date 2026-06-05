from __future__ import annotations

from collections.abc import Iterable

import pandas as pd


CANONICAL_COLUMNS = {
    "pollster": "polling_company",
    "polling company": "polling_company",
    "institute": "polling_company",
    "commissioner": "commissioner",
    "commanditaire": "commissioner",
    "media": "media_partner",
    "publication date": "publication_date",
    "fieldwork": "fieldwork_period",
    "dates": "fieldwork_period",
    "sample": "sample_size",
    "size": "sample_size",
    "population": "population",
    "method": "collection_method",
    "scenario": "scenario_name",
    "round": "round",
    "candidate": "candidate_name",
    "party": "candidate_party",
    "estimate": "estimate_percent",
    "score": "estimate_percent",
}


def canonicalize_columns(columns: Iterable[object]) -> dict[object, str]:
    renamed: dict[object, str] = {}
    for column in columns:
        normalized = " ".join(str(column).lower().split())
        renamed[column] = CANONICAL_COLUMNS.get(normalized, normalized.replace(" ", "_"))
    return renamed


def flatten_multilevel_columns(frame: pd.DataFrame) -> pd.DataFrame:
    if isinstance(frame.columns, pd.MultiIndex):
        frame = frame.copy()
        frame.columns = [
            " ".join(str(value) for value in col if str(value) != "nan").strip() for col in frame.columns
        ]
    return frame


def clean_table(frame: pd.DataFrame) -> pd.DataFrame:
    cleaned = flatten_multilevel_columns(frame)
    cleaned = cleaned.rename(columns=canonicalize_columns(cleaned.columns))
    cleaned.columns = [str(column) for column in cleaned.columns]
    return cleaned.dropna(axis=0, how="all").dropna(axis=1, how="all")

