from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from presidentielle2027.analytics.trends import build_loess_curve
from presidentielle2027.analytics.adjustment_core import (
    _evaluate_polynomial_degree,
    _prepare_xy,
    build_adaptive_polynomial_curve,
    build_interpolated_curve,
    build_polynomial_curve,
    evaluate_curve_fit,
    select_auto_polynomial_degree,
)


def test_build_loess_curve_returns_a_dense_smooth_local_regression() -> None:
    frame = pd.DataFrame(
        {
            "publication_date": pd.date_range("2024-01-01", periods=20, freq="30D"),
            "estimate_percent": [
                12.0,
                12.3,
                12.6,
                12.9,
                13.2,
                13.5,
                13.8,
                14.1,
                30.0,
                14.7,
                15.0,
                15.3,
                15.6,
                15.9,
                16.2,
                16.5,
                16.8,
                17.1,
                17.4,
                17.7,
            ],
        }
    )

    curve = build_loess_curve(frame, "estimate_percent", frac=0.50)

    assert curve is not None
    assert len(curve) == 500
    assert curve["score_smooth"].notna().all()
    assert curve["publication_date"].is_monotonic_increasing
    assert curve["score_smooth"].max() < 25.0


def test_evaluate_curve_fit_returns_zero_for_exact_curve() -> None:
    frame = pd.DataFrame(
        {
            "publication_date": pd.to_datetime(["2026-01-01", "2026-01-10", "2026-01-20"]),
            "estimate_percent": [10.0, 12.0, 14.0],
        }
    )
    curve = pd.DataFrame(
        {
            "publication_date": pd.to_datetime(["2026-01-01", "2026-01-10", "2026-01-20"]),
            "score_smooth": [10.0, 12.0, 14.0],
        }
    )

    quality = evaluate_curve_fit(frame, curve, "estimate_percent")

    assert quality is not None
    assert quality.mae == 0.0
    assert quality.rmse == 0.0
    assert quality.max_abs_error == 0.0
    assert quality.point_count == 3


def test_build_polynomial_curve_follows_non_constant_series() -> None:
    frame = pd.DataFrame(
        {
            "publication_date": pd.to_datetime(
                [
                    "2026-01-01",
                    "2026-01-10",
                    "2026-01-20",
                    "2026-02-01",
                    "2026-02-10",
                    "2026-02-20",
                    "2026-03-01",
                ]
            ),
            "estimate_percent": [4.0, 5.5, 7.0, 8.5, 10.5, 13.0, 16.0],
        }
    )

    curve = build_polynomial_curve(
        frame=frame,
        value_column="estimate_percent",
        degree=3,
    )

    assert curve is not None
    score_values = curve["score_smooth"].tolist()
    assert max(score_values) - min(score_values) > 5.0


def test_build_interpolated_curve_matches_observed_points() -> None:
    frame = pd.DataFrame(
        {
            "publication_date": pd.to_datetime(["2026-01-01", "2026-01-08", "2026-01-20", "2026-02-01"]),
            "estimate_percent": [4.0, 7.0, 6.0, 10.0],
        }
    )

    curve = build_interpolated_curve(frame, "estimate_percent")
    quality = evaluate_curve_fit(frame, curve if curve is not None else pd.DataFrame(), "estimate_percent")

    assert curve is not None
    assert quality is not None
    assert quality.mae == 0.0


def test_build_polynomial_curve_returns_none_when_too_few_points() -> None:
    frame = pd.DataFrame(
        {
            "publication_date": pd.to_datetime(["2026-01-01", "2026-01-08", "2026-01-20"]),
            "estimate_percent": [4.0, 7.0, 6.0],
        }
    )

    curve = build_polynomial_curve(frame, "estimate_percent", degree=3)

    assert curve is None


def test_build_interpolated_curve_returns_none_when_too_few_points() -> None:
    frame = pd.DataFrame(
        {
            "publication_date": pd.to_datetime(["2026-01-01"]),
            "estimate_percent": [4.0],
        }
    )

    curve = build_interpolated_curve(frame, "estimate_percent")

    assert curve is None


