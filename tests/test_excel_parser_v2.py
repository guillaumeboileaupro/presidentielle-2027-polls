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


def test_lost_decimal_separators_are_reconstructed_to_100_percent() -> None:
    raw_values = ["1", "16", "25", "35", "105", "165", "8", "15", "35", "3", "2,5"]
    frame = pd.DataFrame(
        {
            "poll_id": ["poll-1"] * len(raw_values),
            "round": ["first_round"] * len(raw_values),
            "scenario_name": ["A"] * len(raw_values),
            "candidate_name": [f"Candidat {index}" for index in range(len(raw_values))],
            "candidate_party": ["LO", "LFI", "PCF", "LE", "PP", "RE", "LR", "DLF", "RN", "REC", None],
            "raw_text_context": raw_values,
            "estimate_percent": [1, 16, 25, 35, 105, 165, 8, 15, 35, 3, 2.5],
        }
    )

    corrected = _correct_poll_units_by_scenario(frame)

    assert corrected["estimate_percent"].sum() == 100.0
    assert corrected["estimate_percent"].tolist() == [1.0, 16.0, 2.5, 3.5, 10.5, 16.5, 8.0, 1.5, 35.0, 3.0, 2.5]


def test_merged_html_cells_are_deduplicated_without_dropping_the_poll() -> None:
    frame = pd.DataFrame(
        {
            "poll_id": ["poll-1"] * 4,
            "round": ["first_round"] * 4,
            "scenario_name": ["A"] * 4,
            "candidate_name": ["Gauche", "Centre", "Centre", "Droite"],
            "raw_text_context": ["20", "25 Philippe", "25 Philippe", "55"],
            "estimate_percent": [20.0, 25.0, 25.0, 55.0],
        }
    )

    corrected = _correct_poll_units_by_scenario(frame)

    assert len(corrected) == 3
    assert corrected["candidate_name"].tolist() == ["Gauche", "Centre", "Droite"]
    assert corrected["estimate_percent"].sum() == 100.0


def test_annotated_colspan_is_deduplicated_across_candidate_headers() -> None:
    frame = pd.DataFrame(
        {
            "poll_id": ["poll-1"] * 4,
            "round": ["first_round"] * 4,
            "scenario_name": ["A"] * 4,
            "candidate_name": ["Gauche commune", "PCF", "Écologistes", "RN"],
            "candidate_party": ["LFI", "PCF", "LE", "RN"],
            "raw_text_context": ["66[h]", "66[h]", "66[h]", "34"],
            "estimate_percent": [66.0, 66.0, 66.0, 34.0],
        }
    )

    corrected = _correct_poll_units_by_scenario(frame)

    assert corrected["candidate_name"].tolist() == ["Gauche commune", "RN"]
    assert corrected["estimate_percent"].tolist() == [66.0, 34.0]
