from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
import pandas as pd

MIN_POINTS_FOR_TREND = 5
MAX_AUTO_POLYNOMIAL_DEGREE = 5
PACKET_GAP_DAYS = 3


@dataclass(frozen=True)
class TrendFitQuality:
    rmse: float
    mae: float
    max_abs_error: float
    point_count: int


@dataclass(frozen=True)
class AdaptiveCurveResult:
    curve: pd.DataFrame
    order_label: str
    fit_quality: TrendFitQuality


def _prepare_xy(dates: pd.Series, values: pd.Series, *, collapse_packets: bool = True) -> pd.DataFrame:
    prepared = pd.DataFrame(
        {
            "date": pd.to_datetime(dates, errors="coerce"),
            "value": pd.to_numeric(values, errors="coerce"),
        }
    ).dropna()
    if prepared.empty:
        return prepared
    prepared = prepared.sort_values("date")
    if not collapse_packets:
        prepared = prepared.drop_duplicates(subset=["date"], keep="last")
        base_date = pd.Timestamp(prepared["date"].iloc[0])
        prepared["date_num"] = ((prepared["date"] - base_date) / pd.Timedelta(days=1)).astype(float)
        return prepared
    ordered_dates = prepared["date"].tolist()
    ordered_values = prepared["value"].tolist()
    collapsed_dates: list[pd.Timestamp] = []
    collapsed_values: list[float] = []
    current_dates = [pd.Timestamp(ordered_dates[0])]
    current_sum = float(ordered_values[0])
    current_count = 1
    for index in range(1, len(ordered_dates)):
        next_date = pd.Timestamp(ordered_dates[index])
        next_value = float(ordered_values[index])
        current_anchor = current_dates[-1]
        if (next_date - current_anchor) / pd.Timedelta(days=1) <= PACKET_GAP_DAYS:
            current_dates.append(next_date)
            current_sum += next_value
            current_count += 1
            continue
        mean_timestamp = int(round(sum(item.value for item in current_dates) / float(len(current_dates))))
        collapsed_dates.append(pd.Timestamp(mean_timestamp))
        collapsed_values.append(current_sum / float(current_count))
        current_dates = [next_date]
        current_sum = next_value
        current_count = 1
    mean_timestamp = int(round(sum(item.value for item in current_dates) / float(len(current_dates))))
    collapsed_dates.append(pd.Timestamp(mean_timestamp))
    collapsed_values.append(current_sum / float(current_count))
    prepared = pd.DataFrame({"date": collapsed_dates, "value": collapsed_values})
    base_date = pd.Timestamp(prepared["date"].iloc[0])
    prepared["date_num"] = ((prepared["date"] - base_date) / pd.Timedelta(days=1)).astype(float)
    return prepared


def _fit_polynomial(
    prepared: pd.DataFrame,
    degree: int,
) -> tuple[np.ndarray, float, float] | None:
    if len(prepared.index) < max(MIN_POINTS_FOR_TREND, degree + 1):
        return None

    x = prepared["date_num"].to_numpy(dtype=float)
    y = prepared["value"].to_numpy(dtype=float)
    x_center = float(np.mean(x))
    x_scale = float(np.std(x))
    if not np.isfinite(x_scale) or x_scale == 0.0:  # pragma: no cover
        x_scale = 1.0
    x_scaled = (x - x_center) / x_scale

    try:
        vandermonde = np.vander(x_scaled, degree + 1, increasing=True)
        coefficients, *_residuals = np.linalg.lstsq(vandermonde, y, rcond=None)
    except (np.linalg.LinAlgError, ValueError):  # pragma: no cover
        return None
    return coefficients, x_center, x_scale


def _evaluate_polynomial(coefficients: np.ndarray, x_center: float, x_scale: float, x_values: np.ndarray) -> np.ndarray:
    scaled_values = (x_values - x_center) / x_scale
    vandermonde = np.vander(scaled_values, len(coefficients), increasing=True)
    return vandermonde @ coefficients


def build_polynomial_curve(
    frame: pd.DataFrame,
    value_column: str,
    date_column: str = "publication_date",
    degree: int = 3,
    dense_points: int = 500,
) -> pd.DataFrame | None:
    prepared = _prepare_xy(frame[date_column], frame[value_column])
    fit = _fit_polynomial(prepared, degree=degree)
    if fit is None:
        return None
    coefficients, x_center, x_scale = fit
    dense_x = np.linspace(
        float(prepared["date_num"].iloc[0]),
        float(prepared["date_num"].iloc[-1]),
        num=max(dense_points, len(prepared.index)),
    )
    dense_y = np.clip(_evaluate_polynomial(coefficients, x_center, x_scale, dense_x), 0.0, 100.0)
    return pd.DataFrame(
        {
            "publication_date": prepared["date"].iloc[0] + pd.to_timedelta(dense_x, unit="D"),
            "score_smooth": dense_y,
        }
    )


