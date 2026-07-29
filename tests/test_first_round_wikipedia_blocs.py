import pandas as pd

from presidentielle2027.dashboard.views.first_round_raw import (
    WIKIPEDIA_BLOC_ORDER,
    _select_primary_first_round_scenarios,
    _wikipedia_bloc_label,
)


def test_wikipedia_blocs_match_reference_chart_legend() -> None:
    assert WIKIPEDIA_BLOC_ORDER == ["PCF", "LFI", "ECO", "PS", "ENS", "LR", "RN", "REC"]


def test_wikipedia_blocs_combine_successor_party_labels() -> None:
    assert _wikipedia_bloc_label("LE") == "ECO"
    assert _wikipedia_bloc_label("PP") == "PS"
    assert _wikipedia_bloc_label("RE") == "ENS"
    assert _wikipedia_bloc_label("HOR") == "ENS"
    assert _wikipedia_bloc_label("RN") == "RN"
    assert _wikipedia_bloc_label("LO") is None


def test_primary_scenario_must_total_close_to_100_percent() -> None:
    frame = pd.DataFrame(
        {
            "poll_id": ["poll-1"] * 6,
            "scenario_name": ["incomplet"] * 3 + ["complet"] * 3,
            "candidate_name": ["A", "B", "C", "A", "B", "C"],
            "candidate_party": ["LFI", "RN", "ENS"] * 2,
            "estimate_percent": [3.0, 36.0, 18.0, 20.0, 36.0, 44.0],
        }
    )

    selected = _select_primary_first_round_scenarios(frame)

    assert selected["scenario_name"].unique().tolist() == ["complet"]
    assert selected["scenario_total"].unique().tolist() == [100.0]


def test_primary_scenario_prefers_total_closest_to_100() -> None:
    frame = pd.DataFrame(
        {
            "poll_id": ["poll-1"] * 6,
            "scenario_name": ["total-96"] * 3 + ["total-100"] * 3,
            "candidate_name": ["A", "B", "C", "A", "B", "C"],
            "candidate_party": ["LFI", "RN", "ENS"] * 2,
            "estimate_percent": [20.0, 36.0, 40.0, 20.0, 36.0, 44.0],
        }
    )

    selected = _select_primary_first_round_scenarios(frame)

    assert selected["scenario_name"].unique().tolist() == ["total-100"]
