from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


MIN_POINTS_FOR_TREND = 5
MIN_POINTS_FOR_EXTENSION = 2
TARGET_POINTS_FOR_EXTENSION = 5


@dataclass(frozen=True)
class ExploratoryExtension:
    x: pd.Series
    y: pd.Series
    lower: pd.Series
    upper: pd.Series
    points_used: int
    recent_days: int


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
    prepared["date_num"] = (prepared["date"] - prepared["date"].min()).dt.days.astype(float)
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
        return min(max(int(preferred_degree), 1), max(point_count - 1, 1), 6)
    if point_count >= 18:
        return 6
    if point_count >= 15:
        return 5
    if point_count >= 12:
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
    del frac
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
