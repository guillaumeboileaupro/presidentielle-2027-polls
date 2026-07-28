from __future__ import annotations

from dataclasses import dataclass
import math

import numpy as np
import pandas as pd
from statsmodels.nonparametric.smoothers_lowess import lowess


MIN_POINTS_FOR_TREND = 5
MIN_POINTS_FOR_EXTENSION = 2
TARGET_POINTS_FOR_EXTENSION = 5
MAX_AUTO_POLYNOMIAL_DEGREE = 15


@dataclass(frozen=True)
class ExploratoryExtension:
    x: pd.Series
    y: pd.Series
    lower: pd.Series
    upper: pd.Series
    points_used: int
    recent_days: int


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


def _prepare_xy(dates: pd.Series, values: pd.Series) -> pd.DataFrame:
    prepared = pd.DataFrame(
        {
            "date": pd.to_datetime(dates, errors="coerce"),
            "value": pd.to_numeric(values, errors="coerce"),
        }
    ).dropna()
    if prepared.empty:
        return prepared
    prepared = prepared.sort_values("date").drop_duplicates(subset=["date"], keep="last")
    base_date = pd.Timestamp(prepared["date"].iloc[0])
    prepared["date_num"] = (prepared["date"] - base_date) / pd.Timedelta(days=1)
    prepared["date_num"] = prepared["date_num"].astype(float)
    return prepared


def _prepare_binned(prepared: pd.DataFrame, window_days: int = 30) -> pd.DataFrame:
    if prepared.empty:
        return prepared
    working = prepared.copy()
    working["bin_index"] = np.floor(working["date_num"] / max(int(window_days), 1)).astype(int)
    grouped = (
        working.groupby("bin_index", dropna=False)
        .agg(
            date=("date", "max"),
            value=("value", "median"),
            date_num=("date_num", "median"),
            points=("value", "count"),
        )
        .reset_index(drop=True)
        .sort_values("date")
    )
    return grouped


def _build_extension_sample(
    prepared: pd.DataFrame,
    recent_days: int,
    target_points: int = TARGET_POINTS_FOR_EXTENSION,
) -> pd.DataFrame:
    if prepared.empty:
        return prepared

    cutoff = prepared["date"].max() - pd.Timedelta(days=recent_days)
    recent = prepared.loc[prepared["date"] >= cutoff].copy()
    if len(recent.index) < MIN_POINTS_FOR_EXTENSION:
        recent = prepared.tail(target_points).copy()
    else:
        recent = recent.tail(target_points).copy()
    if len(recent.index) < MIN_POINTS_FOR_EXTENSION:
        return recent

    actual_span = float(recent["date_num"].max() - recent["date_num"].min()) if len(recent.index) > 1 else 0.0
    synthetic_span = max(actual_span, float(min(recent_days, 28)))
    synthetic_offsets = np.linspace(0.0, synthetic_span, num=len(recent.index))

    recent = recent.reset_index(drop=True)
    recent["date_num"] = synthetic_offsets
    recent["date"] = recent["date"].max() - pd.to_timedelta(synthetic_span - synthetic_offsets, unit="D")
    return recent


def _linear_projection_from_recent(
    recent_dates: pd.Series,
    recent_values: np.ndarray,
    election_date: pd.Timestamp,
    clip_upper: float | None = 100.0,
) -> tuple[np.ndarray, np.ndarray]:
    last_date = pd.Timestamp(recent_dates.iloc[-1])
    first_date = pd.Timestamp(recent_dates.iloc[0])
    extension_dates = pd.date_range(last_date, pd.Timestamp(election_date), freq="D")

    if len(extension_dates) < 2:
        extension_dates = pd.DatetimeIndex([last_date, pd.Timestamp(election_date)])

    span_days = max(float((last_date - first_date) / pd.Timedelta(days=1)), 1.0)
    anchor_value = float(recent_values[-1])
    raw_slope = float(recent_values[-1] - recent_values[0]) / span_days
    slope_cap = max(float(np.ptp(recent_values)) / span_days, 0.02)
    daily_slope = float(np.clip(raw_slope, -slope_cap, slope_cap))
    total_change_cap = max(2.5, min(8.0, float(np.ptp(recent_values)) * 1.5 + 1.0))

    horizon_days = ((extension_dates - last_date) / pd.Timedelta(days=1)).to_numpy(dtype=float)
    total_horizon = max(float(horizon_days[-1]), 1.0)
    damping = 1.0 - 0.65 * np.clip(horizon_days / total_horizon, 0.0, 1.0)
    projected = anchor_value + np.cumsum(np.r_[0.0, daily_slope * damping[1:]])
    projected = np.clip(projected, anchor_value - total_change_cap, anchor_value + total_change_cap)
    if clip_upper is None:
        projected = np.clip(projected, 0.0, None)
    else:
        projected = np.clip(projected, 0.0, clip_upper)
    return extension_dates.to_numpy(), projected


