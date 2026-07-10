import pandas as pd

from presidentielle2027.dashboard.party_assets import (
    build_force_summary_table,
    get_family_display_label,
    get_party_display_label,
    get_party_logo_url,
    resolve_party_logo_filename,
)


def test_ps_pp_logo_depends_on_candidate_name() -> None:
    glucksmann_logo = get_party_logo_url("PS-PP", "Raphaël Glucksmann")
    hollande_logo = get_party_logo_url("PS-PP", "François Hollande")
    pp_logo = get_party_logo_url("PP", "Raphaël Glucksmann")

    assert "Logo%20Place%20publique.svg" in glucksmann_logo
    assert "Le%20Parti%20socialiste%20wordmark.svg" in hollande_logo
    assert "Logo%20Place%20publique.svg" in pp_logo


def test_resolve_party_logo_filename_normalizes_ren_and_epr() -> None:
    assert resolve_party_logo_filename("REN") == "Renaissance parti logo.svg"
    assert resolve_party_logo_filename("EPR") == "Renaissance parti logo.svg"


def test_display_labels_are_user_facing() -> None:
    assert get_party_display_label("RN") == "Rassemblement national"
    assert get_party_display_label("LFH") == "La France humaniste"
    assert get_party_display_label(None) == "Sans étiquette"

    assert get_family_display_label("centre_gauche") == "Centre gauche"
    assert get_family_display_label("extrême_droite") == "Extrême droite"
    assert get_family_display_label(None) == "Non renseigné"


def test_build_force_summary_table_returns_unique_display_columns() -> None:
    frame = pd.DataFrame(
        [
            {
                "publication_date": "2026-06-10",
                "force_name": "RN",
                "candidate_party": "RN",
                "political_family": "extrême_droite",
                "estimate_percent": 34.5,
                "candidate_name": "Jordan Bardella",
            },
            {
                "publication_date": "2026-06-11",
                "force_name": "RE",
                "candidate_party": "RE",
                "political_family": "centre",
                "estimate_percent": 16.2,
                "candidate_name": "Gabriel Attal",
            },
        ]
    )

    summary = build_force_summary_table(frame, "force_name", "estimate_percent")

    assert list(summary.columns) == [
        "party_logo",
        "force_name",
        "candidate_party",
        "political_family",
        "value_display",
    ]
    assert summary.columns.is_unique
    assert summary.loc[0, "force_name"] == "Rassemblement national"
    assert summary.loc[1, "candidate_party"] == "Renaissance"