def build_interpolated_curve(
    frame: pd.DataFrame,
    value_column: str,
    date_column: str = "publication_date",
    dense_points: int = 500,
) -> pd.DataFrame | None:
    prepared = _prepare_xy(frame[date_column], frame[value_column])
    if len(prepared.index) < 2:
        return None
    x = prepared["date_num"].to_numpy(dtype=float)
    y = prepared["value"].to_numpy(dtype=float)
    dense_x = np.linspace(float(x[0]), float(x[-1]), num=max(dense_points, len(prepared.index)))
    dense_x = np.unique(np.concatenate([dense_x, x]))
    dense_y = np.interp(dense_x, x, y)
    return pd.DataFrame(
        {
            "publication_date": prepared["date"].iloc[0] + pd.to_timedelta(dense_x, unit="D"),
            "score_smooth": np.clip(dense_y, 0.0, 100.0),
        }
    )


def evaluate_curve_fit(
    frame: pd.DataFrame,
    curve: pd.DataFrame,
    value_column: str,
    date_column: str = "publication_date",
) -> TrendFitQuality | None:
    prepared = _prepare_xy(frame[date_column], frame[value_column])
    if prepared.empty or curve.empty:
        return None
    prepared_curve = _prepare_xy(curve["publication_date"], curve["score_smooth"], collapse_packets=False)
    if len(prepared_curve.index) < 2:
        return None
    observed_x = prepared["date_num"].to_numpy(dtype=float)
    curve_x = prepared_curve["date_num"].to_numpy(dtype=float)
    curve_y = prepared_curve["value"].to_numpy(dtype=float)
    interpolated = np.interp(observed_x, curve_x, curve_y)
    errors = prepared["value"].to_numpy(dtype=float) - interpolated
    absolute_errors = np.abs(errors)
    return TrendFitQuality(
        rmse=float(np.sqrt(np.mean(np.square(errors)))),
        mae=float(np.mean(absolute_errors)),
        max_abs_error=float(np.max(absolute_errors)),
        point_count=int(len(prepared.index)),
    )


def _evaluate_polynomial_degree(
    prepared: pd.DataFrame,
    degree: int,
) -> tuple[float, float, float, float] | None:
    if len(prepared.index) < max(MIN_POINTS_FOR_TREND, degree + 2):
        return None

    x_values = prepared["date_num"].to_numpy(dtype=float)
    y_values = prepared["value"].to_numpy(dtype=float)
    date_values = prepared["date"].to_numpy()
    holdout_absolute_errors: list[float] = []
    holdout_squared_errors: list[float] = []
    for index in range(len(prepared.index)):
        mask = np.ones(len(prepared.index), dtype=bool)
        mask[index] = False
        train = pd.DataFrame(
            {
                "date": pd.to_datetime(date_values[mask]),
                "value": y_values[mask],
                "date_num": x_values[mask],
            }
        )
        fit = _fit_polynomial(train, degree=degree)
        if fit is None:
            return None
        coefficients, x_center, x_scale = fit
        x_value = np.array([float(x_values[index])], dtype=float)
        prediction = float(np.clip(_evaluate_polynomial(coefficients, x_center, x_scale, x_value)[0], 0.0, 100.0))
        truth = float(y_values[index])
        error = truth - prediction
        holdout_absolute_errors.append(abs(error))
        holdout_squared_errors.append(error * error)

    fit = _fit_polynomial(prepared, degree=degree)
    if fit is None:
        return None
    coefficients, x_center, x_scale = fit
    dense_x = np.linspace(
        float(prepared["date_num"].iloc[0]),
        float(prepared["date_num"].iloc[-1]),
        num=max(500, len(prepared.index) * 20),
    )
    dense_y = _evaluate_polynomial(coefficients, x_center, x_scale, dense_x)
    roughness = float(np.mean(np.abs(np.diff(dense_y, n=2)))) if len(dense_y) >= 3 else 0.0
    clipped_share = float(np.mean((dense_y <= 0.5) | (dense_y >= 99.5)))
    overshoot = float(np.mean((dense_y < -5.0) | (dense_y > 105.0)))
    observed_min = float(np.min(y_values))
    observed_max = float(np.max(y_values))
    envelope_violation = float(
        np.mean((dense_y < observed_min - 2.0) | (dense_y > observed_max + 2.0))
    )
    first_diff = np.diff(dense_y)
    significant_first = first_diff[np.abs(first_diff) >= 0.05]
    turning_count = 0
    if len(significant_first) >= 2:
        turning_count = int(np.sum(np.sign(significant_first[1:]) != np.sign(significant_first[:-1])))
    second_diff = np.diff(dense_y, n=2)
    significant_second = second_diff[np.abs(second_diff) >= 0.02]
    inflection_count = 0
    if len(significant_second) >= 2:
        inflection_count = int(np.sum(np.sign(significant_second[1:]) != np.sign(significant_second[:-1])))
    mae = float(np.mean(np.array(holdout_absolute_errors, dtype=float)))
    rmse = float(np.sqrt(np.mean(np.array(holdout_squared_errors, dtype=float))))
    score = (
        mae
        + (0.9 * rmse)
        + (12.0 * clipped_share)
        + (12.0 * overshoot)
        + (8.0 * envelope_violation)
        + (0.04 * roughness)
        + (0.9 * float(turning_count))
        + (0.35 * float(inflection_count))
        + (0.6 * float(degree))
    )
    return mae, rmse, clipped_share, score


