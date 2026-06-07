import pandas as pd
import pytest
from pathlib import Path

from presidentielle2027.adjustments.house_effects import apply_house_effect_adjustment, estimate_house_effects
from presidentielle2027.analytics.dynamic_poll_bias import apply_dynamic_poll_bias_correction
from presidentielle2027.adjustments.recency_weighting import compute_recency_weights
from presidentielle2027.adjustments.sample_size_weighting import compute_sample_size_weights
from presidentielle2027.analytics.trends import exploratory_extension
from presidentielle2027.analytics.historical_corrections import (
    apply_first_round_historical_correction,
    apply_second_round_legislative_correction,
    compute_second_round_legislative_benchmark,
    compute_legislative_2024_poll_bias,
    get_second_round_transfer_map,
    load_legislative_2024_results,
)


def test_weighting_functions() -> None:
    recency = compute_recency_weights(pd.Series(["2026-01-01", "2026-01-10"]), reference_date=pd.Timestamp("2026-01-11").date())
    sample = compute_sample_size_weights(pd.Series([1000, 1600]))
    assert recency.iloc[1] > recency.iloc[0]
    assert sample.iloc[1] > sample.iloc[0]


def test_house_effect_adjustment() -> None:
    frame = pd.DataFrame(
        [
            {"polling_company": "A", "scenario_name": "S1", "candidate_name": "X", "round": "first_round", "publication_date": "2026-01-01", "estimate_percent": 22.0},
            {"polling_company": "B", "scenario_name": "S1", "candidate_name": "X", "round": "first_round", "publication_date": "2026-01-05", "estimate_percent": 20.0},
            {"polling_company": "C", "scenario_name": "S1", "candidate_name": "X", "round": "first_round", "publication_date": "2026-01-06", "estimate_percent": 21.0},
        ]
    )
    effects = estimate_house_effects(frame)
    adjusted = apply_house_effect_adjustment(frame, effects)
    assert "adjusted_estimate_house_effect" in adjusted.columns


def test_first_round_historical_correction_exposes_components() -> None:
    frame = pd.DataFrame(
        [
            {
                "polling_company": "Ifop",
                "publication_date": "2026-05-21",
                "candidate_party": "LFI",
                "political_family": "left",
                "estimate_percent": 16.0,
                "collection_method": "online",
                "quota_method": "unknown",
                "sample_size": 1000,
            }
        ]
    )
    corrected, _ = apply_first_round_historical_correction(
        frame,
        Path("data/reference"),
    )
    assert "structural_bias_component" in corrected.columns
    assert "temporal_bias_component" in corrected.columns
    assert "trajectory_bias_component" in corrected.columns
    assert "legislative_2024_bias_component" in corrected.columns
    assert "representativity_bias_component" in corrected.columns
    total = (
        corrected.loc[0, "structural_bias_component"]
        + corrected.loc[0, "temporal_bias_component"]
        + corrected.loc[0, "trajectory_bias_component"]
        + corrected.loc[0, "legislative_2024_bias_component"]
    )
    assert corrected.loc[0, "historical_correction"] == total
    assert corrected.loc[0, "historically_corrected_estimate"] > corrected.loc[0, "estimate_percent"]
    assert corrected.loc[0, "status"] in {"calculé", "à vérifier", "données insuffisantes"}
    assert corrected.loc[0, "historical_2022_weight"] == pytest.approx(0.4)
    assert corrected.loc[0, "legislative_2024_weight"] == pytest.approx(1.0)


def test_first_round_historical_correction_neutralizes_manual_override_for_rn() -> None:
    frame = pd.DataFrame(
        [
            {
                "polling_company": "Ifop",
                "publication_date": "2026-05-21",
                "candidate_party": "RN",
                "political_family": "far_right",
                "estimate_percent": 34.0,
                "collection_method": "online",
                "quota_method": "unknown",
                "sample_size": 1000,
            }
        ]
    )
    corrected, _ = apply_first_round_historical_correction(frame, Path("data/reference"))
    assert corrected.loc[0, "structural_bias_component"] == pytest.approx(0.0)
    assert corrected.loc[0, "temporal_bias_component"] == pytest.approx(0.0)
    assert corrected.loc[0, "trajectory_bias_component"] == pytest.approx(0.0)
    assert corrected.loc[0, "legislative_2024_bias_component"] == pytest.approx(-5.24, abs=1e-5)
    assert corrected.loc[0, "historical_correction"] == pytest.approx(-5.24, abs=1e-5)
    assert corrected.loc[0, "historically_corrected_estimate"] == pytest.approx(28.76, abs=1e-5)
    assert corrected.loc[0, "historical_2022_weight"] == pytest.approx(0.4)
    assert corrected.loc[0, "legislative_2024_weight"] == pytest.approx(1.0)


