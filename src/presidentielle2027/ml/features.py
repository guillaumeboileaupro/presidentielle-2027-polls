from __future__ import annotations

from datetime import date

import pandas as pd


FEATURE_COLUMNS = [
    "polling_company",
    "candidate_party",
    "political_family",
    "days_until_election",
    "sample_size",
    "collection_method",
    "round",
    "scenario_size",
    "publication_month",
]


def build_feature_frame(frame: pd.DataFrame, election_date: date) -> pd.DataFrame:
    working = frame.copy()
    working["publication_date"] = pd.to_datetime(working["publication_date"], errors="coerce")
    working["days_until_election"] = (
        pd.Timestamp(election_date) - working["publication_date"]
    ).dt.days.fillna(0)
    working["sample_size"] = pd.to_numeric(working["sample_size"], errors="coerce").fillna(0)
    working["scenario_size"] = working.groupby(["poll_id", "scenario_name"], dropna=False)["candidate_name"].transform("count")
    working["publication_month"] = working["publication_date"].dt.month.fillna(0).astype(int)
    return working[FEATURE_COLUMNS]

