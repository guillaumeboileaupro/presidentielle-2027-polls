from __future__ import annotations

from dataclasses import dataclass
from io import StringIO
from pathlib import Path
from urllib.parse import quote

import pandas as pd
import requests

WIKIPEDIA_API_URL = "https://fr.wikipedia.org/w/api.php"
USER_AGENT = "Mozilla/5.0 (compatible; CodexNFPMapper/1.0)"
OUTPUT_PATH = Path("data/reference/nfp_internal_party_mapping_2024.csv")


def normalize_person_key(first_name: object, last_name: object) -> str:
    first = str(first_name or "").strip().upper()
    last = str(last_name or "").strip().upper()
    return " ".join(part for part in [first, last] if part).strip()


def normalize_party_label(raw: object) -> str | None:
    text = str(raw or "").strip()
    if not text:
        return None
    upper = text.upper()
    if "(NFP)" not in upper and "NOUVEAU FRONT POPULAIRE" not in upper:
        return None
    if "LFI" in upper or "FRANCE INSOUMISE" in upper:
        return "LFI / NFP"
    if "PS" in upper or "PARTI SOCIALISTE" in upper:
        return "PS / NFP"
    if "EELV" in upper or "LÉ" in upper or "LES ÉCOLOGISTES" in text or "LES ECOLOGISTES" in upper:
        return "EELV / NFP"
    if "PCF" in upper or "PARTI COMMUNISTE" in upper:
        return "PCF / NFP"
    if "NPA" in upper:
        return "NPA / NFP"
    return "Autre NFP"


def fetch_wikipedia_title(query: str) -> str | None:
    response = requests.get(
        WIKIPEDIA_API_URL,
        params={
            "action": "query",
            "list": "search",
            "srsearch": query,
            "format": "json",
        },
        headers={"User-Agent": USER_AGENT},
        timeout=30,
    )
    response.raise_for_status()
    payload = response.json()
    for result in payload.get("query", {}).get("search", []):
        title = str(result.get("title") or "")
        if title.startswith("Élections législatives de 2024"):
            return title
    return None


def fetch_html_for_title(title: str) -> str:
    url = f"https://fr.wikipedia.org/wiki/{quote(title.replace(' ', '_'))}"
    response = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=30)
    response.raise_for_status()
    return response.text


def extract_candidate_tables(html: str) -> list[pd.DataFrame]:
    tables = pd.read_html(StringIO(html))
    extracted: list[pd.DataFrame] = []
    for table in tables:
        flat_columns = []
        for column in table.columns:
            if isinstance(column, tuple):
                flat_columns.append(" | ".join(str(part) for part in column if str(part) != "nan"))
            else:
                flat_columns.append(str(column))
        table = table.copy()
        table.columns = flat_columns
        has_candidate = any("Candidat" in column for column in flat_columns)
        has_party = any("Parti et coalition" in column for column in flat_columns)
        if has_candidate and has_party:
            extracted.append(table)
    return extracted


def find_column(columns: list[str], needle: str) -> str | None:
    for column in columns:
        if needle in column:
            return column
    return None


def infer_department_page_query(label: str) -> str:
    if label == "Paris":
        return "Élections législatives de 2024 à Paris"
    return f"Élections législatives de 2024 {label}"


@dataclass
class OfficialCandidate:
    dept_code: str
    circo_key: str
    candidate_key: str
    candidate_name: str
    nuance: str
    share_exprimes: float


def load_official_first_round_candidates() -> pd.DataFrame:
    from presidentielle2027.dashboard.views.analysis_2024_projection_logic import _build_official_2024_circo_force_analysis

    _summary, candidates, _maintained = _build_official_2024_circo_force_analysis()
    if candidates.empty:
        raise RuntimeError("No official first-round candidates available")
    rows = (
        candidates[
            [
                "dept_code",
                "circo_key",
                "candidate_key",
                "candidate_name",
                "nuance",
                "share_exprimes",
            ]
        ]
        .drop_duplicates()
        .copy()
    )
    rows["dept_code"] = rows["dept_code"].astype(str)
    rows["candidate_key"] = rows["candidate_key"].astype(str)
    rows["nuance"] = rows["nuance"].astype(str)
    rows["share_exprimes"] = pd.to_numeric(rows["share_exprimes"], errors="coerce").fillna(0.0)
    return rows


