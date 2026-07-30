import pandas as pd
import pytest

from presidentielle2027.extraction.excel_parser import _correct_poll_units_by_scenario


def _scenario(values: list[float], raw: list[str] | None = None) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "poll_id": ["poll"] * len(values),
            "round": ["first_round"] * len(values),
            "scenario_name": ["scenario"] * len(values),
            "candidate_name": [f"Candidat {index}" for index in range(len(values))],
            "candidate_party": [None] * len(values),
            "raw_text_context": raw or [str(value) for value in values],
            "estimate_percent": values,
        }
    )


def test_large_integer_percentages_are_scaled_repeatedly() -> None:
    frame = _scenario([250, 2195, 2785, 2315, 105])
    corrected = _correct_poll_units_by_scenario(frame)
    assert len(corrected) == len(frame)
    assert corrected["candidate_name"].tolist() == frame["candidate_name"].tolist()
    assert corrected["estimate_percent"].tolist() == [25.0, 21.95, 27.85, 23.15, 1.05]
    assert corrected["estimate_percent"].sum() == pytest.approx(99.0)


def test_normal_scenarios_are_not_modified() -> None:
    for values in ([35, 65], [30, 25, 20, 15, 10]):
        frame = _scenario(list(values))
        corrected = _correct_poll_units_by_scenario(frame)
        assert corrected["estimate_percent"].tolist() == list(values)
        assert not corrected["percentage_correction_applied"].any()


def test_ambiguous_scenario_is_retained_and_not_arbitrarily_changed() -> None:
    frame = _scenario([60, 60, 40])
    corrected = _correct_poll_units_by_scenario(frame)
    assert len(corrected) == len(frame)
    assert corrected["estimate_percent"].tolist() == [60, 60, 40]
    assert corrected["percentage_correction_reason"].eq("ambiguous_multiple_solutions").all()
