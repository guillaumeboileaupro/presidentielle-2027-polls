from __future__ import annotations

from typing import Any

import pandas as pd

GENERIC_BLOC_LABELS: set[str] = {
    "DIV",
    "DLF",
    "ENS",
    "EXG",
    "LFI",
    "LR",
    "NFP",
    "PS-PP",
    "REC",
    "RN",
    "UDR",
}


CANDIDATE_ALIASES: dict[str, str] = {
    "Arthaud": "Arlette Arthaud",
    "Poutou": "Philippe Poutou",
    "Roussel": "Fabien Roussel",
    "Mélenchon": "Jean-Luc Mélenchon",
    "Melenchon": "Jean-Luc Mélenchon",
    "Jean-Luc Mélenchon": "Jean-Luc Mélenchon",
    "Tondelier": "Marine Tondelier",
    "Glucksmann": "Raphaël Glucksmann",
    "Raphaël Glucksmann": "Raphaël Glucksmann",
    "Philippe": "Édouard Philippe",
    "Edouard Philippe": "Édouard Philippe",
    "Édouard Philippe": "Édouard Philippe",
    "Attal": "Gabriel Attal",
    "Gabriel Attal": "Gabriel Attal",
    "de Villepin": "Dominique de Villepin",
    "Dominique de Villepin": "Dominique de Villepin",
    "Retailleau": "Bruno Retailleau",
    "Bruno Retailleau": "Bruno Retailleau",
    "Dupont-Aignan": "Nicolas Dupont-Aignan",
    "Bardella": "Jordan Bardella",
    "Jordan Bardella": "Jordan Bardella",
    "Le Pen": "Marine Le Pen",
    "Marine Le Pen": "Marine Le Pen",
    "Zemmour": "Éric Zemmour",
    "Eric Zemmour": "Éric Zemmour",
    "Ruffin": "François Ruffin",
    "François Ruffin": "François Ruffin",
    "Maréchal": "Marion Maréchal",
    "Marion Maréchal": "Marion Maréchal",
    "Bayrou": "François Bayrou",
    "Bertrand": "Xavier Bertrand",
    "Darmanin": "Gérald Darmanin",
    "Emmanuel Macron": "Emmanuel Macron",
    "Faure": "Olivier Faure",
    "Hanouna": "Cyril Hanouna",
    "Hollande": "François Hollande",
    "Knafo": "Sarah Knafo",
    "Leclerc": "Michel-Édouard Leclerc",
    "Lecornu": "Sébastien Lecornu",
    "Riner": "Teddy Riner",
    "Sébastien": "Sébastien Chenu",
    "de Villiers": "Philippe de Villiers",
    "Wauquiez": "Laurent Wauquiez",
}

CANDIDATE_PARTY_DEFAULTS: dict[str, str | None] = {
    "Arlette Arthaud": None,
    "Philippe Poutou": None,
    "Fabien Roussel": "PCF",
    "Jean-Luc Mélenchon": "LFI",
    "Marine Tondelier": "EELV",
    "Raphaël Glucksmann": "PS-PP",
    "Édouard Philippe": "HOR",
    "Gabriel Attal": "RE",
    "Dominique de Villepin": None,
    "Bruno Retailleau": "LR",
    "Nicolas Dupont-Aignan": "DLF",
    "Jordan Bardella": "RN",
    "Marine Le Pen": "RN",
    "Éric Zemmour": "REC",
    "François Ruffin": None,
    "François Bayrou": None,
    "Xavier Bertrand": "LR",
    "Gérald Darmanin": "RE",
    "Emmanuel Macron": "RE",
    "Olivier Faure": "PS-PP",
    "Cyril Hanouna": None,
    "François Hollande": "PS-PP",
    "Sarah Knafo": "REC",
    "Michel-Édouard Leclerc": None,
    "Sébastien Lecornu": "RE",
    "Teddy Riner": None,
    "Sébastien Chenu": "RN",
    "Philippe de Villiers": None,
    "Laurent Wauquiez": "LR",
}

POLITICAL_FAMILY_DEFAULTS: dict[str, str | None] = {
    "Arlette Arthaud": "extrême_gauche",
    "Philippe Poutou": "extrême_gauche",
    "Fabien Roussel": "gauche",
    "Jean-Luc Mélenchon": "gauche_radicale",
    "Marine Tondelier": "écologistes",
    "Raphaël Glucksmann": "centre_gauche",
    "Édouard Philippe": "centre_droit",
    "Gabriel Attal": "centre",
    "Dominique de Villepin": "droite_gaulliste",
    "Bruno Retailleau": "droite",
    "Nicolas Dupont-Aignan": "droite_souverainiste",
    "Jordan Bardella": "droite_nationale",
    "Marine Le Pen": "droite_nationale",
    "Éric Zemmour": "extrême_droite",
    "François Ruffin": "gauche",
    "François Bayrou": "centre",
    "Xavier Bertrand": "droite",
    "Gérald Darmanin": "centre_droit",
    "Emmanuel Macron": "centre",
    "Olivier Faure": "centre_gauche",
    "Cyril Hanouna": "hors_champ",
    "François Hollande": "centre_gauche",
    "Sarah Knafo": "extrême_droite",
    "Michel-Édouard Leclerc": "hors_champ",
    "Sébastien Lecornu": "centre_droit",
    "Teddy Riner": "hors_champ",
    "Sébastien Chenu": "droite_nationale",
    "Philippe de Villiers": "droite_souverainiste",
    "Laurent Wauquiez": "droite",
}


def _none_if_na(value: Any) -> Any:
    if value is None or value == "" or pd.isna(value):
        return None
    return value


def canonicalize_candidate_fields(
    candidate_name: Any,
    candidate_party: Any = None,
    political_family: Any = None,
) -> tuple[str, str | None, str | None]:
    raw_name = str(_none_if_na(candidate_name) or "").strip()
    canonical_name = CANDIDATE_ALIASES.get(raw_name, raw_name)

    party = _none_if_na(candidate_party)
    family = _none_if_na(political_family)

    if canonical_name in CANDIDATE_PARTY_DEFAULTS and party is None:
        party = CANDIDATE_PARTY_DEFAULTS[canonical_name]
    if canonical_name in POLITICAL_FAMILY_DEFAULTS and family is None:
        family = POLITICAL_FAMILY_DEFAULTS[canonical_name]
    if canonical_name in GENERIC_BLOC_LABELS:
        party = canonical_name
        family = "generic_bloc"

    return canonical_name, party, family


def is_generic_bloc_label(value: Any) -> bool:
    name = str(_none_if_na(value) or "").strip()
    return name in GENERIC_BLOC_LABELS
