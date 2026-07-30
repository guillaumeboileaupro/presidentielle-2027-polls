import pandas as pd

from presidentielle2027.dashboard.colors import PARTY_COLORS
from presidentielle2027.dashboard.party_assets import (
    build_force_summary_table,
    get_family_display_label,
    get_party_display_label,
    get_party_logo_url,
    resolve_party_logo_filename,
)


def test_ps_and_pp_have_distinct_logos() -> None:
    pp_logo = get_party_logo_url("PP", "Raphaël Glucksmann")
    ps_logo = get_party_logo_url("PS", "François Hollande")

    assert "Logo%20Place%20publique.svg" in pp_logo
    assert "Le%20Parti%20socialiste%20wordmark.svg" in ps_logo


def test_lfi_uses_the_official_2027_logo() -> None:
    assert get_party_logo_url("LFI") == (
        "https://lafranceinsoumise.fr/wp-content/uploads/2026/05/LOGO-LFI-VIOLET.png"
    )


def test_resolve_party_logo_filename_normalizes_ren() -> None:
    assert resolve_party_logo_filename("REN") == "Renaissance parti logo.svg"
    assert resolve_party_logo_filename("EPR") is None


def test_display_labels_are_user_facing() -> None:
    assert get_party_display_label("RN") == "Rassemblement national"
    assert get_party_display_label("LFH") == "La France humaniste"
    assert get_party_display_label(None) == "Sans étiquette"

    assert get_family_display_label("centre_gauche") == "Centre gauche"
    assert get_family_display_label("extrême_droite") == "Extrême droite"
    assert get_family_display_label(None) == "Non renseigné"


def test_ps_pp_and_eelv_have_distinct_required_colors() -> None:
    assert PARTY_COLORS["LFI"] == "#4C0297"
    assert PARTY_COLORS["PS"] == "#E8528D"
    assert PARTY_COLORS["PP"] == "#FFEC00"
    assert PARTY_COLORS["EELV"] == "#109910"
    assert "PS-PP" not in PARTY_COLORS
    assert "LE" not in PARTY_COLORS


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
