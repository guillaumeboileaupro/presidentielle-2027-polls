from presidentielle2027.dashboard.views.first_round_raw import (
    WIKIPEDIA_BLOC_ORDER,
    _party_family_label,
    _wikipedia_bloc_label,
    first_round_scenario_totals,
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


def test_party_family_label_matches_canonical_political_family() -> None:
    """Regression: this used to shortcut on hardcoded party-code buckets that
    disagreed with `extraction.canonicalization.PARTY_FAMILY_DEFAULTS`, e.g.
    RN showed "Extrême droite" instead of the canonical "Droite nationale",
    and LFH showed "Centre" instead of "Droite gaulliste"."""
    assert _party_family_label("droite_nationale") == "Droite nationale"
    assert _party_family_label("droite_gaulliste") == "Droite gaulliste"
    assert _party_family_label("gauche_radicale") == "Gauche radicale"
    assert _party_family_label("centre_gauche") == "Centre-gauche"
    assert _party_family_label("écologistes") == "Écologistes"
    assert _party_family_label(None) == "Non renseigné"


def test_first_round_scenario_totals_include_generic_bloc_rows() -> None:
    """Regression: the dashboard control excluded generic blocs such as NFP and reported
    74 % for a scenario whose published scores sum to 100 %."""
    import pandas as pd

    frame = pd.DataFrame(
        {
            "poll_id": ["p1"] * 4 + ["p2"] * 2,
            "scenario_name": ["s"] * 4 + ["t"] * 2,
            "round": ["first_round"] * 4 + ["second_round"] * 2,
            "candidate_name": ["Marine Le Pen", "NFP", "Autres", "Éric Zemmour", "A", "B"],
            "estimate_percent": [34.0, 26.0, 3.0, 37.0, 50.0, 50.0],
            "is_generic_bloc": [False, True, False, False, False, False],
        }
    )

    totals = first_round_scenario_totals(frame)

    assert totals.to_dict() == {("p1", "s"): 100.0}
