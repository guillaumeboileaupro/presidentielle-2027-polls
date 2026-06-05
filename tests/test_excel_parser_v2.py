from pathlib import Path

from presidentielle2027.extraction.excel_parser import workbook_to_normalized_dataframe


def test_workbook_v2_to_normalized_dataframe() -> None:
    frame = workbook_to_normalized_dataframe(
        Path("data/raw/presidentielle_2027_sondages_wikipedia_extraction_v2.xlsx")
    )
    assert not frame.empty
    assert set(frame["round"].unique()) == {"first_round", "second_round"}
    assert frame["scenario_name"].notna().all()
    assert frame["fieldwork_start_date"].notna().any()
