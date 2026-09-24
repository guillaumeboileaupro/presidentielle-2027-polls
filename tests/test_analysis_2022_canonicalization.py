"""Regression tests for the 2022 historical loader's party/family vocabulary.

`analysis_2022.py::_load_2022_first_round_from_wiki_tables` bypasses the main
ingestion pipeline (it reads `sondages_presidentielle_2022_wikipedia_tables.csv`
directly), so its `WIKI_2022_FORCE_MAP` used to hardcode English family names
("left", "green", "far_right", ...) instead of the canonical French
`political_family` vocabulary produced by `canonicalization.py` for the rest
of the app, and computed `broad_bloc` as a raw copy of `political_family`
instead of going through the shared `normalize_broad_bloc` helper used
everywhere else (second_round_raw.py, dynamic_poll_bias.py,
analysis_2024_projection_logic.py, historical_corrections.py itself).

Note: `force_label` keeps the historical "PS-PP" bucket value on purpose for
Hidalgo/Taubira. That string is a deliberate, self-contained join key shared
with `data/reference/historical_results_2022_presidential_first_round.csv`
for this 2022 backtesting feature specifically (no "Place Publique" candidate
existed in 2022), not the same "composite alias that must be resolved
per-candidate" concept `canonicalization.py` handles for the 2027 dataset.
Renaming it would require touching that reference CSV, which is out of scope
for a code-quality fix.
"""

from __future__ import annotations

import pandas as pd

from presidentielle2027.analytics.historical_corrections import normalize_broad_bloc
from presidentielle2027.dashboard.views.analysis_2022 import WIKI_2022_FORCE_MAP

CANONICAL_POLITICAL_FAMILIES = {
    "extrême_gauche",
    "gauche",
    "gauche_radicale",
    "centre_gauche",
    "écologistes",
    "centre",
    "centre_droit",
    "droite_gaulliste",
    "droite",
    "droite_souverainiste",
    "droite_nationale",
    "extrême_droite",
    "autres",
    "hors_champ",
}

ENGLISH_LEFTOVERS = {
    "far_left",
    "left",
    "green",
    "greens",
    "right",
    "far_right",
    "sovereigntist_right",
    "gaullist_right",
    "nationalist_right",
    "other",
}


def test_wiki_2022_force_map_uses_canonical_french_family_vocabulary() -> None:
    families = {family for _, _, family in WIKI_2022_FORCE_MAP.values()}
    assert families <= CANONICAL_POLITICAL_FAMILIES
    assert not (families & ENGLISH_LEFTOVERS)


def test_wiki_2022_force_map_candidate_family_assignments_unchanged() -> None:
    expected = {
        "Nathalie Arthaud": "extrême_gauche",
        "Philippe Poutou": "extrême_gauche",
        "Fabien Roussel": "gauche",
        "Jean-Luc Mélenchon": "gauche",
        "Anne Hidalgo": "gauche",
        "Yannick Jadot": "écologistes",
        "Emmanuel Macron": "centre",
        "Valérie Pécresse": "droite",
        "Jean Lassalle": "autres",
        "Nicolas Dupont-Aignan": "droite_souverainiste",
        "Marine Le Pen": "extrême_droite",
        "Éric Zemmour": "extrême_droite",
        "Christiane Taubira": "gauche",
    }
    actual = {candidate: family for _, candidate, family in WIKI_2022_FORCE_MAP.values()}
    assert actual == expected


def test_broad_bloc_for_2022_history_uses_shared_normalizer() -> None:
    history = pd.DataFrame(
        [
            {"force_label": force_label, "political_family": family}
            for force_label, _, family in WIKI_2022_FORCE_MAP.values()
        ]
    )
    broad_bloc = history.apply(
        lambda row: normalize_broad_bloc(row.get("force_label"), row.get("political_family")),
        axis=1,
    )
    # PS-PP is a recognized party-code key in BROAD_BLOC_MAP (historical_corrections.py),
    # so it resolves without ever needing the political_family fallback.
    assert set(broad_bloc[history["force_label"] == "PS-PP"]) == {"centre_gauche"}
    assert "autres" not in broad_bloc[history["force_label"] != "DIV"].to_numpy()