def _select_polynomial_degree(point_count: int, preferred_degree: int | None = None) -> int:
    if point_count < MIN_POINTS_FOR_TREND:
        return 1
    if preferred_degree is not None:
        return min(max(int(preferred_degree), 1), max(point_count - 1, 1), MAX_AUTO_POLYNOMIAL_DEGREE)
    if point_count >= 22:
        return 9
    if point_count >= 20:
        return 8
    if point_count >= 18:
        return 7
    if point_count >= 16:
        return 6
    if point_count >= 14:
        return 5
    if point_count >= 11:
        return 4
    if point_count >= 8:
        return 3
    return 1


def _fit_polynomial(
    prepared: pd.DataFrame,
    weights: np.ndarray | None = None,
    degree: int | None = None,
    min_points: int = MIN_POINTS_FOR_TREND,
):
    if len(prepared.index) < min_points:
        return None, None
    degree = min(_select_polynomial_degree(len(prepared.index), preferred_degree=degree), max(len(prepared.index) - 1, 1))
    if degree < 1:
        return None, None

    x = prepared["date_num"].to_numpy(dtype=float)
    y = prepared["value"].to_numpy(dtype=float)
    x_center = float(np.mean(x))
    x_scale = float(np.std(x))
    if not np.isfinite(x_scale) or x_scale == 0.0:
        x_scale = 1.0
    x_scaled = (x - x_center) / x_scale

    try:
        coefficients = np.polyfit(x_scaled, y, deg=degree, w=weights)
    except np.linalg.LinAlgError:
        return None, None

    def evaluator(raw_x: np.ndarray | float) -> np.ndarray:
        raw = np.asarray(raw_x, dtype=float)
        return np.polyval(coefficients, (raw - x_center) / x_scale)

    return evaluator, degree


def _recency_weights(prepared: pd.DataFrame) -> np.ndarray:
    if prepared.empty:
        return np.array([], dtype=float)
    latest = prepared["date"].max()
    days_from_latest = (latest - prepared["date"]).dt.days.to_numpy(dtype=float)
    return 1.0 / (1.0 + np.clip(days_from_latest, 0.0, None) / 45.0)


def polynomial_smooth_series(
    dates: pd.Series,
    values: pd.Series,
    degree: int | None = None,
) -> pd.Series:
    ordered_values = pd.to_numeric(values, errors="coerce")
    fitted = pd.Series(index=ordered_values.index, dtype=float)
    prepared = _prepare_xy(dates, values)
    if len(prepared.index) < MIN_POINTS_FOR_TREND:
        return fitted

    polynomial, _ = _fit_polynomial(prepared, weights=_recency_weights(prepared), degree=degree)
    if polynomial is None:
        return fitted

    smoothed = polynomial(prepared["date_num"].to_numpy(dtype=float))
    fitted.loc[prepared.index] = np.clip(smoothed, 0.0, 100.0)
    return fitted


def compute_group_trend(
    frame: pd.DataFrame,
    group_columns: list[str],
    value_column: str,
    date_column: str = "publication_date",
    degree: int | None = None,
) -> pd.Series:
    if frame.empty:
        return pd.Series(index=frame.index, dtype=float)

    result = pd.Series(index=frame.index, dtype=float)
    for _, group in frame.groupby(group_columns, dropna=False, sort=False):
        result.loc[group.index] = polynomial_smooth_series(group[date_column], group[value_column], degree=degree).to_numpy()
    return result


