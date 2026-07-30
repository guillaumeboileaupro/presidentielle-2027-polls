from __future__ import annotations

import re

import pandas as pd

GENERIC_BLOC_LABELS: set[str] = {
    "DIV",
    "DLF",
    "ENS",
    "EXG",
    "LFI",
    "LR",
    "NFP",
    "REC",
    "RN",
    "UDR",
}

PARTY_ALIASES: dict[str, str] = {
    "LE": "EELV",
    "EELV": "EELV",
    "Les Écologistes": "EELV",
    "Les Ecologistes": "EELV",
    "Europe Écologie Les Verts": "EELV",
    "Europe Ecologie Les Verts": "EELV",
    "REN": "RE",
    "MDM": "MoDem",
    "MODEM": "MoDem",
    "MoDem": "MoDem",
}

FAMILY_ALIASES: dict[str, str] = {
    "green": "écologistes",
    "greens": "écologistes",
    "ecologistes": "écologistes",
    "écologistes": "écologistes",
    "centre_left": "centre_gauche",
    "centre_gauche": "centre_gauche",
}

POLLING_COMPANY_ALIASES: dict[str, str] = {
    "cluster 17": "Cluster17",
    "cluster17": "Cluster17",
    "harris": "Harris Interactive",
    "harris interactive": "Harris Interactive",
    "harris-interactive": "Harris Interactive",
    "ifop": "Ifop",
}


def canonicalize_polling_company(value: object) -> object:
    """Remove source footnotes and return one stable name per polling company."""
    if value is None or pd.isna(value):
        return value
    text = re.sub(r"\s*\[[a-z0-9]+\]\s*$", "", str(value), flags=re.IGNORECASE)
    text = re.sub(r"\s+", " ", text).strip()
    return POLLING_COMPANY_ALIASES.get(text.casefold(), text)


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
    "Lassalle": "Jean Lassalle",
    "Jean Lassalle": "Jean Lassalle",
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
    "Vallaud": "Boris Vallaud",
    "Boris Vallaud": "Boris Vallaud",
    "de Villiers": "Philippe de Villiers",
    "Wauquiez": "Laurent Wauquiez",
}

CANDIDATE_PARTY_DEFAULTS: dict[str, str | None] = {
    "Arlette Arthaud": "LO",
    "Philippe Poutou": "NPA-A",
    "Fabien Roussel": "PCF",
    "Jean-Luc Mélenchon": "LFI",
    "Marine Tondelier": "EELV",
    "Raphaël Glucksmann": "PP",
    "Édouard Philippe": "HOR",
    "Gabriel Attal": "RE",
    "Dominique de Villepin": "LFH",
    "Bruno Retailleau": "LR",
    "Nicolas Dupont-Aignan": "DLF",
    "Jordan Bardella": "RN",
    "Marine Le Pen": "RN",
    "Jean Lassalle": "RES",
    "Éric Zemmour": "REC",
    "François Ruffin": None,
    "François Bayrou": "MoDem",
    "Xavier Bertrand": "LR",
    "Gérald Darmanin": "RE",
    "Emmanuel Macron": "RE",
    "Olivier Faure": "PS",
    "Cyril Hanouna": None,
    "François Hollande": "PS",
    "Boris Vallaud": "PS",
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
    "Jean Lassalle": "droite_souverainiste",
    "Éric Zemmour": "extrême_droite",
    "François Ruffin": "gauche",
    "François Bayrou": "centre",
    "Xavier Bertrand": "droite",
    "Gérald Darmanin": "centre_droit",
    "Emmanuel Macron": "centre",
    "Olivier Faure": "centre_gauche",
    "Cyril Hanouna": "hors_champ",
    "François Hollande": "centre_gauche",
    "Boris Vallaud": "centre_gauche",
    "Sarah Knafo": "extrême_droite",
    "Michel-Édouard Leclerc": "hors_champ",
    "Sébastien Lecornu": "centre_droit",
    "Teddy Riner": "hors_champ",
    "Sébastien Chenu": "droite_nationale",
    "Philippe de Villiers": "droite_souverainiste",
    "Laurent Wauquiez": "droite",
}

FAMILY_BROAD_BLOC_MAP: dict[str, str] = {
    "far_left": "extrême_gauche",
    "extrême_gauche": "extrême_gauche",
    "left": "gauche",
    "gauche": "gauche",
    "gauche_radicale": "gauche",
    "centre_gauche": "centre_gauche",
    "green": "écologistes",
    "greens": "écologistes",
    "écologistes": "écologistes",
    "centre": "centre",
    "centre_droit": "centre",
    "right": "droite",
    "droite": "droite",
    "gaullist_right": "droite",
    "droite_gaulliste": "droite",
    "sovereigntist_right": "droite",
    "droite_souverainiste": "droite",
    "nationalist_right": "extrême_droite",
    "droite_nationale": "extrême_droite",
    "far_right": "extrême_droite",
    "extrême_droite": "extrême_droite",
    "other": "autres",
    "hors_champ": "autres",
    "generic_bloc": "autres",
}
def _none_if_na(value: object) -> object | None:
    if value is None or value == "" or pd.isna(value):
        return None
    return value


