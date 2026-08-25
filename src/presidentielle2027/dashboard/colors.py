from __future__ import annotations

PARTY_COLORS: dict[str, str] = {
    "LO": "#BB0000",
    "LFI": "#4C0297",
    "PCF": "#DD0000",
    "PS": "#E8528D",
    "PP": "#FFEC00",
    "EELV": "#109910",
    "RE": "#FFEB00",
    "ENS": "#FED700",
    "HOR": "#0001B8",
    "LFH": "#ADC1FD",
    "MoDem": "#FFB74D",
    "MODEM": "#FFB74D",
    "LR": "#0066CC",
    "DLF": "#0082C4",
    "UDR": "#3949AB",
    "RN": "#0D378A",
    "REC": "#333333",
    "NPA-A": "#8E244D",
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
    "far_left": "#F80606",
    "extrême_gauche": "#AD1457",
    "left": "#D32F2F",
    "gauche": "#D32F2F",
    "gauche_radicale": "#C62828",
    "centre_gauche": "#EC407A",
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


def get_political_color(candidate_party: object = None, political_family: object = None) -> str:
    party = str(candidate_party).strip() if candidate_party not in (None, "") else ""
    family = str(political_family).strip() if political_family not in (None, "") else ""
    if party in PARTY_COLORS:
        return PARTY_COLORS[party]
    if family in FAMILY_COLORS:
        return FAMILY_COLORS[family]
    return DEFAULT_CANDIDATE_COLOR
