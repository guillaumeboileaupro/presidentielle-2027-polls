import pandas as pd
import pytest

from presidentielle2027.extraction.excel_parser import (
    _correct_poll_units_by_scenario,
    _parse_raw_poll_percent,
    _split_compound_candidate_cell,
)


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


def test_scenario_at_101_is_preserved_as_source_rounding() -> None:
    frame = _scenario([35, 26, 14, 10, 5, 5, 4, 1, 0.5, 0.5])

    corrected = _correct_poll_units_by_scenario(frame)

    assert corrected["estimate_percent"].sum() == pytest.approx(101.0)
    assert not corrected["percentage_correction_applied"].any()
    assert corrected["percentage_correction_reason"].eq("unchanged").all()


def test_less_than_one_is_not_imputed_as_point_five() -> None:
    assert _parse_raw_poll_percent("<1") is None


def test_compound_other_candidate_cell_is_split() -> None:
    assert _split_compound_candidate_cell(
        "6 Ruffin3,5 Lisnard",
        generic_header=True,
    ) == ["6 Ruffin", "3,5 Lisnard"]
    assert _split_compound_candidate_cell(
        "6 Ruffin3,5 Lisnard",
        generic_header=False,
    ) == ["6 Ruffin3,5 Lisnard"]


def _write_first_round_table(tmp_path, poll_cells: list[str]):
    from pathlib import Path

    headers = [
        "Arthaud (LO)",
        "Mélenchon (LFI)",
        "Roussel (PCF)",
        "Le Pen (RN)",
        "Zemmour (REC)",
        "Unnamed: 7_level_1",
        "Autres",
    ]
    meta = ["Sondeur", "Date", "Échantillon"]
    filler = [""] * (len(meta) + len(headers))
    rows = [
        [*meta, *headers],
        [*meta, *headers],
        [*meta, *headers],
        filler,
        ["Ifop", "1-3 septembre 2026", "1 000", *poll_cells],
    ]
    path: Path = tmp_path / "wikipedia-fr-2027-polls-20260924T000000Z-table-01.csv"
    pd.DataFrame(rows).to_csv(path, index=False, header=False)
    return path


def test_bounded_score_keeps_its_own_upper_bound_and_a_clean_candidate_name(tmp_path) -> None:
    from presidentielle2027.extraction.excel_parser import _parse_first_round_raw_wikipedia_table

    table = _write_first_round_table(
        tmp_path,
        ["<1", "12,5", "3", "30", "8", "", "<1 Bonnal2 Lisnard"],
    )

    parsed = _parse_first_round_raw_wikipedia_table(table, fallback_year=2026)

    by_name = parsed.set_index("candidate_name")
    assert not parsed["candidate_name"].str.contains(r"[<\d]", regex=True).any()
    assert not parsed["candidate_name"].str.startswith("Unnamed").any()

    arthaud = by_name.loc["Arlette Arthaud"]
    assert arthaud["parse_status"] == "bounded_estimate"
    assert pd.isna(arthaud["estimate_percent"])
    assert arthaud["upper_bound_percent"] == pytest.approx(1.0)

    bonnal = by_name.loc["Bonnal"]
    assert bonnal["parse_status"] == "bounded_estimate"
    assert bonnal["upper_bound_percent"] == pytest.approx(1.0)

    lisnard = by_name.loc["Lisnard"]
    assert lisnard["estimate_percent"] == pytest.approx(2.0)
    assert lisnard["parse_status"] == "parsed"
    assert pd.isna(lisnard["upper_bound_percent"])


def test_bounded_upper_percent_reads_the_actual_bound() -> None:
    from presidentielle2027.extraction.excel_parser import _bounded_upper_percent

    assert _bounded_upper_percent("<1") == pytest.approx(1.0)
    assert _bounded_upper_percent("< 0,5 Poutou") == pytest.approx(0.5)
    assert _bounded_upper_percent("12") is None
    assert _bounded_upper_percent(None) is None