def build_polynomial_curve(
    frame: pd.DataFrame,
    value_column: str,
    date_column: str = "publication_date",
    dense_points: int = 200,
    degree: int | None = None,
) -> pd.DataFrame | None:
    prepared = _prepare_xy(frame[date_column], frame[value_column])
    if len(prepared.index) < MIN_POINTS_FOR_TREND:
        return None

    polynomial, _ = _fit_polynomial(prepared, weights=_recency_weights(prepared), degree=degree)
    if polynomial is None:
        return None

    x_min = float(prepared["date_num"].min())
    x_max = float(prepared["date_num"].max())
    dense_x = np.linspace(x_min, x_max, num=max(dense_points, len(prepared.index)))
    dense_y = np.clip(polynomial(dense_x), 0.0, 100.0)
    return pd.DataFrame(
        {
            "publication_date": prepared["date"].min() + pd.to_timedelta(dense_x, unit="D"),
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
    dense_x = np.linspace(float(x.min()), float(x.max()), num=max(dense_points, len(prepared.index)))
    dense_x = np.unique(np.concatenate([dense_x, x]))
    dense_y = np.interp(dense_x, x, y)
    return pd.DataFrame(
        {
            "publication_date": prepared["date"].min() + pd.to_timedelta(dense_x, unit="D"),
            "score_smooth": np.clip(dense_y, 0.0, 100.0),
        }
    )


def build_stable_polynomial_curve(
    frame: pd.DataFrame,
    value_column: str,
    date_column: str = "publication_date",
    dense_points: int = 200,
    degree: int | None = None,
    window_days: int = 30,
) -> pd.DataFrame | None:
    prepared = _prepare_xy(frame[date_column], frame[value_column])
    if len(prepared.index) < MIN_POINTS_FOR_TREND:
        return None

    support = _prepare_binned(prepared, window_days=window_days)
    if len(support.index) < MIN_POINTS_FOR_TREND:
        support = prepared.copy()
    if len(support.index) < MIN_POINTS_FOR_TREND:
        return None

    bounded_degree = _select_polynomial_degree(
        len(support.index),
        preferred_degree=degree if degree is not None else 3,
    )
    polynomial, _ = _fit_polynomial(
        support,
        weights=_recency_weights(support),
        degree=bounded_degree,
    )
    if polynomial is None:
        return None

    x_min = float(support["date_num"].min())
    x_max = float(support["date_num"].max())
    dense_x = np.linspace(x_min, x_max, num=max(dense_points, len(support.index)))
    dense_y = np.clip(polynomial(dense_x), 0.0, 100.0)
    return pd.DataFrame(
        {
            "publication_date": support["date"].min() + pd.to_timedelta(dense_x, unit="D"),
            "score_smooth": dense_y,
        }
    )


def build_binned_curve(
    frame: pd.DataFrame,
    value_column: str,
    date_column: str = "publication_date",
    window_days: int = 30,
) -> pd.DataFrame | None:
    prepared = _prepare_xy(frame[date_column], frame[value_column])
    if len(prepared.index) < MIN_POINTS_FOR_TREND:
        return None
    binned = _prepare_binned(prepared, window_days=window_days)
    if len(binned.index) < 2:
        return None
    return pd.DataFrame(
        {
            "publication_date": binned["date"].to_numpy(),
            "score_smooth": np.clip(binned["value"].to_numpy(dtype=float), 0.0, 100.0),
            "points_used": binned["points"].to_numpy(dtype=int),
        }
    )


def build_loess_curve(
    frame: pd.DataFrame,
    value_column: str,
    date_column: str = "publication_date",
    frac: float = 0.25,
    dense_points: int = 500,
) -> pd.DataFrame | None:
    prepared = _prepare_xy(frame[date_column], frame[value_column])
    if len(prepared.index) < MIN_POINTS_FOR_TREND:
        return None

    x = prepared["date_num"].to_numpy(dtype=float)
    y = prepared["value"].to_numpy(dtype=float)
    fitted = lowess(
        endog=y,
        exog=x,
        frac=float(np.clip(frac, 0.05, 1.0)),
        it=3,
        return_sorted=True,
    )
    if fitted.size == 0:
        return None

    dense_x = np.linspace(float(x.min()), float(x.max()), num=max(dense_points, len(x)))
    dense_y = np.interp(dense_x, fitted[:, 0], fitted[:, 1])
    return pd.DataFrame(
        {
            "publication_date": prepared["date"].min() + pd.to_timedelta(dense_x, unit="D"),
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

    prepared_curve = _prepare_xy(curve["publication_date"], curve["score_smooth"])
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


def _evaluate_polynomial_degree_on_prepared(
    prepared: pd.DataFrame,
    degree: int,
) -> tuple[float, float, float, float, float] | None:
    minimum_points = max(MIN_POINTS_FOR_TREND, degree + 1)
    if len(prepared.index) < minimum_points + 1:
        return None

    weights = _recency_weights(prepared)
    squared_errors: list[float] = []
    holdout_weights: list[float] = []

    for idx in range(len(prepared.index)):
        train = prepared.drop(prepared.index[idx])
        if len(train.index) < minimum_points:
            return None
        polynomial, _ = _fit_polynomial(
            train,
            weights=_recency_weights(train),
            degree=degree,
            min_points=minimum_points,
        )
        if polynomial is None:
            return None
        x_value = float(prepared.iloc[idx]["date_num"])
        y_true = float(prepared.iloc[idx]["value"])
        y_pred = float(np.clip(polynomial(np.array([x_value], dtype=float))[0], 0.0, 100.0))
        squared_errors.append((y_true - y_pred) ** 2)
        holdout_weights.append(float(weights[idx]))

    rmse = math.sqrt(float(np.average(np.array(squared_errors, dtype=float), weights=np.array(holdout_weights, dtype=float))))

    polynomial_full, _ = _fit_polynomial(
        prepared,
        weights=weights,
        degree=degree,
        min_points=minimum_points,
    )
    if polynomial_full is None:
        return None

    fitted_full = np.clip(polynomial_full(prepared["date_num"].to_numpy(dtype=float)), 0.0, 100.0)
    in_sample_errors = prepared["value"].to_numpy(dtype=float) - fitted_full
    in_sample_rmse = float(np.sqrt(np.mean(np.square(in_sample_errors))))
    in_sample_mae = float(np.mean(np.abs(in_sample_errors)))

    dense_x = np.linspace(
        float(prepared["date_num"].min()),
        float(prepared["date_num"].max()),
        num=max(400, len(prepared.index) * 20),
    )
    dense_y = polynomial_full(dense_x)
    second_diff = np.diff(dense_y, n=2)
    value_range = max(float(prepared["value"].max() - prepared["value"].min()), 1.0)
    roughness = float(np.mean(np.abs(second_diff))) / value_range
    complexity_penalty = 0.015 * float(degree) + 0.004 * roughness + 0.008 * max(float(degree - 6), 0.0) ** 2
    score = (0.55 * rmse) + (0.30 * in_sample_rmse) + (0.15 * in_sample_mae) + complexity_penalty
    return rmse, roughness, score, in_sample_rmse, in_sample_mae


def select_auto_polynomial_degree(
    frame: pd.DataFrame,
    value_column: str,
    date_column: str = "publication_date",
    max_degree: int = MAX_AUTO_POLYNOMIAL_DEGREE,
) -> int:
    prepared = _prepare_xy(frame[date_column], frame[value_column])
    maximum_degree = min(max(int(max_degree), 1), MAX_AUTO_POLYNOMIAL_DEGREE, max(len(prepared.index) - 2, 1))
    candidate_degrees = range(1, maximum_degree + 1)
    best_degree = 1
    best_score = float("inf")
    best_in_sample_mae = float("inf")
    best_rmse = float("inf")

    for degree in candidate_degrees:
        evaluation = _evaluate_polynomial_degree_on_prepared(prepared, degree)
        if evaluation is None:
            continue
        rmse, _roughness, score, _in_sample_rmse, in_sample_mae = evaluation
        if (
            in_sample_mae < best_in_sample_mae
            or (
                math.isclose(in_sample_mae, best_in_sample_mae, rel_tol=0.0, abs_tol=1e-9)
                and (rmse < best_rmse or (math.isclose(rmse, best_rmse, rel_tol=0.0, abs_tol=1e-9) and score < best_score))
            )
        ):
            best_in_sample_mae = in_sample_mae
            best_rmse = rmse
            best_score = score
            best_degree = degree

    return best_degree


def build_polynomial_degree_diagnostics(
    frame: pd.DataFrame,
    group_column: str,
    value_column: str,
    date_column: str = "publication_date",
    max_degree: int = MAX_AUTO_POLYNOMIAL_DEGREE,
) -> pd.DataFrame:
    diagnostics_rows: list[dict[str, object]] = []
    group_values = frame[group_column].drop_duplicates().tolist()
    for group_value in group_values:
        if pd.isna(group_value):
            group = frame.loc[frame[group_column].isna()].copy()
        else:
            group = frame.loc[frame[group_column] == group_value].copy()
        prepared = _prepare_xy(group[date_column], group[value_column])
        maximum_degree = min(max(int(max_degree), 1), MAX_AUTO_POLYNOMIAL_DEGREE, max(len(prepared.index) - 2, 1))
        for degree in range(1, maximum_degree + 1):
            evaluation = _evaluate_polynomial_degree_on_prepared(prepared, degree)
            if evaluation is None:
                continue
            rmse, roughness, score, in_sample_rmse, in_sample_mae = evaluation
            diagnostics_rows.append(
                {
                    group_column: group_value,
                    "degree": degree,
                    "rmse": rmse,
                    "in_sample_rmse": in_sample_rmse,
                    "in_sample_mae": in_sample_mae,
                    "roughness": roughness,
                    "penalized_score": score,
                    "points": int(len(prepared.index)),
                }
            )
    return pd.DataFrame(diagnostics_rows)


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

    maximum_degree = min(max(int(max_degree), 1), MAX_AUTO_POLYNOMIAL_DEGREE, max(len(prepared.index) - 2, 1))
    best_curve: pd.DataFrame | None = None
    best_quality: TrendFitQuality | None = None
    best_degree = 1

    for degree in range(1, maximum_degree + 1):
        curve = build_polynomial_curve(
            frame=frame,
            value_column=value_column,
            date_column=date_column,
            degree=degree,
        )
        if curve is None:
            continue
        quality = evaluate_curve_fit(frame, curve, value_column=value_column, date_column=date_column)
        if quality is None:
            continue
        if best_quality is None or quality.mae < best_quality.mae or (
            math.isclose(quality.mae, best_quality.mae, rel_tol=0.0, abs_tol=1e-9)
            and quality.rmse < best_quality.rmse
        ):
            best_curve = curve
            best_quality = quality
            best_degree = degree

    if best_curve is None or best_quality is None:
        return None

    if best_quality.mae <= target_mae:
        return AdaptiveCurveResult(
            curve=best_curve,
            order_label=str(best_degree),
            fit_quality=best_quality,
        )

    interpolated_curve = build_interpolated_curve(
        frame=frame,
        value_column=value_column,
        date_column=date_column,
    )
    if interpolated_curve is None:
        return AdaptiveCurveResult(
            curve=best_curve,
            order_label=str(best_degree),
            fit_quality=best_quality,
        )

    interpolated_quality = evaluate_curve_fit(
        frame,
        interpolated_curve,
        value_column=value_column,
        date_column=date_column,
    )
    if interpolated_quality is None:
        return AdaptiveCurveResult(
            curve=best_curve,
            order_label=str(best_degree),
            fit_quality=best_quality,
        )

    return AdaptiveCurveResult(
        curve=interpolated_curve,
        order_label="adaptatif",
        fit_quality=interpolated_quality,
    )


def polynomial_extension(
    frame: pd.DataFrame,
    election_date: pd.Timestamp,
    value_column: str,
    date_column: str = "publication_date",
    recent_days: int = 31,
    degree: int | None = None,
    clip_upper: float | None = 100.0,
) -> ExploratoryExtension | None:
    prepared = _prepare_xy(frame[date_column], frame[value_column])
    if len(prepared.index) < MIN_POINTS_FOR_EXTENSION:
        return None

    recent = _build_extension_sample(prepared, recent_days=recent_days)
    if len(recent.index) < MIN_POINTS_FOR_EXTENSION:
        return None

    polynomial, _ = _fit_polynomial(
        recent,
        weights=_recency_weights(recent),
        degree=degree,
        min_points=MIN_POINTS_FOR_EXTENSION,
    )
    if polynomial is None:
        return None

    if pd.Timestamp(election_date) <= pd.Timestamp(recent["date"].max()):
        return None

    if clip_upper is None:
        fitted_recent = np.clip(polynomial(recent["date_num"].to_numpy(dtype=float)), 0.0, None)
    else:
        fitted_recent = np.clip(polynomial(recent["date_num"].to_numpy(dtype=float)), 0.0, clip_upper)
    extension_dates, extension_y = _linear_projection_from_recent(recent["date"], fitted_recent, election_date, clip_upper=clip_upper)
    residuals = recent["value"].to_numpy(dtype=float) - fitted_recent
    sigma = float(np.nanstd(residuals)) if len(residuals) > 1 else 1.0
    growth = np.linspace(1.0, 1.7, num=len(extension_dates))
    uncertainty = np.clip(sigma * growth, 0.8, 12.0)
    return ExploratoryExtension(
        x=pd.Series(extension_dates),
        y=pd.Series(extension_y),
        lower=pd.Series(np.clip(extension_y - uncertainty, 0.0, None)),
        upper=pd.Series(np.clip(extension_y + uncertainty, 0.0, clip_upper) if clip_upper is not None else np.clip(extension_y + uncertainty, 0.0, None)),
        points_used=int(len(recent.index)),
        recent_days=recent_days,
    )


def binned_extension(
    frame: pd.DataFrame,
    election_date: pd.Timestamp,
    value_column: str,
    date_column: str = "publication_date",
    recent_days: int = 31,
    degree: int | None = None,
    window_days: int = 30,
    clip_upper: float | None = 100.0,
) -> ExploratoryExtension | None:
    prepared = _prepare_xy(frame[date_column], frame[value_column])
    if len(prepared.index) < MIN_POINTS_FOR_EXTENSION:
        return None

    recent = _build_extension_sample(prepared, recent_days=recent_days)
    if len(recent.index) < MIN_POINTS_FOR_EXTENSION:
        return None

    recent_binned = _prepare_binned(recent, window_days=window_days)
    if len(recent_binned.index) < 2:
        recent_binned = _prepare_binned(recent, window_days=max(7, window_days // 2))
    if len(recent_binned.index) < 2:
        recent_binned = recent.copy()

    polynomial, _ = _fit_polynomial(
        recent_binned,
        degree=degree,
        min_points=MIN_POINTS_FOR_EXTENSION,
    )
    if polynomial is None:
        return None

    if pd.Timestamp(election_date) <= pd.Timestamp(recent_binned["date"].max()):
        return None

    if clip_upper is None:
        fitted_recent = np.clip(polynomial(recent_binned["date_num"].to_numpy(dtype=float)), 0.0, None)
    else:
        fitted_recent = np.clip(polynomial(recent_binned["date_num"].to_numpy(dtype=float)), 0.0, clip_upper)
    extension_dates, extension_y = _linear_projection_from_recent(recent_binned["date"], fitted_recent, election_date, clip_upper=clip_upper)
    residuals = recent_binned["value"].to_numpy(dtype=float) - fitted_recent
    sigma = float(np.nanstd(residuals)) if len(residuals) > 1 else 1.0
    growth = np.linspace(1.0, 1.7, num=len(extension_dates))
    uncertainty = np.clip(sigma * growth, 0.8, 12.0)
    return ExploratoryExtension(
        x=pd.Series(extension_dates),
        y=pd.Series(extension_y),
        lower=pd.Series(np.clip(extension_y - uncertainty, 0.0, None)),
        upper=pd.Series(np.clip(extension_y + uncertainty, 0.0, clip_upper) if clip_upper is not None else np.clip(extension_y + uncertainty, 0.0, None)),
        points_used=int(len(recent_binned.index)),
        recent_days=recent_days,
    )


def smooth_candidate_trends(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return frame.copy()

    working = frame.copy()
    working["publication_date"] = pd.to_datetime(working["publication_date"], errors="coerce")
    working = working.sort_values(["candidate_name", "scenario_name", "publication_date"])
    working["trend_estimate"] = compute_group_trend(
        working,
        ["candidate_name", "scenario_name"],
        "estimate_percent",
    )
    working["smoothed_estimate"] = working["trend_estimate"]
    return working


def build_lowess_curve(
    frame: pd.DataFrame,
    value_column: str,
    date_column: str = "publication_date",
    frac: float = 0.30,
    degree: int | None = None,
    method: str = "polynomial",
) -> pd.DataFrame | None:
    if method == "loess":
        return build_loess_curve(
            frame=frame,
            value_column=value_column,
            date_column=date_column,
            frac=frac,
        )
    if method == "bins":
        return build_binned_curve(frame=frame, value_column=value_column, date_column=date_column)
    return build_polynomial_curve(frame=frame, value_column=value_column, date_column=date_column, degree=degree)


def exploratory_extension(
    frame: pd.DataFrame,
    election_date: pd.Timestamp,
    value_column: str,
    date_column: str = "publication_date",
    recent_days: int = 31,
    frac: float = 0.45,
    degree: int | None = None,
    method: str = "polynomial",
    clip_upper: float | None = 100.0,
) -> ExploratoryExtension | None:
    del frac
    if method == "bins":
        return binned_extension(
            frame=frame,
            election_date=election_date,
            value_column=value_column,
            date_column=date_column,
            recent_days=recent_days,
            degree=degree,
            clip_upper=clip_upper,
        )
    return polynomial_extension(
        frame=frame,
        election_date=election_date,
        value_column=value_column,
        date_column=date_column,
        recent_days=recent_days,
        degree=degree,
        clip_upper=clip_upper,
    )