def test_evaluate_curve_fit_returns_none_for_empty_inputs_and_single_point_curve() -> None:
    empty_frame = pd.DataFrame(
        {
            "publication_date": pd.Series(dtype="datetime64[ns]"),
            "estimate_percent": pd.Series(dtype="float64"),
        }
    )
    frame = pd.DataFrame(
        {
            "publication_date": pd.to_datetime(["2026-01-01", "2026-01-10", "2026-01-20"]),
            "estimate_percent": [10.0, 12.0, 14.0],
        }
    )
    single_point_curve = pd.DataFrame(
        {
            "publication_date": pd.to_datetime(["2026-01-01"]),
            "score_smooth": [10.0],
        }
    )

    assert evaluate_curve_fit(empty_frame, pd.DataFrame(), "estimate_percent") is None
    assert evaluate_curve_fit(frame, single_point_curve, "estimate_percent") is None


def test_build_adaptive_polynomial_curve_returns_credible_or_adaptive_curve() -> None:
    frame = pd.DataFrame(
        {
            "publication_date": pd.date_range("2026-01-01", periods=9, freq="7D"),
            "estimate_percent": [5.0, 5.5, 6.2, 7.6, 8.1, 9.9, 11.2, 12.8, 14.1],
        }
    )

    result = build_adaptive_polynomial_curve(frame, "estimate_percent", max_degree=10, target_mae=1.0)

    assert result is not None
    assert result.fit_quality.mae <= 1.0
    assert result.order_label != ""


def test_select_auto_polynomial_degree_uses_higher_degree_for_curved_series() -> None:
    dates = pd.date_range("2026-01-01", periods=14, freq="7D")
    x_values = np.linspace(-1.0, 1.0, num=len(dates))
    frame = pd.DataFrame(
        {
            "publication_date": dates,
            "estimate_percent": 12.0 + (4.0 * x_values) + (9.0 * np.square(x_values)),
        }
    )

    degree = select_auto_polynomial_degree(frame, "estimate_percent", max_degree=12)

    assert degree >= 2


def test_select_auto_polynomial_degree_returns_one_for_short_series() -> None:
    frame = pd.DataFrame(
        {
            "publication_date": pd.to_datetime(["2026-01-01", "2026-01-08", "2026-01-20"]),
            "estimate_percent": [10.0, 10.5, 11.0],
        }
    )

    degree = select_auto_polynomial_degree(frame, "estimate_percent", max_degree=12)

    assert degree == 1


def test_build_adaptive_polynomial_curve_falls_back_to_adaptative_label_when_needed() -> None:
    frame = pd.DataFrame(
        {
            "publication_date": pd.to_datetime(
                ["2026-01-01", "2026-01-06", "2026-01-15", "2026-01-21", "2026-02-05", "2026-02-18"]
            ),
            "estimate_percent": [10.0, 14.0, 5.0, 15.0, 6.0, 16.0],
        }
    )

    result = build_adaptive_polynomial_curve(
        frame,
        value_column="estimate_percent",
        max_degree=8,
        target_mae=0.01,
    )

    assert result is not None
    assert result.order_label == "adaptatif"
    assert result.fit_quality.mae == 0.0


def test_build_adaptive_polynomial_curve_returns_none_for_short_series() -> None:
    frame = pd.DataFrame(
        {
            "publication_date": pd.to_datetime(["2026-01-01", "2026-01-08", "2026-01-20"]),
            "estimate_percent": [10.0, 14.0, 5.0],
        }
    )

    result = build_adaptive_polynomial_curve(frame, value_column="estimate_percent", max_degree=8, target_mae=0.01)

    assert result is None


def test_prepare_xy_collapses_same_day_packets_by_mean() -> None:
    prepared = _prepare_xy(
        pd.Series(pd.to_datetime(["2026-01-01", "2026-01-01", "2026-01-10"])),
        pd.Series([10.0, 14.0, 20.0]),
    )

    assert len(prepared.index) == 2
    assert prepared["value"].tolist() == [12.0, 20.0]


