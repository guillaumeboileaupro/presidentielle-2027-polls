from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Engine

from presidentielle2027.adjustments.recency_weighting import compute_recency_weights
from presidentielle2027.adjustments.sample_size_weighting import compute_sample_size_weights
from presidentielle2027.extraction.canonicalization import is_generic_bloc_label


JOINED_RESULTS_SQL = """
SELECT
    polls.poll_id,
    polls.publication_date,
    polls.sample_size,
    polls.collection_method,
    polls.round,
    polls.abstention_estimate,
    poll_scenarios.scenario_name,
    polling_companies.name AS polling_company,
    candidates.candidate_name,
    candidates.candidate_party,
    candidates.political_family,
    poll_results.estimate_percent,
    poll_results.margin_of_error
FROM poll_results
JOIN poll_scenarios ON poll_results.scenario_id = poll_scenarios.id
JOIN polls ON poll_scenarios.poll_id = polls.id
JOIN candidates ON poll_results.candidate_id = candidates.id
LEFT JOIN polling_companies ON polls.polling_company_id = polling_companies.id
"""


def load_results_dataframe(engine: Engine) -> pd.DataFrame:
    return pd.read_sql(text(JOINED_RESULTS_SQL), engine)


def compute_weighted_polling_averages(
    frame: pd.DataFrame,
    reference_date: date | None = None,
    lambda_: float = 0.03,
) -> pd.DataFrame:
    if frame.empty:
        return pd.DataFrame(
            columns=[
                "scenario_name",
                "round",
                "candidate_name",
                "weighted_average",
                "poll_count",
                "combined_weight",
            ]
        )

    working = frame.copy()
    working = working.loc[~working["candidate_name"].map(is_generic_bloc_label)].copy()
    if working.empty:
        return pd.DataFrame(
            columns=[
                "scenario_name",
                "round",
                "candidate_name",
                "weighted_average",
                "poll_count",
                "combined_weight",
            ]
        )
    working["publication_date"] = pd.to_datetime(working["publication_date"], errors="coerce")
    working["recency_weight"] = compute_recency_weights(
        working["publication_date"], reference_date=reference_date, lambda_=lambda_
    )
    working["sample_size_weight"] = compute_sample_size_weights(working["sample_size"])
    working["combined_weight"] = (working["recency_weight"] * working["sample_size_weight"]).replace(0, np.nan)
    working["weighted_score"] = working["estimate_percent"] * working["combined_weight"]

    grouped = working.groupby(["scenario_name", "round", "candidate_name"], dropna=False)
    result = grouped.agg(
        weighted_score_sum=("weighted_score", "sum"),
        combined_weight=("combined_weight", "sum"),
        poll_count=("poll_id", "nunique"),
    ).reset_index()
    result["weighted_average"] = result["weighted_score_sum"] / result["combined_weight"]
    return result.drop(columns=["weighted_score_sum"])
