from __future__ import annotations

from pathlib import Path

import pandas as pd


COMPLETE_WIKI_ZIP_DIR = Path("data/imported_wiki_zip_complete")

WIKI_COMPLETE_FILES = {
    "2022": {
        "label": "Présidentielle 2022",
        "slug": "Liste_de_sondages_sur_lélection_présidentielle_française_de_2022",
        "source_url": "https://fr.wikipedia.org/wiki/Liste_de_sondages_sur_l%27%C3%A9lection_pr%C3%A9sidentielle_fran%C3%A7aise_de_2022",
    },
    "2024": {
        "label": "Législatives 2024",
        "slug": "Liste_de_sondages_sur_les_élections_législatives_françaises_de_2024",
        "source_url": "https://fr.wikipedia.org/wiki/Liste_de_sondages_sur_les_%C3%A9lections_l%C3%A9gislatives_fran%C3%A7aises_de_2024",
    },
    "2027": {
        "label": "Présidentielle 2027",
        "slug": "Liste_de_sondages_sur_lélection_présidentielle_française_de_2027",
        "source_url": "https://fr.wikipedia.org/wiki/Liste_de_sondages_sur_l%27%C3%A9lection_pr%C3%A9sidentielle_fran%C3%A7aise_de_2027",
    },
}


def _csv_base_path(year_key: str) -> Path:
    config = WIKI_COMPLETE_FILES[year_key]
    return COMPLETE_WIKI_ZIP_DIR / f"csv_from_pdf_{config['slug']}"


def load_complete_visual_rows(year_key: str) -> pd.DataFrame:
    path = _csv_base_path(year_key) / f"{WIKI_COMPLETE_FILES[year_key]['slug']}_visual_rows.csv"
    if not path.exists():
        return pd.DataFrame()
    frame = pd.read_csv(path)
    frame["source_url"] = WIKI_COMPLETE_FILES[year_key]["source_url"]
    return frame


def load_complete_layout_lines(year_key: str) -> pd.DataFrame:
    path = _csv_base_path(year_key) / f"{WIKI_COMPLETE_FILES[year_key]['slug']}_pdftotext_layout_lines.csv"
    if not path.exists():
        return pd.DataFrame()
    frame = pd.read_csv(path)
    frame["source_url"] = WIKI_COMPLETE_FILES[year_key]["source_url"]
    return frame


def build_complete_zip_registry() -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for year_key, config in WIKI_COMPLETE_FILES.items():
        visual_rows = load_complete_visual_rows(year_key)
        layout_lines = load_complete_layout_lines(year_key)
        rows.append(
            {
                "Périmètre": config["label"],
                "Visual rows": int(len(visual_rows)),
                "Layout lines": int(len(layout_lines)),
                "Source": config["source_url"],
                "Statut": "Importé depuis le zip complet",
            }
        )
    return pd.DataFrame(rows)