def test_prepare_xy_collapses_close_dates_into_same_packet() -> None:
    prepared = _prepare_xy(
        pd.Series(pd.to_datetime(["2026-01-01", "2026-01-03", "2026-01-04", "2026-01-20"])),
        pd.Series([10.0, 14.0, 12.0, 20.0]),
    )

    assert len(prepared.index) == 2
    assert prepared["value"].tolist() == [12.0, 20.0]


def test_evaluate_polynomial_degree_returns_none_when_not_enough_points_for_degree() -> None:
    prepared = _prepare_xy(
        pd.Series(pd.to_datetime(["2026-01-01", "2026-01-08", "2026-01-15", "2026-01-22", "2026-01-29"])),
        pd.Series([10.0, 11.0, 12.0, 13.0, 14.0]),
    )

    assert _evaluate_polynomial_degree(prepared, degree=4) is None


def test_evaluate_polynomial_degree_returns_none_when_train_fit_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    prepared = _prepare_xy(
        pd.Series(pd.date_range("2026-01-01", periods=6, freq="7D")),
        pd.Series([10.0, 11.0, 12.5, 11.5, 13.0, 14.0]),
    )
    original_fit = __import__("presidentielle2027.analytics.adjustment_core", fromlist=["_fit_polynomial"])._fit_polynomial
    state = {"calls": 0}

    def fake_fit(frame: pd.DataFrame, degree: int) -> tuple[np.ndarray, float, float] | None:
        state["calls"] += 1
        if state["calls"] == 1:
            return None
        return original_fit(frame, degree)

    monkeypatch.setattr("presidentielle2027.analytics.adjustment_core._fit_polynomial", fake_fit)

    assert _evaluate_polynomial_degree(prepared, degree=1) is None


def test_evaluate_polynomial_degree_returns_none_when_final_fit_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    prepared = _prepare_xy(
        pd.Series(pd.date_range("2026-01-01", periods=6, freq="7D")),
        pd.Series([10.0, 11.0, 12.5, 11.5, 13.0, 14.0]),
    )
    original_fit = __import__("presidentielle2027.analytics.adjustment_core", fromlist=["_fit_polynomial"])._fit_polynomial
    state = {"calls": 0}

    def fake_fit(frame: pd.DataFrame, degree: int) -> tuple[np.ndarray, float, float] | None:
        state["calls"] += 1
        if state["calls"] == len(prepared.index) + 1:
            return None
        return original_fit(frame, degree)

    monkeypatch.setattr("presidentielle2027.analytics.adjustment_core._fit_polynomial", fake_fit)

    assert _evaluate_polynomial_degree(prepared, degree=1) is None


def test_evaluate_polynomial_degree_handles_multiple_inflections() -> None:
    prepared = _prepare_xy(
        pd.Series(pd.date_range("2026-01-01", periods=10, freq="7D")),
        pd.Series([10.0, 14.0, 7.0, 16.0, 6.0, 15.0, 8.0, 17.0, 7.5, 16.5]),
    )

    evaluation = _evaluate_polynomial_degree(prepared, degree=2)

    assert evaluation is not None
    assert evaluation[3] > 0.0


def test_select_auto_polynomial_degree_caps_to_four_for_medium_packet_count() -> None:
    frame = pd.DataFrame(
        {
            "publication_date": pd.date_range("2026-01-01", periods=20, freq="7D"),
            "estimate_percent": np.linspace(10.0, 18.0, 20),
        }
    )

    degree = select_auto_polynomial_degree(frame, "estimate_percent", max_degree=8)

    assert degree <= 2


def test_select_auto_polynomial_degree_caps_to_five_for_large_packet_count() -> None:
    frame = pd.DataFrame(
        {
            "publication_date": pd.date_range("2026-01-01", periods=32, freq="7D"),
            "estimate_percent": np.linspace(10.0, 22.0, 32),
        }
    )

    degree = select_auto_polynomial_degree(frame, "estimate_percent", max_degree=8)

    assert degree <= 3
