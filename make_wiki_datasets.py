#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Extraction complète des tableaux et du contenu Wikipédia demandés.

Ce script génère 3 fichiers CSV de tableaux, un par page Wikipédia :
1. sondages_presidentielle_2027_wikipedia_tables.csv
2. sondages_presidentielle_2022_wikipedia_tables.csv
3. sondages_legislatives_2024_wikipedia_tables.csv

Il génère aussi 3 fichiers CSV de contenu textuel structuré :
1. sondages_presidentielle_2027_wikipedia_content_blocks.csv
2. sondages_presidentielle_2022_wikipedia_content_blocks.csv
3. sondages_legislatives_2024_wikipedia_content_blocks.csv

Il conserve aussi :
- source_page
- source_url
- table_index
- row_index
- les colonnes Wikipédia originales aplaties
- les liens extraits de chaque ligne quand disponibles

Usage :
    python make_wiki_datasets.py

Dépendances :
    pip install pandas lxml beautifulsoup4 requests openpyxl
"""

from __future__ import annotations

import json
import argparse
import re
import sys
from io import StringIO
from pathlib import Path
from urllib.parse import urljoin

import pandas as pd
import requests
from bs4 import BeautifulSoup
from requests import RequestException


PAGES = [
    {
        "key": "presidentielle_2027",
        "title": "Liste de sondages sur l'élection présidentielle française de 2027",
        "url": "https://fr.wikipedia.org/wiki/Liste_de_sondages_sur_l%27%C3%A9lection_pr%C3%A9sidentielle_fran%C3%A7aise_de_2027",
        "output_csv": "sondages_presidentielle_2027_wikipedia_tables.csv",
        "content_csv": "sondages_presidentielle_2027_wikipedia_content_blocks.csv",
    },
    {
        "key": "presidentielle_2022",
        "title": "Liste de sondages sur l'élection présidentielle française de 2022",
        "url": "https://fr.wikipedia.org/wiki/Liste_de_sondages_sur_l%27%C3%A9lection_pr%C3%A9sidentielle_fran%C3%A7aise_de_2022",
        "output_csv": "sondages_presidentielle_2022_wikipedia_tables.csv",
        "content_csv": "sondages_presidentielle_2022_wikipedia_content_blocks.csv",
    },
    {
        "key": "legislatives_2024",
        "title": "Liste de sondages sur les élections législatives françaises de 2024",
        "url": "https://fr.wikipedia.org/wiki/Liste_de_sondages_sur_les_%C3%A9lections_l%C3%A9gislatives_fran%C3%A7aises_de_2024",
        "output_csv": "sondages_legislatives_2024_wikipedia_tables.csv",
        "content_csv": "sondages_legislatives_2024_wikipedia_content_blocks.csv",
    },
]


def flatten_columns(df: pd.DataFrame) -> pd.DataFrame:
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [
            " | ".join(str(x).strip() for x in col if str(x).strip() and str(x) != "nan")
            for col in df.columns
        ]
    else:
        df.columns = [str(c).strip() for c in df.columns]

    seen: dict[str, int] = {}
    new_cols: list[str] = []
    for col in df.columns:
        base = col if col else "column"
        if base not in seen:
            seen[base] = 0
            new_cols.append(base)
        else:
            seen[base] += 1
            new_cols.append(f"{base}_{seen[base]}")
    df.columns = new_cols
    return df


def clean_cell(value: object) -> str:
    if pd.isna(value):
        return ""
    text = str(value).replace("\xa0", " ")
    return re.sub(r"\s+", " ", text).strip()


def extract_row_links(table: BeautifulSoup, row_index: int, base_url: str) -> str:
    rows = table.find_all("tr")
    body_rows = [row for row in rows if row.find_all(["td", "th"])]
    if row_index + 1 >= len(body_rows):
        return ""

    row = body_rows[row_index + 1]
    links: list[dict[str, str]] = []
    for anchor in row.find_all("a", href=True):
        href = anchor["href"]
        if href.startswith("#"):
            continue
        links.append(
            {
                "label": anchor.get_text(" ", strip=True),
                "url": urljoin(base_url, href),
            }
        )
    return json.dumps(links, ensure_ascii=False)


def nearest_heading(table: BeautifulSoup | None) -> str:
    node = table
    while node:
        node = node.find_previous()
        if not node:
            return ""
        if node.name in {"h2", "h3", "h4"}:
            return node.get_text(" ", strip=True)
    return ""


def extract_content_blocks(page: dict[str, str], cache_dir: Path | None = None) -> pd.DataFrame:
    url = page["url"]
    html = fetch_html(page, cache_dir=cache_dir)
    soup = BeautifulSoup(html, "lxml")
    content_root = soup.select_one("div.mw-parser-output")
    if content_root is None:
        return pd.DataFrame(
            columns=[
                "source_page",
                "source_url",
                "page_key",
                "block_index",
                "section",
                "subsection",
                "tag",
                "text",
                "links_json",
            ]
        )

    current_h2 = ""
    current_h3 = ""
    rows: list[dict[str, object]] = []
    block_index = 0
    for node in content_root.children:
        if getattr(node, "name", None) is None:
            continue
        if node.name == "h2":
            current_h2 = clean_cell(node.get_text(" ", strip=True))
            current_h3 = ""
            continue
        if node.name == "h3":
            current_h3 = clean_cell(node.get_text(" ", strip=True))
            continue
        if node.name not in {"p", "ul", "ol", "dl", "blockquote"}:
            continue
        text = clean_cell(node.get_text(" ", strip=True))
        if not text:
            continue
        links = []
        for anchor in node.find_all("a", href=True):
            href = anchor["href"]
            if href.startswith("#"):
                continue
            links.append(
                {
                    "label": clean_cell(anchor.get_text(" ", strip=True)),
                    "url": urljoin(url, href),
                }
            )
        rows.append(
            {
                "source_page": page["title"],
                "source_url": url,
                "page_key": page["key"],
                "block_index": block_index,
                "section": current_h2,
                "subsection": current_h3,
                "tag": node.name,
                "text": text,
                "links_json": json.dumps(links, ensure_ascii=False),
            }
        )
        block_index += 1
    return pd.DataFrame(rows)


def fetch_html(page: dict[str, str], cache_dir: Path | None = None, timeout: int = 60) -> str:
    cache_dir = cache_dir or (Path("data") / "raw" / "wikipedia_html")
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_path = cache_dir / f"{page['key']}.html"
    if cache_path.exists():
        return cache_path.read_text(encoding="utf-8")

    headers = {"User-Agent": "Mozilla/5.0 compatible; poll-dataset-extractor/1.0"}
    response = requests.get(page["url"], headers=headers, timeout=timeout)
    response.raise_for_status()
    html = response.text
    cache_path.write_text(html, encoding="utf-8")
    return html


def extract_page(page: dict[str, str], cache_dir: Path | None = None) -> pd.DataFrame:
    url = page["url"]
    print(f"Extraction : {page['title']}", file=sys.stderr)
    html = fetch_html(page, cache_dir=cache_dir)
    soup = BeautifulSoup(html, "lxml")

    tables = soup.find_all("table", class_=lambda cls: cls and "wikitable" in cls)
    dfs = pd.read_html(StringIO(html))

    extracted: list[pd.DataFrame] = []
    for table_index, df in enumerate(dfs):
        if df.empty:
            continue

        df = flatten_columns(df)
        df = df.apply(lambda column: column.map(clean_cell))

        html_table = tables[table_index] if table_index < len(tables) else None
        section = nearest_heading(html_table) if html_table else ""

        df.insert(0, "source_page", page["title"])
        df.insert(1, "source_url", url)
        df.insert(2, "page_key", page["key"])
        df.insert(3, "table_index", table_index)
        df.insert(4, "section", section)
        df.insert(5, "row_index", range(len(df)))
        if html_table is not None:
            df["row_links_json"] = [extract_row_links(html_table, i, url) for i in range(len(df))]
        else:
            df["row_links_json"] = ""
        extracted.append(df)

    if not extracted:
        return pd.DataFrame(
            columns=[
                "source_page",
                "source_url",
                "page_key",
                "table_index",
                "section",
                "row_index",
                "row_links_json",
            ]
        )
    return pd.concat(extracted, ignore_index=True, sort=False)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", default=".", help="Dossier de sortie des CSV/XLSX")
    parser.add_argument(
        "--cache-dir",
        default="data/raw/wikipedia_html",
        help="Dossier de cache HTML local. Si les fichiers existent, aucun accès réseau n’est nécessaire.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    out_dir = Path(args.output_dir)
    cache_dir = Path(args.cache_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    all_frames: list[pd.DataFrame] = []
    all_content_frames: list[pd.DataFrame] = []
    try:
        for page in PAGES:
            df = extract_page(page, cache_dir=cache_dir)
            output = out_dir / page["output_csv"]
            df.to_csv(output, index=False, encoding="utf-8-sig")
            print(f"OK : {output} ({len(df)} lignes, {len(df.columns)} colonnes)", file=sys.stderr)
            all_frames.append(df)
            content_df = extract_content_blocks(page, cache_dir=cache_dir)
            content_output = out_dir / page["content_csv"]
            content_df.to_csv(content_output, index=False, encoding="utf-8-sig")
            print(
                f"OK : {content_output} ({len(content_df)} blocs, {len(content_df.columns)} colonnes)",
                file=sys.stderr,
            )
            all_content_frames.append(content_df)
    except RequestException as exc:
        print(
            "Erreur réseau vers Wikipédia. "
            "Vérifie l’accès Internet/DNS ou place les fichiers HTML dans "
            f"'{cache_dir}'. Détail: {exc}",
            file=sys.stderr,
        )
        raise SystemExit(2) from exc

    xlsx = out_dir / "wikipedia_sondages_2022_2024_2027_tables.xlsx"
    with pd.ExcelWriter(xlsx, engine="openpyxl") as writer:
        for page, df in zip(PAGES, all_frames):
            df.to_excel(writer, sheet_name=page["key"][:31], index=False)
        for page, content_df in zip(PAGES, all_content_frames):
            content_df.to_excel(writer, sheet_name=f"{page['key'][:23]}_content", index=False)
    print(f"OK : {xlsx}", file=sys.stderr)


if __name__ == "__main__":
    main()