def select_auto_polynomial_degree(
    frame: pd.DataFrame,
    value_column: str,
    date_column: str = "publication_date",
    max_degree: int = MAX_AUTO_POLYNOMIAL_DEGREE,
) -> int:
    prepared = _prepare_xy(frame[date_column], frame[value_column])
    if len(prepared.index) < MIN_POINTS_FOR_TREND:
        return 1

    packet_count = len(prepared.index)
    if packet_count <= 10:
        credibility_cap = 1
    elif packet_count <= 20:
        credibility_cap = 2
    elif packet_count <= 36:
        credibility_cap = 3
    else:
        credibility_cap = 4
    maximum_degree = min(
        max(int(max_degree), 1),
        MAX_AUTO_POLYNOMIAL_DEGREE,
        max(len(prepared.index) - 2, 1),
        credibility_cap,
    )
    best_degree = 1
    best_score = float("inf")
    best_mae = float("inf")
    improvement_threshold = 0.35

    for degree in range(1, maximum_degree + 1):
        evaluation = _evaluate_polynomial_degree(prepared, degree)
        if evaluation is None:  # pragma: no cover
            continue
        mae, _rmse, _clipped_share, score = evaluation
        if score < (best_score - improvement_threshold) or (
            math.isclose(score, best_score, rel_tol=0.0, abs_tol=0.1) and (degree < best_degree or mae < best_mae)
        ):
            best_degree = degree
            best_mae = mae
            best_score = score

    return best_degree


def build_adaptive_polynomial_curve(
    frame: pd.DataFrame,
    value_column: str,
    date_column: str = "publication_date",
    max_degree: int = MAX_AUTO_POLYNOMIAL_DEGREE,
    target_mae: float = 1.0,
) -> AdaptiveCurveResult | None:
    prepared = _prepare_xy(frame[date_column], frame[value_column])
    if len(prepared.index) < MIN_POINTS_FOR_TREND:
        return None

    degree = select_auto_polynomial_degree(
        frame,
        value_column=value_column,
        date_column=date_column,
        max_degree=max_degree,
    )
    polynomial_curve = build_polynomial_curve(
        frame,
        value_column=value_column,
        date_column=date_column,
        degree=degree,
    )
    if polynomial_curve is None:  # pragma: no cover
        return None
    polynomial_quality = evaluate_curve_fit(
        frame,
        polynomial_curve,
        value_column=value_column,
        date_column=date_column,
    )
    if polynomial_quality is None:  # pragma: no cover
        return None
    if polynomial_quality.mae <= target_mae:
        return AdaptiveCurveResult(
            curve=polynomial_curve,
            order_label=str(degree),
            fit_quality=polynomial_quality,
        )

    interpolated_curve = build_interpolated_curve(
        frame,
        value_column=value_column,
        date_column=date_column,
    )
    if interpolated_curve is None:  # pragma: no cover
        return AdaptiveCurveResult(
            curve=polynomial_curve,
            order_label=str(degree),
            fit_quality=polynomial_quality,
        )
    interpolated_quality = evaluate_curve_fit(
        frame,
        interpolated_curve,
        value_column=value_column,
        date_column=date_column,
    )
    if interpolated_quality is None:  # pragma: no cover
        return AdaptiveCurveResult(
            curve=polynomial_curve,
            order_label=str(degree),
            fit_quality=polynomial_quality,
        )
    return AdaptiveCurveResult(
        curve=interpolated_curve,
        order_label="adaptatif",
        fit_quality=interpolated_quality,
    )
