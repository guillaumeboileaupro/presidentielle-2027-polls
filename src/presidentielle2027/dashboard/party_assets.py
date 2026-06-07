from __future__ import annotations

from html import escape
from pathlib import Path
from urllib.parse import quote

import pandas as pd

from presidentielle2027.dashboard.colors import get_political_color

FI_BRAND = {
    "violet": "#9A36E0",
    "red": "#EF1926",
    "pink": "#E6255B",
    "yellow": "#FFEC00",
    "green": "#4BB166",
    "black": "#1D1D1B",
    "soft_bg": "#FAF7FF",
    "soft_border": "#E4D7FA",
}

COMMONS_SPECIAL_FILEPATH = "https://commons.wikimedia.org/wiki/Special:FilePath/"
PLACEHOLDER_LOGO_PATH = str(Path(__file__).parent / "assets" / "logo-placeholder.svg")

PARTY_LOGO_FILENAMES: dict[str, str] = {
    "LFI": "LFI Logo 2024 (cropped).svg",
    "RN": "Logo Rassemblement National - Cropped.svg",
    "LR": "Les Républicains - logo (France, 2023) (cropped).svg",
    "PS": "Le Parti socialiste wordmark.svg",
    "PS-PP": "Le Parti socialiste wordmark.svg",
    "PP": "Le Parti socialiste wordmark.svg",
    "EELV": "Logo Les Écologistes (France).png",
    "PCF": "PCF LOGO.svg",
    "DLF": "Debout la France logo (2022).png",
    "REC": "Logo du parti Reconquête.svg",
    "RE": "Renaissance parti logo.svg",
    "ENS": "Groupe EPR.png",
    "HOR": "Logo Horizons.svg",
    "NFP": "Logo Nouveau Front Populaire 2024.svg",
    "UDR": "UDR logo.svg",
    "D!": "DemsFrance.png",
}


def get_party_logo_url(candidate_party: object | None) -> str | None:
    if candidate_party is None:
        return PLACEHOLDER_LOGO_PATH
    normalized_party = str(candidate_party).strip()
    if not normalized_party:
        return PLACEHOLDER_LOGO_PATH
    filename = PARTY_LOGO_FILENAMES.get(normalized_party)
    if filename is None:
        return PLACEHOLDER_LOGO_PATH
    return f"{COMMONS_SPECIAL_FILEPATH}{quote(filename, safe='()')}"


def render_app_header() -> str:
    return (
        '<section class="fi-hero"><div class="fi-hero__identity"><div>'
        '<div class="fi-kicker">Présidentielle 2027</div><h1>Forces politiques, biais et redressages</h1>'
        "<p>Lecture des sondages par force politique, avec correction historique 2022 et point d’appui législatif 2024.</p>"
        "</div></div></section>"
    )


def render_candidate_badges(
    frame: pd.DataFrame,
    value_column: str,
    empty_message: str,
    include_remote_logos: bool = False,
) -> str:
    if frame.empty:
        return f'<div class="fi-empty">{escape(empty_message)}</div>'

    working = frame.dropna(subset=["candidate_name"]).copy()
    if working.empty:
        return f'<div class="fi-empty">{escape(empty_message)}</div>'

    sort_columns = [column for column in ["publication_date", value_column] if column in working.columns]
    ascending = [False] * len(sort_columns)
    if sort_columns:
        working = working.sort_values(sort_columns, ascending=ascending)
    latest = working.groupby("candidate_name", dropna=False).head(1).sort_values(value_column, ascending=False)

    cards: list[str] = []
    for row in latest.itertuples(index=False):
        candidate_name = getattr(row, "candidate_name", "")
        candidate_party = getattr(row, "candidate_party", None)
        political_family = getattr(row, "political_family", None)
        estimate = getattr(row, value_column, None)
        color = get_political_color(candidate_party, political_family)
        logo_url = get_party_logo_url(candidate_party) if include_remote_logos else None
        party_label = str(candidate_party).strip() if candidate_party not in (None, "", "nan") else "Sans étiquette"
        value_label = f"{float(estimate):.1f}%" if estimate is not None and pd.notna(estimate) else "n.d."

        if logo_url:
            avatar = f'<img src="{escape(logo_url, quote=True)}" alt="{escape(party_label)}" class="fi-chip__logo" />'
        else:
            avatar = (
                f'<span class="fi-chip__fallback" style="background:{escape(color, quote=True)};">'
                f"{escape(party_label[:3].upper())}</span>"
            )

        cards.append(
            f'<div class="fi-chip" style="border-color:{escape(color, quote=True)};">'
            f'<div class="fi-chip__media">{avatar}</div>'
            '<div class="fi-chip__content">'
            f'<div class="fi-chip__title">{escape(str(candidate_name))}</div>'
            f'<div class="fi-chip__meta">{escape(party_label)}</div>'
            '</div>'
            f'<div class="fi-chip__value" style="color:{escape(color, quote=True)};">{escape(value_label)}</div>'
            '</div>'
        )

    return '<div class="fi-chip-grid">' + "".join(cards) + "</div>"


def build_candidate_summary_table(frame: pd.DataFrame, value_column: str) -> pd.DataFrame:
    if frame.empty:
        return pd.DataFrame()
    if value_column not in frame.columns:
        return pd.DataFrame()
    working = frame.dropna(subset=["candidate_name"]).copy()
    if working.empty:
        return pd.DataFrame()

    sort_columns = [column for column in ["publication_date", value_column] if column in working.columns]
    if sort_columns:
        working = working.sort_values(sort_columns, ascending=[False] * len(sort_columns))
    latest = working.groupby("candidate_name", dropna=False).head(1).copy()
    latest["party_logo"] = latest["candidate_party"].map(get_party_logo_url)
    latest["color"] = latest.apply(
        lambda row: get_political_color(row.get("candidate_party"), row.get("political_family")),
        axis=1,
    )
    latest["value_display"] = latest[value_column].map(lambda x: f"{x:.1f}%" if pd.notna(x) else "n.d.")
    latest = latest.sort_values(value_column, ascending=False)
    columns = [
        "party_logo",
        "candidate_name",
        "candidate_party",
        "political_family",
        "value_display",
        "color",
    ]
    available = [column for column in columns if column in latest.columns]
    return latest[available]


def build_force_summary_table(
    frame: pd.DataFrame,
    force_column: str,
    value_column: str,
    party_column: str = "candidate_party",
    family_column: str = "political_family",
) -> pd.DataFrame:
    if frame.empty or force_column not in frame.columns or value_column not in frame.columns:
        return pd.DataFrame()

    working = frame.copy()
    working["publication_date"] = pd.to_datetime(working.get("publication_date"), errors="coerce")
    working = working.dropna(subset=[force_column, value_column])
    if working.empty:
        return pd.DataFrame()

    sort_columns = [column for column in ["publication_date", value_column] if column in working.columns]
    if sort_columns:
        working = working.sort_values(sort_columns, ascending=[False] * len(sort_columns))

    latest = working.groupby(force_column, dropna=False).head(1).copy()
    latest["party_logo"] = latest[party_column].map(get_party_logo_url) if party_column in latest.columns else None
    latest["value_display"] = latest[value_column].map(lambda x: f"{x:.1f}%" if pd.notna(x) else "n.d.")
    latest = latest.sort_values(value_column, ascending=False)

    columns = {
        force_column: "force_name",
        party_column: "candidate_party",
        family_column: "political_family",
    }
    latest = latest.rename(columns=columns)
    available = [column for column in ["party_logo", "force_name", "candidate_party", "political_family", "value_display"] if column in latest.columns]
    return latest[available]