def build_mapping() -> pd.DataFrame:
    official = load_official_first_round_candidates()
    departments = (
        official[["dept_code"]]
        .drop_duplicates()
        .merge(
            official.merge(
                official[["dept_code"]].drop_duplicates(),
                on="dept_code",
                how="inner",
            ),
            on="dept_code",
            how="left",
        )
    )
    # Re-read department labels from general results through the dashboard loader.
    from presidentielle2027.dashboard.views.analysis_2024_projection_logic import _load_official_general_results

    general = _load_official_general_results()
    dept_labels = (
        general.loc[general["id_election"] == "2024_legi_t1", ["code_departement", "libelle_departement"]]
        .drop_duplicates()
        .rename(columns={"code_departement": "dept_code", "libelle_departement": "dept_label"})
    )
    dept_labels["dept_code"] = dept_labels["dept_code"].astype(str)
    todo = dept_labels.sort_values("dept_code").to_dict("records")

    mappings: list[dict[str, object]] = []
    for item in todo:
        dept_code = str(item["dept_code"])
        dept_label = str(item["dept_label"])
        query = infer_department_page_query(dept_label)
        title = fetch_wikipedia_title(query)
        if not title:
            continue
        html = fetch_html_for_title(title)
        tables = extract_candidate_tables(html)
        dept_candidates = official.loc[official["dept_code"] == dept_code].copy()
        if dept_candidates.empty:
            continue
        for table in tables:
            candidate_col = find_column(list(table.columns), "Candidat.1") or find_column(list(table.columns), "Candidat")
            party_col = find_column(list(table.columns), "Parti et coalition")
            score_col = find_column(list(table.columns), "Premier tour | %") or find_column(list(table.columns), "Premier tour")
            if not candidate_col or not party_col:
                continue
            working = table[[candidate_col, party_col] + ([score_col] if score_col else [])].copy()
            working = working.dropna(subset=[candidate_col, party_col])
            for row in working.to_dict("records"):
                internal_party = normalize_party_label(row.get(party_col))
                if not internal_party:
                    continue
                candidate_name = str(row.get(candidate_col) or "").strip()
                if not candidate_name:
                    continue
                parts = candidate_name.split()
                candidate_key = normalize_person_key(" ".join(parts[:-1]), parts[-1]) if len(parts) > 1 else candidate_name.upper()
                matches = dept_candidates.loc[dept_candidates["candidate_key"] == candidate_key].copy()
                if matches.empty:
                    continue
                if len(matches) > 1 and score_col:
                    raw_score = str(row.get(score_col) or "").replace("%", "").replace("\xa0", "").replace(",", ".").strip()
                    try:
                        score_value = float(raw_score)
                    except ValueError:
                        score_value = None
                    if score_value is not None:
                        matches["score_gap"] = (matches["share_exprimes"] - score_value).abs()
                        matches = matches.sort_values("score_gap", ascending=True).head(1)
                    else:
                        matches = matches.sort_values("share_exprimes", ascending=False).head(1)
                else:
                    matches = matches.head(1)
                match = matches.iloc[0]
                mappings.append(
                    {
                        "circo_key": str(match["circo_key"]),
                        "candidate_key": str(match["candidate_key"]),
                        "candidate_name": str(match["candidate_name"]),
                        "dept_code": dept_code,
                        "dept_label": dept_label,
                        "wikipedia_title": title,
                        "nfp_internal_party": internal_party,
                        "party_label_raw": str(row.get(party_col) or ""),
                    }
                )
    frame = pd.DataFrame(mappings).drop_duplicates(subset=["circo_key", "candidate_key"])
    return frame


def main() -> None:
    frame = build_mapping()
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(OUTPUT_PATH, index=False, sep=";")
    print({"rows": len(frame), "path": str(OUTPUT_PATH)})
    if not frame.empty:
        print(frame["nfp_internal_party"].value_counts(dropna=False).to_dict())


if __name__ == "__main__":
    main()
