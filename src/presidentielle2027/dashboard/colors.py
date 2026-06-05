from __future__ import annotations

from typing import Any

PARTY_COLORS: dict[str, str] = {
    "LFI": "#C62828",
    "PCF": "#B71C1C",
    "PS": "#E91E63",
    "PS-PP": "#E91E63",
    "PP": "#E91E63",
    "EELV": "#2E7D32",
    "RE": "#F4A300",
    "ENS": "#F4A300",
    "HOR": "#C88B00",
    "LR": "#1565C0",
    "DLF": "#5D6D7E",
    "UDR": "#3949AB",
    "RN": "#0D47A1",
    "REC": "#00ACC1",
    "NFP": "#C62828",
    "DVG": "#F8A5B6",
    "ECO": "#39D353",
    "DVD": "#AFC6FF",
    "DVC": "#F6D8A8",
    "EXG": "#AD1457",
    "DSV": "#7E57C2",
    "DIV": "#757575",
}

FAMILY_COLORS: dict[str, str] = {
    "far_left": "#AD1457",
    "extrême_gauche": "#AD1457",
    "left": "#D32F2F",
    "gauche": "#D32F2F",
    "gauche_radicale": "#C62828",
    "centre_left": "#EC407A",
    "centre_gauche": "#EC407A",
    "greens": "#2E7D32",
    "green": "#2E7D32",
    "écologistes": "#2E7D32",
    "centre": "#F9A825",
    "centre_droit": "#5C6BC0",
    "gaullist_right": "#3F51B5",
    "droite_gaulliste": "#3F51B5",
    "right": "#1565C0",
    "droite": "#1565C0",
    "sovereigntist_right": "#283593",
    "droite_souverainiste": "#283593",
    "nationalist_right": "#0D47A1",
    "droite_nationale": "#0D47A1",
    "far_right": "#00838F",
    "extrême_droite": "#00838F",
    "other": "#757575",
    "hors_champ": "#757575",
    "generic_bloc": "#9E9E9E",
}

DEFAULT_CANDIDATE_COLOR = "#616161"


def get_political_color(candidate_party: Any = None, political_family: Any = None) -> str:
    party = str(candidate_party).strip() if candidate_party not in (None, "") else ""
    family = str(political_family).strip() if political_family not in (None, "") else ""
    if party in PARTY_COLORS:
        return PARTY_COLORS[party]
    if family in FAMILY_COLORS:
        return FAMILY_COLORS[family]
    return DEFAULT_CANDIDATE_COLOR
