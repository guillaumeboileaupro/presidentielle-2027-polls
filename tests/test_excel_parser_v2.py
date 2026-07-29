from pathlib import Path

import pandas as pd

from presidentielle2027.extraction.excel_parser import (
    _correct_poll_units_by_scenario,
    _parse_raw_poll_percent,
    workbook_to_normalized_dataframe,
)


def test_workbook_v2_to_normalized_dataframe() -> None:
    frame = workbook_to_normalized_dataframe(
        Path("data/raw/presidentielle_2027_sondages_wikipedia_extraction_v2.xlsx")
    )
    assert not frame.empty
    assert set(frame["round"].unique()) == {"first_round", "second_round"}
    assert frame["scenario_name"].notna().all()
    assert frame["fieldwork_start_date"].notna().any()


def test_raw_poll_percent_preserves_percentage_scale() -> None:
    assert _parse_raw_poll_percent("31 Le Pen") == 31.0
    assert _parse_raw_poll_percent("3,5 %") == 3.5


def test_scenario_total_above_110_does_not_rescale_valid_percentages() -> None:
    frame = pd.DataFrame(
        {
            "poll_id": ["poll-1"] * 4,
            "round": ["first_round"] * 4,
            "scenario_name": ["Alternatives"] * 4,
            "estimate_percent": [31.0, 36.0, 30.0, 25.0],
        }
    )

    corrected = _correct_poll_units_by_scenario(frame)

    assert corrected["estimate_percent"].tolist() == [31.0, 36.0, 30.0, 25.0]


def test_only_individually_impossible_percentages_are_corrected() -> None:
    frame = pd.DataFrame(
        {
            "poll_id": ["poll-1", "poll-1"],
            "round": ["first_round", "first_round"],
            "scenario_name": ["A", "A"],
            "estimate_percent": [2195.0, 31.0],
        }
    )

    corrected = _correct_poll_units_by_scenario(frame)

    assert corrected["estimate_percent"].tolist() == [21.95, 31.0]