WIKI_2027_PARTY_BY_CANDIDATE: dict[str, str | None] = {
    "Arlette Arthaud": "LO",
    "Philippe Poutou": "NPA-A",
    "Fabien Roussel": "PCF",
    "Jean-Luc Mélenchon": "LFI",
    "Marine Tondelier": "EELV",
    "Raphaël Glucksmann": "PP",
    "Gabriel Attal": "RE",
    "Édouard Philippe": "HOR",
    "Dominique de Villepin": "LFH",
    "Bruno Retailleau": "LR",
    "Nicolas Dupont-Aignan": "DLF",
    "Jordan Bardella": "RN",
    "Marine Le Pen": "RN",
    "Éric Zemmour": "REC",
    "Sarah Knafo": "REC",
    "François Hollande": "PS",
    "Olivier Faure": "PS",
    "Boris Vallaud": "PS",
    "Gérald Darmanin": "RE",
    "Emmanuel Macron": "RE",
    "Sébastien Lecornu": "RE",
    "François Bayrou": "MoDem",
    "Xavier Bertrand": "LR",
}

NOISY_PRESIDENTIAL_PARTIES: set[str] = {
    "D!",
    "DIV",
    "ENS",
    "EPR",
    "NFP",
    "PS-PP",
    "PS / PP",
    "PS/DVG",
    "REN",
    "UDR",
}

FINAL_PARTY_NORMALIZATION: dict[str, str | None] = {
    "D!": None,
    "DIV": None,
    "LE": "EELV",
    "EELV": "EELV",
    "ENS": None,
    "EPR": None,
    "EXG": None,
    "NFP": None,
    "PS-PP": None,
    "PS / PP": None,
    "PS/DVG": "PS",
    "UDR": None,
}

PARTY_FAMILY_DEFAULTS: dict[str, str] = {
    "DLF": "droite_souverainiste",
    "HOR": "centre",
    "EELV": "écologistes",
    "LFI": "gauche_radicale",
    "LFH": "droite_gaulliste",
    "LR": "droite",
    "MoDem": "centre",
    "PCF": "gauche",
    "PP": "centre_gauche",
    "PS": "centre_gauche",
    "RE": "centre",
    "REC": "extrême_droite",
    "RES": "droite_souverainiste",
    "RN": "droite_nationale",
}


def canonicalize_candidate_fields(
    candidate_name: object,
    candidate_party: object = None,
    political_family: object = None,
) -> tuple[str, str | None, str | None]:
    raw_name = str(_none_if_na(candidate_name) or "").strip()
    canonical_name = CANDIDATE_ALIASES.get(raw_name, raw_name)

    # Some raw sources collapse PS and Place Publique into a single "PS-PP" bucket.
    # For dashboard display and candidate-level analysis, keep candidate-specific labels.

    party = _none_if_na(candidate_party)
    family = _none_if_na(political_family)

    if party is not None:
        party = PARTY_ALIASES.get(str(party).strip(), str(party).strip())
    if family is not None:
        family = FAMILY_ALIASES.get(str(family).strip(), str(family).strip())

    if party in {"PS-PP", "PP-PS", "PS/PP", "PP/PS", "PP/PS/DVG", "PS/PP/DVG"}:
        if canonical_name == "Raphaël Glucksmann":
            party = "PP"
        elif canonical_name in {"François Hollande", "Olivier Faure", "Boris Vallaud"}:
            party = "PS"

    if str(candidate_party).strip() in {"EPR", "Ensemble pour la République"}:
        if canonical_name == "Édouard Philippe":
            party = "HOR"
        elif canonical_name in {
            "Gabriel Attal",
            "Gérald Darmanin",
            "Emmanuel Macron",
            "Sébastien Lecornu",
        }:
            party = "RE"

    preferred_party = WIKI_2027_PARTY_BY_CANDIDATE.get(canonical_name)
    if preferred_party is not None:
        if party is None or party in NOISY_PRESIDENTIAL_PARTIES or canonical_name == "Marine Tondelier":
            party = preferred_party

    if canonical_name in CANDIDATE_PARTY_DEFAULTS and party is None:
        party = CANDIDATE_PARTY_DEFAULTS[canonical_name]
    if canonical_name in POLITICAL_FAMILY_DEFAULTS and family is None:
        family = POLITICAL_FAMILY_DEFAULTS[canonical_name]
    if canonical_name in GENERIC_BLOC_LABELS:
        party = canonical_name
        family = "generic_bloc"

    if party is not None:
        party = FINAL_PARTY_NORMALIZATION.get(party, party)

    if party is not None and family is None:
        family = PARTY_FAMILY_DEFAULTS.get(str(party).strip())
    return canonical_name, party, family


def is_generic_bloc_label(value: object) -> bool:
    name = str(_none_if_na(value) or "").strip()
    return name in GENERIC_BLOC_LABELS
