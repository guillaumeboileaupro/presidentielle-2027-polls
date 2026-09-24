import pandas as pd

from presidentielle2027.dashboard.views.wikipedia_2027 import (
    build_wikipedia_style_table,
    wikipedia_table_cell_styles,
)


def test_wikipedia_style_table_has_one_row_and_one_column_per_candidate() -> None:
    frame = pd.DataFrame(
        {
            "poll_id": ["p1", "p1", "p1"],
            "round": ["first_round"] * 3,
            "scenario_name": ["Hypothèse A"] * 3,
            "candidate_name": ["Nicolas Dupont-Aignan", "Éric Zemmour", "Sarah Knafo"],
            "estimate_percent": [2.5, 3.5, None],
            "polling_company": ["Institut"] * 3,
            "sample_size": [1000] * 3,
            "fieldwork_date_raw": ["1-2 septembre"] * 3,
            "parse_status": ["parsed", "parsed", "not_tested"],
        }
    )

    table = build_wikipedia_style_table(frame)

    assert len(table) == 1
    assert table.loc[0, "Sondeur"] == "Institut"
    assert table.loc[0, "Nicolas Dupont-Aignan"] == "2.5"
    assert table.loc[0, "Éric Zemmour"] == "3.5"
    assert table.loc[0, "Sarah Knafo"] == "—"


def test_wikipedia_table_styles_bold_and_color_the_two_qualified_candidates() -> None:
    row = pd.Series(
        {
            "Sondeur": "Institut",
            "Marine Le Pen": "34.5",
            "Édouard Philippe": "17",
            "Éric Zemmour": "4",
            "Nicolas Dupont-Aignan": "2.5",
        }
    )

    styles = dict(zip(row.index, wikipedia_table_cell_styles(row)))

    assert "font-weight: 800" in styles["Marine Le Pen"]
    assert "background-color: #0D378A" in styles["Marine Le Pen"]
    assert "font-weight: 800" in styles["Édouard Philippe"]
    assert "background-color: #0001B8" in styles["Édouard Philippe"]
    assert styles["Éric Zemmour"] == ""
    assert styles["Nicolas Dupont-Aignan"] == ""


def test_wikipedia_style_table_keeps_cluster17_and_sorts_latest_first() -> None:
    frame = pd.DataFrame(
        {
            "poll_id": ["old", "recent"],
            "round": ["first_round", "first_round"],
            "scenario_name": ["Ancien", "Récent"],
            "candidate_name": ["Éric Zemmour", "Éric Zemmour"],
            "estimate_percent": [6.0, 4.0],
            "polling_company": ["Cluster17[m]", "Cluster17"],
            "sample_size": [1000, 1506],
            "fieldwork_date_raw": ["2-5 avril", "22-24 juillet"],
            "publication_date": ["2024-04-05", "2026-07-24"],
            "parse_status": ["parsed", "parsed"],
        }
    )

    table = build_wikipedia_style_table(frame)

    assert table["Sondeur"].tolist() == ["Cluster17", "Cluster17"]
    assert table["Hypothèse"].tolist() == ["Récent", "Ancien"]


def test_wikipedia_style_table_shows_bounded_scores_instead_of_not_tested() -> None:
    frame = pd.DataFrame(
        {
            "poll_id": ["p1"] * 3,
            "round": ["first_round"] * 3,
            "scenario_name": ["Hypothèse A"] * 3,
            "candidate_name": ["Arlette Arthaud", "Éric Zemmour", "Sarah Knafo"],
            "estimate_percent": [None, 3.5, None],
            "upper_bound_percent": [1.0, None, None],
            "polling_company": ["Institut"] * 3,
            "sample_size": [1000] * 3,
            "fieldwork_date_raw": ["1-2 septembre"] * 3,
            "parse_status": ["bounded_estimate", "parsed", "not_tested"],
        }
    )

    table = build_wikipedia_style_table(frame)

    assert table.loc[0, "Arlette Arthaud"] == "<1"
    assert table.loc[0, "Éric Zemmour"] == "3.5"
    assert table.loc[0, "Sarah Knafo"] == "—"


def test_wikipedia_style_table_formats_sample_size_as_readable_integer() -> None:
    frame = pd.DataFrame(
        {
            "poll_id": ["p1", "p2", "p3"],
            "round": ["first_round"] * 3,
            "scenario_name": ["A", "B", "C"],
            "candidate_name": ["Éric Zemmour"] * 3,
            "estimate_percent": [3.0, 4.0, 5.0],
            "polling_company": ["Institut"] * 3,
            "sample_size": [1943.0, 13060.0, None],
            "fieldwork_date_raw": ["1-2 septembre"] * 3,
            "parse_status": ["parsed"] * 3,
        }
    )

    table = build_wikipedia_style_table(frame).set_index("Hypothèse")

    assert table.loc["A", "Échantillon"] == "1\u00a0943"
    assert table.loc["B", "Échantillon"] == "13\u00a0060"
    assert table.loc["C", "Échantillon"] == "—"
