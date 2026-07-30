from presidentielle2027.dashboard.views.first_round_raw import (
    WIKIPEDIA_BLOC_ORDER,
    _wikipedia_bloc_label,
)


def test_wikipedia_blocs_match_reference_chart_legend() -> None:
    assert WIKIPEDIA_BLOC_ORDER == ["PCF", "LFI", "ECO", "PS", "ENS", "LR", "RN", "REC"]


def test_wikipedia_blocs_combine_successor_party_labels() -> None:
    assert _wikipedia_bloc_label("EELV") == "ECO"
    assert _wikipedia_bloc_label("PP") == "PS"
    assert _wikipedia_bloc_label("RE") == "ENS"
    assert _wikipedia_bloc_label("HOR") == "ENS"
    assert _wikipedia_bloc_label("RN") == "RN"
    assert _wikipedia_bloc_label("LO") is None
