from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from presidentielle2027.analytics.historical_corrections import (
    CURRENT_ELECTION_DATE,
    compute_days_bucket,
    load_historical_2022_polls,
    load_historical_2022_results,
    load_manual_first_round_biases,
    normalize_force_label,
)


MIN_POINTS_FOR_SEGMENT_MODEL = 3


@dataclass(frozen=True)
class DynamicBiasContext:
    calibration_frame: pd.DataFrame
    segment_models: pd.DataFrame


def _fit_linear_model(group: pd.DataFrame) -> dict[str, float] | None:
    sample = group.dropna(subset=["days_until_election", "bias"]).copy()
    if len(sample.index) < MIN_POINTS_FOR_SEGMENT_MODEL or sample["days_until_election"].nunique() < 2:
        return None
    x = pd.to_numeric(sample["days_until_election"], errors="coerce").to_numpy(dtype=float)
    y = pd.to_numeric(sample["bias"], errors="coerce").to_numpy(dtype=float)
    slope, intercept = np.polyfit(x, y, 1)
    return {
        "slope": float(slope),
        "intercept": float(intercept),
        "min_days": float(np.nanmin(x)),
        "max_days": float(np.nanmax(x)),
        "n_points": int(len(sample.index)),
        "mean_bias": float(np.nanmean(y)),
    }


def build_dynamic_bias_context(reference_dir: Path) -> DynamicBiasContext:
    polls_2022 = load_historical_2022_polls(reference_dir)
    results_2022 = load_historical_2022_results(reference_dir)
    if polls_2022.empty or results_2022.empty:
        empty = pd.DataFrame()
        return DynamicBiasContext(empty, empty)

    calibration = polls_2022.merge(
        results_2022[["force_label", "result_percent"]],
        on="force_label",
        how="left",
    )
    calibration["days_until_election"] = pd.to_numeric(calibration["days_until_election"], errors="coerce")
    calibration["pollster"] = calibration["pollster"].fillna("Unknown").astype(str)
    calibration["force_label"] = calibration["force_label"].fillna("OTHER").astype(str)
    calibration["bias"] = pd.to_numeric(calibration["result_percent"], errors="coerce") - pd.to_numeric(
        calibration["estimate_percent"],
        errors="coerce",
    )
    calibration["days_bucket"] = compute_days_bucket(calibration["days_until_election"])

    rows: list[dict[str, object]] = []
    segment_specs = [
        ("pollster_force", ["pollster", "force_label"]),
        ("force_only", ["force_label"]),
        ("pollster_only", ["pollster"]),
        ("global", []),
    ]
    for model_level, keys in segment_specs:
        grouped = [((), calibration)] if not keys else calibration.groupby(keys, dropna=False)
        for key, group in grouped:
            fitted = _fit_linear_model(group)
            if fitted is None:
                continue
            key_values = key if isinstance(key, tuple) else (key,)
            row = {
                "model_level": model_level,
                "pollster": None,
                "force_label": None,
                **fitted,
            }
            for idx, column in enumerate(keys):
                row[column] = key_values[idx]
            rows.append(row)
    models = pd.DataFrame(rows)
    return DynamicBiasContext(calibration, models)


def _predict_segment_bias(
    days_until_election: float,
    pollster: str,
    force_label: str,
    models: pd.DataFrame,
) -> tuple[float, str] | tuple[None, str]:
    if models.empty or pd.isna(days_until_election):
        return None, "unavailable"

    candidates = [
        ("pollster_force", (models["model_level"] == "pollster_force") & (models["pollster"] == pollster) & (models["force_label"] == force_label)),
        ("force_only", (models["model_level"] == "force_only") & (models["force_label"] == force_label)),
        ("pollster_only", (models["model_level"] == "pollster_only") & (models["pollster"] == pollster)),
        ("global", models["model_level"] == "global"),
    ]
    for label, mask in candidates:
        subset = models.loc[mask]
        if subset.empty:
            continue
        model = subset.iloc[0]
        clipped_days = float(np.clip(days_until_election, model["min_days"], model["max_days"]))
        predicted = float(model["intercept"] + model["slope"] * clipped_days)
        return predicted, label
    return None, "unavailable"


def apply_dynamic_poll_bias_correction(frame: pd.DataFrame, reference_dir: Path) -> tuple[pd.DataFrame, DynamicBiasContext]:
    context = build_dynamic_bias_context(reference_dir)
    if frame.empty:
        return frame.copy(), context

    working = frame.copy()
    working["polling_company"] = working["polling_company"].fillna("Unknown").astype(str)
    working["force_label"] = working.apply(
        lambda row: normalize_force_label(row.get("candidate_party"), row.get("political_family")),
        axis=1,
    )
    working["publication_date"] = pd.to_datetime(working["publication_date"], errors="coerce")
    working["days_until_election"] = (CURRENT_ELECTION_DATE - working["publication_date"]).dt.days

    predictions = working.apply(
        lambda row: _predict_segment_bias(
            row["days_until_election"],
            row["polling_company"],
            row["force_label"],
            context.segment_models,
        ),
        axis=1,
    )
    working["dynamic_model_source"] = predictions.map(lambda item: item[1])
    working["dynamic_bias_2027"] = predictions.map(lambda item: item[0] if item[0] is not None else 0.0).astype(float)
    manual_biases = load_manual_first_round_biases(reference_dir)
    if not manual_biases.empty:
        manual_map = manual_biases.set_index("force_label")["manual_total_bias"].to_dict()
        manual_values = working["force_label"].map(manual_map)
        manual_mask = manual_values.notna()
        working.loc[manual_mask, "dynamic_bias_2027"] = manual_values.loc[manual_mask].astype(float)
        working.loc[manual_mask, "dynamic_model_source"] = "manual_override"
    working["dynamically_corrected_estimate"] = (
        pd.to_numeric(working["estimate_percent"], errors="coerce").fillna(0.0) + working["dynamic_bias_2027"]
    ).clip(lower=0.0, upper=100.0)
    working["dynamic_correction_applied"] = working["dynamic_model_source"] != "unavailable"
    return working, context