def test_second_round_legislative_benchmark_uses_2024_bloc_labels() -> None:
    legislative = load_legislative_2024_results(Path("data/reference"))
    left, far_right = compute_second_round_legislative_benchmark("gauche", "extrême_droite", legislative)
    assert round(left + far_right, 5) == 100.0
    assert left > far_right
    assert left > 54.0


def test_second_round_transfer_map_strengthens_centre_to_left_against_far_right() -> None:
    transfer_map = get_second_round_transfer_map("centre", "gauche", "extrême_droite")
    assert transfer_map["gauche"] == pytest.approx(0.82)
    assert transfer_map["extrême_droite"] == pytest.approx(0.03)


def test_compute_legislative_2024_poll_bias_uses_national_wiki_table() -> None:
    bias = compute_legislative_2024_poll_bias(Path("data/reference"))
    assert not bias.empty
    rn_row = bias.loc[bias["bloc_label"] == "extrême_droite"].iloc[0]
    assert rn_row["n_points"] >= 10
    assert pd.notna(rn_row["poll_bias_2024"])


def test_second_round_legislative_correction_penalizes_far_right_with_manual_seat_override() -> None:
    frame = pd.DataFrame(
        [
            {
                "scenario_name": "Test duel",
                "candidate_name": "Jordan Bardella",
                "candidate_party": "RN",
                "political_family": "far_right",
                "estimate_percent": 50.0,
                "publication_date": "2026-05-21",
            },
            {
                "scenario_name": "Test duel",
                "candidate_name": "Raphaël Glucksmann",
                "candidate_party": "PS-PP",
                "political_family": "centre_left",
                "estimate_percent": 50.0,
                "publication_date": "2026-05-21",
            },
        ]
    )
    corrected = apply_second_round_legislative_correction(frame, Path("data/reference"))
    rn_row = corrected.loc[corrected["candidate_party"] == "RN"].iloc[0]
    assert rn_row["legislatively_corrected_estimate"] < rn_row["estimate_percent"]


def test_exploratory_extension_falls_back_to_last_five_polls_when_recent_window_is_sparse() -> None:
    frame = pd.DataFrame(
        [
            {"publication_date": "2026-01-01", "estimate_percent": 10.0},
            {"publication_date": "2026-01-20", "estimate_percent": 10.5},
            {"publication_date": "2026-02-10", "estimate_percent": 11.0},
            {"publication_date": "2026-03-05", "estimate_percent": 11.8},
            {"publication_date": "2026-04-25", "estimate_percent": 12.4},
        ]
    )

    extension = exploratory_extension(
        frame,
        election_date=pd.Timestamp("2027-04-11"),
        value_column="estimate_percent",
        recent_days=31,
        degree=4,
        method="polynomial",
    )

    assert extension is not None
    assert extension.points_used == 5
    assert len(extension.x) >= 2
    assert extension.x.iloc[0] == pd.Timestamp("2026-04-25")
    assert extension.x.iloc[-1] == pd.Timestamp("2027-04-11")


def test_exploratory_extension_supports_short_series_for_prolongation() -> None:
    frame = pd.DataFrame(
        [
            {"publication_date": "2026-04-10", "estimate_percent": 8.0},
            {"publication_date": "2026-05-20", "estimate_percent": 9.5},
            {"publication_date": "2026-06-30", "estimate_percent": 11.0},
        ]
    )

    extension = exploratory_extension(
        frame,
        election_date=pd.Timestamp("2027-04-11"),
        value_column="estimate_percent",
        recent_days=31,
        degree=4,
        method="polynomial",
    )

    assert extension is not None
    assert extension.points_used == 3
    assert extension.x.iloc[-1] == pd.Timestamp("2027-04-11")


def test_exploratory_extension_does_not_blow_up_on_recent_upward_series() -> None:
    frame = pd.DataFrame(
        [
            {"publication_date": "2026-04-01", "estimate_percent": 12.0},
            {"publication_date": "2026-04-20", "estimate_percent": 12.1},
            {"publication_date": "2026-05-10", "estimate_percent": 12.3},
            {"publication_date": "2026-06-05", "estimate_percent": 12.4},
            {"publication_date": "2026-07-22", "estimate_percent": 12.6},
        ]
    )

    extension = exploratory_extension(
        frame,
        election_date=pd.Timestamp("2027-04-11"),
        value_column="estimate_percent",
        recent_days=31,
        degree=4,
        method="polynomial",
    )

    assert extension is not None
    assert extension.y.iloc[0] <= 13.0
    assert extension.y.iloc[-1] <= 20.0


