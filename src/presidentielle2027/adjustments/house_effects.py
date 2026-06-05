from __future__ import annotations

import pandas as pd

from presidentielle2027.extraction.canonicalization import is_generic_bloc_label


def estimate_house_effects(frame: pd.DataFrame, window_days: int = 45) -> pd.DataFrame:
    required = {"polling_company", "scenario_name", "candidate_name", "estimate_percent", "publication_date", "round"}
    missing = required.difference(frame.columns)
    if missing:
        raise ValueError(f"Missing columns for house effect estimation: {sorted(missing)}")

    working = frame.copy()
    working = working.loc[~working["candidate_name"].map(is_generic_bloc_label)].copy()
    working["publication_date"] = pd.to_datetime(working["publication_date"], errors="coerce")
    working["estimate_percent"] = pd.to_numeric(working["estimate_percent"], errors="coerce")

    residual_rows: list[dict[str, object]] = []
    for row in working.itertuples(index=False):
        if pd.isna(row.publication_date) or pd.isna(row.estimate_percent):
            continue
        peers = working.loc[
            (working["scenario_name"] == row.scenario_name)
            & (working["candidate_name"] == row.candidate_name)
            & (working["round"] == row.round)
            & (working["polling_company"] != row.polling_company)
            & (working["publication_date"].notna())
        ].copy()
        if peers.empty:
            continue
        age_delta = (peers["publication_date"] - row.publication_date).abs().dt.days
        peers = peers.loc[age_delta <= window_days]
        if len(peers) < 2:
            continue
        baseline = peers["estimate_percent"].mean()
        residual_rows.append(
            {
                "polling_company": row.polling_company,
                "candidate_name": row.candidate_name,
                "round": row.round,
                "house_effect": float(row.estimate_percent - baseline),
            }
        )

    residuals = pd.DataFrame(residual_rows)
    if residuals.empty:
        return pd.DataFrame(columns=["polling_company", "candidate_name", "round", "house_effect"])

    return (
        residuals.groupby(["polling_company", "candidate_name", "round"], dropna=False)["house_effect"]
        .mean()
        .rename("house_effect")
        .reset_index()
    )


def apply_house_effect_adjustment(frame: pd.DataFrame, effects: pd.DataFrame) -> pd.DataFrame:
    merged = frame.merge(effects, on=["polling_company", "candidate_name", "round"], how="left")
    merged["house_effect"] = pd.to_numeric(merged["house_effect"], errors="coerce").fillna(0.0)
    merged["adjusted_estimate_house_effect"] = merged["estimate_percent"] - merged["house_effect"]
    return merged