def test_exploratory_extension_can_disable_upper_cap_for_projection_scenarios() -> None:
    frame = pd.DataFrame(
        [
            {"publication_date": "2026-04-01", "estimate_percent": 96.0},
            {"publication_date": "2026-04-20", "estimate_percent": 97.0},
            {"publication_date": "2026-05-10", "estimate_percent": 98.0},
            {"publication_date": "2026-06-05", "estimate_percent": 99.0},
            {"publication_date": "2026-07-22", "estimate_percent": 100.0},
        ]
    )

    capped = exploratory_extension(
        frame,
        election_date=pd.Timestamp("2027-04-11"),
        value_column="estimate_percent",
        recent_days=31,
        degree=4,
        method="polynomial",
    )
    uncapped = exploratory_extension(
        frame,
        election_date=pd.Timestamp("2027-04-11"),
        value_column="estimate_percent",
        recent_days=31,
        degree=4,
        method="polynomial",
        clip_upper=None,
    )

    assert capped is not None
    assert uncapped is not None
    assert capped.y.max() <= 100.0
    assert uncapped.upper.max() > 100.0


def test_dynamic_poll_bias_correction_targets_all_rows_with_model_fallbacks() -> None:
    frame = pd.DataFrame(
        [
            {
                "poll_id": "ifop-1",
                "polling_company": "Ifop",
                "round": "first_round",
                "candidate_name": "Jean-Luc Mélenchon",
                "candidate_party": "LFI",
                "estimate_percent": 12.0,
                "publication_date": "2026-05-29",
                "political_family": "left",
            },
            {
                "poll_id": "ifop-1",
                "polling_company": "Ifop",
                "round": "first_round",
                "candidate_name": "Jordan Bardella",
                "candidate_party": "RN",
                "estimate_percent": 36.0,
                "publication_date": "2026-05-29",
                "political_family": "far_right",
            },
            {
                "poll_id": "elabe-1",
                "polling_company": "Elabe",
                "round": "first_round",
                "candidate_name": "Jean-Luc Mélenchon",
                "candidate_party": "LFI",
                "estimate_percent": 12.0,
                "publication_date": "2026-05-29",
                "political_family": "left",
            },
        ]
    )

    corrected, context = apply_dynamic_poll_bias_correction(frame, Path("data/reference"))

    lfi_row = corrected.loc[corrected["candidate_party"] == "LFI"].iloc[0]
    rn_row = corrected.loc[corrected["candidate_party"] == "RN"].iloc[0]
    non_ifop_row = corrected.loc[corrected["polling_company"] == "Elabe"].iloc[0]

    assert not context.segment_models.empty
    assert lfi_row["dynamic_model_source"] in {"pollster_force", "force_only", "pollster_only", "global", "manual_override"}
    assert rn_row["dynamic_model_source"] in {"pollster_force", "force_only", "pollster_only", "global", "manual_override"}
    assert non_ifop_row["dynamic_model_source"] in {"pollster_force", "force_only", "pollster_only", "global", "manual_override"}
    assert lfi_row["dynamically_corrected_estimate"] != pytest.approx(12.0)
    assert rn_row["dynamically_corrected_estimate"] == pytest.approx(36.0)
    assert bool(non_ifop_row["dynamic_correction_applied"]) is True


def test_dynamic_poll_bias_correction_applies_manual_override_for_rn() -> None:
    frame = pd.DataFrame(
        [
            {
                "poll_id": "ifop-rn",
                "polling_company": "Ifop",
                "round": "first_round",
                "candidate_name": "Jordan Bardella",
                "candidate_party": "RN",
                "estimate_percent": 36.0,
                "publication_date": "2026-05-29",
                "political_family": "far_right",
            }
        ]
    )

    corrected, _ = apply_dynamic_poll_bias_correction(frame, Path("data/reference"))
    rn_row = corrected.iloc[0]
    assert rn_row["dynamic_model_source"] == "manual_override"
    assert rn_row["dynamic_bias_2027"] == pytest.approx(0.0)
    assert rn_row["dynamically_corrected_estimate"] == pytest.approx(rn_row["estimate_percent"])
