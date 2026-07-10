from __future__ import annotations

from datetime import date
import re
from pathlib import Path
from typing import Iterable

from openpyxl import load_workbook
import pandas as pd

from presidentielle2027.extraction.canonicalization import canonicalize_candidate_fields, is_generic_bloc_label


def load_workbook_sheets(workbook_path: Path) -> dict[str, pd.DataFrame]:
    workbook = load_workbook(workbook_path, read_only=True, data_only=True)
    sheets: dict[str, pd.DataFrame] = {}
    for sheet_name in workbook.sheetnames:
        sheet = workbook[sheet_name]
        values = list(sheet.iter_rows(values_only=True))
        if not values:
            sheets[sheet_name] = pd.DataFrame()
            continue
        header = [str(cell) if cell is not None else "" for cell in values[0]]
        rows = values[1:]
        sheets[sheet_name] = pd.DataFrame(rows, columns=header)
    return sheets


def _parse_fieldwork_dates(value: str, fallback_year: int | None = None) -> tuple[str | None, str | None]:
    if not isinstance(value, str) or not value.strip():
        return None, None
    normalized_value = value.replace("–", "-").replace("—", "-").strip()
    month_map = {
        "janvier": 1, "january": 1,
        "fevrier": 2, "février": 2, "february": 2, "feb": 2,
        "mars": 3, "march": 3, "mar": 3,
        "avril": 4, "april": 4, "apr": 4,
        "mai": 5, "may": 5,
        "juin": 6, "june": 6, "jun": 6,
        "juillet": 7, "july": 7, "jul": 7,
        "aout": 8, "août": 8, "august": 8, "aug": 8,
        "septembre": 9, "september": 9, "sept": 9, "sep": 9,
        "octobre": 10, "october": 10, "oct": 10,
        "novembre": 11, "november": 11, "nov": 11,
        "decembre": 12, "décembre": 12, "december": 12, "dec": 12,
    }
    year_match = re.search(r"(20\d{2})", normalized_value)
    inferred_year = int(year_match.group(1)) if year_match else fallback_year

    match = re.search(r"(\d{1,2})-(\d{1,2})\s+([A-Za-zéûôîàç]+)(?:\s+(20\d{2}))?", normalized_value, flags=re.IGNORECASE)
    if match:
        start_day, end_day, month_name, year = match.groups()
        month = month_map.get(month_name.lower())
        resolved_year = int(year) if year is not None else inferred_year
        if month is not None and resolved_year is not None:
            start = pd.Timestamp(year=int(resolved_year), month=month, day=int(start_day)).date().isoformat()
            end = pd.Timestamp(year=int(resolved_year), month=month, day=int(end_day)).date().isoformat()
            return start, end
    match = re.search(r"(\d{1,2})\s+([A-Za-zéûôîàç]+)(?:\s+(20\d{2}))?", normalized_value, flags=re.IGNORECASE)
    if match:
        day, month_name, year = match.groups()
        month = month_map.get(month_name.lower())
        resolved_year = int(year) if year is not None else inferred_year
        if month is not None and resolved_year is not None:
            iso = pd.Timestamp(year=int(resolved_year), month=month, day=int(day)).date().isoformat()
            return iso, iso
    parsed = pd.to_datetime(normalized_value, errors="coerce", dayfirst=True)
    if pd.notna(parsed):
        iso = parsed.date().isoformat()
        return iso, iso

    return None, None


def _extract_publication_date_from_poll_id(poll_id: str) -> str | None:
    match = re.search(r"(20\d{2})-(\d{2})-(\d{2})", poll_id)
    if not match:
        return None
    year, month, day = match.groups()
    return f"{year}-{month}-{day}"


def _publication_year_from_poll_id(poll_id: object) -> int | None:
    publication_date = _extract_publication_date_from_poll_id(str(poll_id or ""))
    if not publication_date:
        return None
    return int(publication_date[:4])


def _normalize_company_name(name: str) -> str:
    mapping = {
        "Harris": "Harris Interactive",
        "Ifop": "Ifop",
        "Elabe": "Elabe",
        "Odoxa": "Odoxa",
        "Cluster17": "Cluster17",
    }
    return mapping.get(str(name).strip(), str(name).strip())


def _parse_sample_size(value: object) -> int | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if "/" in text:
        text = text.split("/", 1)[0]
    digits = re.sub(r"[^\d]", "", text)
    return int(digits) if digits else None


def _guess_party_and_family(label: str) -> tuple[str | None, str | None, str]:
    text = label.strip()
    if "=" in text:
        party, candidate = [chunk.strip() for chunk in text.split("=", 1)]
        candidate, party, family = canonicalize_candidate_fields(candidate, party, party)
        return party, family, candidate
    family_map = {
        "Arthaud": "far_left",
        "Poutou": "far_left",
        "Roussel": "left",
        "Mélenchon": "left",
        "Melenchon": "left",
        "Tondelier": "greens",
        "Glucksmann": "centre_left",
        "Philippe": "centre",
        "Attal": "centre",
        "Villepin": "gaullist_right",
        "Retailleau": "right",
        "Dupont-Aignan": "sovereigntist_right",
        "Bardella": "nationalist_right",
        "Le Pen": "nationalist_right",
        "Zemmour": "far_right",
        "Autres": "other",
    }
    candidate, party, family = canonicalize_candidate_fields(text, None, family_map.get(text))
    return party, family, candidate


def _tokenize_score_vector(raw_vector: str) -> list[str]:
    return [token.strip() for token in str(raw_vector).replace("–", " - ").replace("—", " - ").split() if token.strip()]


def _clean_candidate_name(name: str) -> str:
    return (
        str(name)
        .replace("Édouard", "Edouard")
        .replace("Éric", "Eric")
        .replace("É", "E")
        .strip()
    )


def _strip_wikipedia_annotations(text: object) -> str:
    return re.sub(r"\[[^\]]+\]", "", str(text or "")).strip()


def _extract_candidate_and_party_from_label(label: str, header_hint: str | None = None) -> tuple[str, str | None, str | None]:
    cleaned = _clean_candidate_name(_strip_wikipedia_annotations(label))
    party_hint = None
    match = re.match(r"^(.*?)\s*\(([^)]+)\)$", cleaned)
    if match:
        cleaned = match.group(1).strip()
        party_hint = match.group(2).strip()
    if header_hint:
        header_hint = header_hint.strip()
        if header_hint.startswith("Candidat "):
            party_hint = header_hint.replace("Candidat ", "").strip()
    candidate_name, candidate_party, political_family = canonicalize_candidate_fields(cleaned, party_hint, None)
    return candidate_name, candidate_party, political_family


def _parse_raw_poll_percent(value: object) -> float | None:
    text = str(value or "").replace("\xa0", " ").strip()
    if not text or text in {"—", "-", "nan", "NaN"}:
        return None
    match = re.search(r"(\d+(?:[.,]\d+)?)", text)
    if not match:
        return None
    try:
        return float(match.group(1).replace(",", "."))
    except ValueError:
        return None

def _correct_poll_units_by_scenario(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return frame.copy()
    corrected = frame.copy()
    numeric = pd.to_numeric(corrected["estimate_percent"], errors="coerce")
    corrected.loc[numeric.notna(), "estimate_percent"] = numeric.loc[numeric.notna()]
    scenario_columns = ["poll_id", "round", "scenario_name"]
    for _, indexes in corrected.groupby(scenario_columns, dropna=False).groups.items():
        indexes = list(indexes)
        values = pd.to_numeric(corrected.loc[indexes, "estimate_percent"], errors="coerce")
        total = values.sum(min_count=1)
        scale = 1.0
        if pd.notna(total):
            while total / scale > 110.0:
                scale *= 10.0
        if scale > 1.0:
            corrected.loc[indexes, "estimate_percent"] = values / scale
    return corrected


def _row_looks_like_poll(pollster: object, date_text: object, sample_size: object) -> bool:
    if _parse_sample_size(sample_size) is None:
        return False
    pollster_text = str(pollster or "").strip()
    date_label = str(date_text or "").strip()
    if not pollster_text or not date_label:
        return False
    if len(pollster_text) > 40 and " " in pollster_text:
        return False
    return True


def _latest_wikipedia_fr_2027_table_files(raw_dir: Path) -> list[Path]:
    pattern = re.compile(r"wikipedia-fr-2027-polls-(\d{8}T\d{6}Z)-table-(\d+)\.csv$")
    grouped: dict[str, list[Path]] = {}
    for path in raw_dir.glob("wikipedia-fr-2027-polls-*-table-*.csv"):
        match = pattern.match(path.name)
        if not match:
            continue
        grouped.setdefault(match.group(1), []).append(path)
    if not grouped:
        return []
    latest_key = sorted(grouped.keys())[-1]
    return sorted(grouped[latest_key], key=lambda path: int(pattern.match(path.name).group(2)))


def _parse_first_round_raw_wikipedia_table(table_path: Path, fallback_year: int) -> pd.DataFrame:
    frame = pd.read_csv(table_path, header=None, dtype=str, keep_default_na=False)
    if frame.shape[1] < 10 or str(frame.iat[0, 0]).strip() != "Sondeur":
        return pd.DataFrame()
    candidate_headers = [_strip_wikipedia_annotations(value) for value in frame.iloc[1, 3:].tolist()]
    rows: list[dict[str, object]] = []
    scenario_counters: dict[tuple[str, str], int] = {}
    table_match = re.search(r"table-(\d+)\.csv$", table_path.name)
    table_index = table_match.group(1) if table_match else "00"
    for row_index in range(4, len(frame)):
        pollster = frame.iat[row_index, 0]
        date_text = frame.iat[row_index, 1]
        sample_size = frame.iat[row_index, 2]
        if not _row_looks_like_poll(pollster, date_text, sample_size):
            continue
        fieldwork_start_date, fieldwork_end_date = _parse_fieldwork_dates(str(date_text), fallback_year=fallback_year)
        if fieldwork_start_date is None and fieldwork_end_date is None:
            continue
        pollster_label = _normalize_company_name(str(pollster))
        key = (pollster_label, str(date_text))
        scenario_counters[key] = scenario_counters.get(key, 0) + 1
        scenario_index = scenario_counters[key]
        scenario_name = f"{pollster_label} · {date_text} · scénario {scenario_index}"
        poll_id = f"RAW-FR-{pollster_label.upper().replace(' ', '-')}-{table_index}-{row_index:03d}"

        for column_index, header_label in enumerate(candidate_headers, start=3):
            cell_text = str(frame.iat[row_index, column_index] or "").strip()
            estimate = _parse_raw_poll_percent(cell_text)
            if estimate is None:
                continue
            generic_header = header_label.startswith("Candidat ") or header_label in {"Autre", "Autres"}
            candidate_fragment = re.sub(r"^\s*\d+(?:[.,]\d+)?\s*", "", _strip_wikipedia_annotations(cell_text)).strip()
            candidate_label = candidate_fragment if generic_header and candidate_fragment and candidate_fragment not in {"—", "-"} else header_label
            candidate_name, candidate_party, political_family = _extract_candidate_and_party_from_label(candidate_label, header_label if generic_header else None)
            rows.append(
                {
                    "poll_id": poll_id,
                    "source_url": "https://fr.wikipedia.org/wiki/Liste_de_sondages_sur_l%27%C3%A9lection_pr%C3%A9sidentielle_fran%C3%A7aise_de_2027",
                    "source_name": "wikipedia_fr_raw_tables",
                    "polling_company": pollster_label,
                    "commissioner": None,
                    "media_partner": None,
                    "fieldwork_start_date": fieldwork_start_date,
                    "fieldwork_end_date": fieldwork_end_date,
                    "publication_date": fieldwork_end_date or fieldwork_start_date,
                    "sample_size": _parse_sample_size(sample_size),
                    "population": "unknown",
                    "collection_method": "unknown",
                    "quota_method": "unknown",
                    "round": "first_round",
                    "scenario_name": scenario_name,
                    "candidate_name": candidate_name,
                    "candidate_party": candidate_party,
                    "political_family": political_family,
                    "estimate_percent": estimate,
                    "lower_bound_percent": None,
                    "upper_bound_percent": None,
                    "margin_of_error": None,
                    "undecided_percent": None,
                    "abstention_estimate": None,
                    "registered_voters_basis": None,
                    "raw_text_context": cell_text,
                    "extraction_confidence": 0.55,
                }
            )
    return pd.DataFrame(rows)


def _parse_second_round_raw_wikipedia_table(table_path: Path, fallback_year: int) -> pd.DataFrame:
    frame = pd.read_csv(table_path, header=None, dtype=str, keep_default_na=False)
    if frame.shape[1] != 5 or str(frame.iat[0, 0]).strip() != "Sondeur":
        return pd.DataFrame()
    candidate_headers = [_strip_wikipedia_annotations(value) for value in frame.iloc[0, 3:5].tolist()]
    if any(str(header).startswith("Unnamed:") for header in candidate_headers):
        return pd.DataFrame()
    rows: list[dict[str, object]] = []
    table_match = re.search(r"table-(\d+)\.csv$", table_path.name)
    table_index = table_match.group(1) if table_match else "00"
    for row_index in range(3, len(frame)):
        pollster = frame.iat[row_index, 0]
        date_text = frame.iat[row_index, 1]
        sample_size = frame.iat[row_index, 2]
        if not _row_looks_like_poll(pollster, date_text, sample_size):
            continue
        fieldwork_start_date, fieldwork_end_date = _parse_fieldwork_dates(str(date_text), fallback_year=fallback_year)
        if fieldwork_start_date is None and fieldwork_end_date is None:
            continue
        pollster_label = _normalize_company_name(str(pollster))
        scenario_name = f"{candidate_headers[0]} / {candidate_headers[1]}"
        poll_id = f"RAW-SR-{pollster_label.upper().replace(' ', '-')}-{table_index}-{row_index:03d}"
        for offset, candidate_label in enumerate(candidate_headers, start=3):
            estimate = _parse_raw_poll_percent(frame.iat[row_index, offset])
            if estimate is None:
                continue
            candidate_name, candidate_party, political_family = _extract_candidate_and_party_from_label(candidate_label)
            rows.append(
                {
                    "poll_id": poll_id,
                    "source_url": "https://fr.wikipedia.org/wiki/Liste_de_sondages_sur_l%27%C3%A9lection_pr%C3%A9sidentielle_fran%C3%A7aise_de_2027",
                    "source_name": "wikipedia_fr_raw_tables",
                    "polling_company": pollster_label,
                    "commissioner": None,
                    "media_partner": None,
                    "fieldwork_start_date": fieldwork_start_date,
                    "fieldwork_end_date": fieldwork_end_date,
                    "publication_date": fieldwork_end_date or fieldwork_start_date,
                    "sample_size": _parse_sample_size(sample_size),
                    "population": "unknown",
                    "collection_method": "unknown",
                    "quota_method": "unknown",
                    "round": "second_round",
                    "scenario_name": scenario_name,
                    "candidate_name": candidate_name,
                    "candidate_party": candidate_party,
                    "political_family": political_family,
                    "estimate_percent": estimate,
                    "lower_bound_percent": None,
                    "upper_bound_percent": None,
                    "margin_of_error": None,
                    "undecided_percent": None,
                    "abstention_estimate": None,
                    "registered_voters_basis": None,
                    "raw_text_context": str(frame.iat[row_index, offset]),
                    "extraction_confidence": 0.65,
                }
            )
    return pd.DataFrame(rows)


def raw_wikipedia_2027_tables_to_normalized_dataframe(raw_dir: Path) -> pd.DataFrame:
    table_files = _latest_wikipedia_fr_2027_table_files(raw_dir)
    if not table_files:
        return pd.DataFrame()
    timestamp_match = re.search(r"wikipedia-fr-2027-polls-(\d{4})", table_files[0].name)
    fallback_year = int(timestamp_match.group(1)) if timestamp_match else None
    frames: list[pd.DataFrame] = []
    for table_path in table_files:
        parsed_first_round = _parse_first_round_raw_wikipedia_table(table_path, fallback_year or 2026)
        if not parsed_first_round.empty:
            frames.append(parsed_first_round)
            continue
        parsed_second_round = _parse_second_round_raw_wikipedia_table(table_path, fallback_year or 2026)
        if not parsed_second_round.empty:
            frames.append(parsed_second_round)
    if not frames:
        return pd.DataFrame()
    normalized = pd.concat(frames, ignore_index=True)
    normalized = _correct_poll_units_by_scenario(normalized)
    normalized = _rewrite_first_round_scenario_names(normalized)
    publication_dates = pd.to_datetime(normalized["publication_date"], errors="coerce")
    normalized = normalized.loc[publication_dates.notna()].copy()
    normalized["_publication_date"] = publication_dates.loc[normalized.index]
    normalized = normalized.loc[normalized["_publication_date"].dt.date <= date.today()].copy()
    normalized = normalized.drop(columns="_publication_date")
    normalized = normalized.drop_duplicates(
        subset=[
            "round",
            "polling_company",
            "fieldwork_start_date",
            "fieldwork_end_date",
            "scenario_name",
            "candidate_name",
            "estimate_percent",
        ],
        keep="last",
    )
    ordered_columns = [
        "poll_id",
        "source_url",
        "source_name",
        "polling_company",
        "commissioner",
        "media_partner",
        "fieldwork_start_date",
        "fieldwork_end_date",
        "publication_date",
        "sample_size",
        "population",
        "collection_method",
        "quota_method",
        "round",
        "scenario_name",
        "candidate_name",
        "candidate_party",
        "political_family",
        "estimate_percent",
        "lower_bound_percent",
        "upper_bound_percent",
        "margin_of_error",
        "undecided_percent",
        "abstention_estimate",
        "registered_voters_basis",
        "raw_text_context",
        "extraction_confidence",
    ]
    return normalized.reindex(columns=ordered_columns)


def _candidate_order_from_sheet(frame: pd.DataFrame) -> list[str]:
    if frame.empty:
        return []
    candidate_column = "candidate" if "candidate" in frame.columns else frame.columns[1]
    return [_clean_candidate_name(candidate) for candidate in frame[candidate_column].dropna().tolist()]


def _scenario_name_from_v2_row(section: str, pollster: str, scenario_index: object) -> str:
    return f"{section} - scenario {scenario_index} - {pollster}"


SCENARIO_PRIORITY = [
    "Édouard Philippe",
    "Gabriel Attal",
    "Marine Le Pen",
    "Jordan Bardella",
    "Jean-Luc Mélenchon",
    "Raphaël Glucksmann",
    "Dominique de Villepin",
    "Bruno Retailleau",
    "François Ruffin",
    "Marine Tondelier",
    "François Bayrou",
    "Olivier Faure",
]


def _sort_candidates_for_label(candidates: set[str]) -> list[str]:
    return sorted(candidates, key=lambda name: (SCENARIO_PRIORITY.index(name) if name in SCENARIO_PRIORITY else 999, name))


def _humanize_second_round_name(name: str) -> str:
    parts = [part.strip() for part in re.split(r"\bvs\b|-", str(name), flags=re.IGNORECASE) if part.strip()]
    if len(parts) >= 2:
        left, _, _ = canonicalize_candidate_fields(parts[0])
        right, _, _ = canonicalize_candidate_fields(parts[1])
        return f"{left} / {right}"
    return str(name)


def _rewrite_first_round_scenario_names(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return frame

    working = frame.copy()
    first_round = working.loc[working["round"] == "first_round"].copy()
    if first_round.empty:
        return working

    bundle_keys = ["polling_company", "fieldwork_start_date", "fieldwork_end_date", "source_url", "round"]
    scenario_sets = (
        first_round.groupby(bundle_keys + ["poll_id", "scenario_name"], dropna=False)["candidate_name"]
        .apply(lambda series: set(str(value) for value in series.dropna().tolist() if not is_generic_bloc_label(value)))
        .reset_index(name="candidate_set")
    )

    renamed: dict[tuple[str, str], str] = {}
    for _, bundle in scenario_sets.groupby(bundle_keys, dropna=False):
        scenario_rows = bundle.to_dict(orient="records")
        scenario_sets_only = [row["candidate_set"] for row in scenario_rows if row["candidate_set"]]
        common_candidates = set.intersection(*scenario_sets_only) if scenario_sets_only else set()
        for row in scenario_rows:
            distinctive = row["candidate_set"] - common_candidates
            if distinctive:
                label_candidates = _sort_candidates_for_label(distinctive)
                label = "Hypothèse " + " / ".join(label_candidates[:3])
            else:
                label_candidates = _sort_candidates_for_label(row["candidate_set"])
                label = "Scénario " + " / ".join(label_candidates[:3]) if label_candidates else "Scénario premier tour"
            renamed[(row["poll_id"], row["scenario_name"])] = label

    working["scenario_name"] = working.apply(
        lambda row: renamed.get((row["poll_id"], row["scenario_name"]), row["scenario_name"])
        if row["round"] == "first_round"
        else _humanize_second_round_name(str(row["scenario_name"])),
        axis=1,
    )
    return working


def parse_first_round_sheet(frame: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for record in frame.to_dict(orient="records"):
        raw_summary = str(record.get("raw_context_or_structured_summary") or "")
        status = str(record.get("status") or "")
        if not raw_summary or "raw_block_needs_parser" in status:
            continue

        scenario_match = re.search(r"Scenario\s+([^:]+):", raw_summary, flags=re.IGNORECASE)
        scenario_name = scenario_match.group(1).strip() if scenario_match else f"Scenario {record.get('poll_id')}"
        after_colon = raw_summary.split(":", 1)[1] if ":" in raw_summary else raw_summary
        publication_date = _extract_publication_date_from_poll_id(str(record.get("poll_id") or ""))
        fieldwork_start_date, fieldwork_end_date = _parse_fieldwork_dates(
            str(record.get("fieldwork_dates") or ""),
            fallback_year=_publication_year_from_poll_id(record.get("poll_id")),
        )

        for chunk in after_colon.split(";"):
            piece = chunk.strip()
            if not piece or "—" in piece:
                continue
            candidate_match = re.match(r"(.+?)\s+(-?\d+(?:[.,]\d+)?)$", piece)
            if not candidate_match:
                continue
            raw_candidate, value = candidate_match.groups()
            candidate_party, political_family, candidate_name = _guess_party_and_family(raw_candidate)
            rows.append(
                {
                    "poll_id": record.get("poll_id"),
                    "source_url": record.get("source_url"),
                    "source_name": "wikipedia_fr_excel_extraction",
                    "polling_company": _normalize_company_name(str(record.get("polling_company") or "")),
                    "commissioner": None,
                    "media_partner": None,
                    "fieldwork_start_date": fieldwork_start_date,
                    "fieldwork_end_date": fieldwork_end_date,
                    "publication_date": publication_date,
                    "sample_size": record.get("sample_size"),
                    "population": "unknown",
                    "collection_method": "unknown",
                    "quota_method": "unknown",
                    "round": "first_round",
                    "scenario_name": scenario_name,
                    "candidate_name": candidate_name,
                    "candidate_party": candidate_party,
                    "political_family": political_family,
                    "estimate_percent": str(value).replace(",", "."),
                    "lower_bound_percent": None,
                    "upper_bound_percent": None,
                    "margin_of_error": None,
                    "undecided_percent": None,
                    "abstention_estimate": None,
                    "registered_voters_basis": None,
                    "raw_text_context": raw_summary,
                    "extraction_confidence": 0.75,
                }
            )
    return pd.DataFrame(rows)


def parse_second_round_sheet(frame: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for record in frame.to_dict(orient="records"):
        publication_date = _extract_publication_date_from_poll_id(str(record.get("poll_id") or ""))
        fieldwork_start_date, fieldwork_end_date = _parse_fieldwork_dates(
            str(record.get("fieldwork_dates") or ""),
            fallback_year=_publication_year_from_poll_id(record.get("poll_id")),
        )
        scenario_name = str(record.get("hypothesis") or f"Second round {record.get('poll_id')}")
        candidates = [
            (record.get("candidate_a"), record.get("candidate_a_percent")),
            (record.get("candidate_b"), record.get("candidate_b_percent")),
        ]
        for candidate_label, estimate in candidates:
            _, political_family, candidate_name = _guess_party_and_family(str(candidate_label))
            rows.append(
                {
                    "poll_id": record.get("poll_id"),
                    "source_url": record.get("source_url"),
                    "source_name": "wikipedia_fr_excel_extraction",
                    "polling_company": _normalize_company_name(str(record.get("polling_company") or "")),
                    "commissioner": None,
                    "media_partner": None,
                    "fieldwork_start_date": fieldwork_start_date,
                    "fieldwork_end_date": fieldwork_end_date,
                    "publication_date": publication_date,
                    "sample_size": record.get("sample_size"),
                    "population": "unknown",
                    "collection_method": "unknown",
                    "quota_method": "unknown",
                    "round": "second_round",
                    "scenario_name": scenario_name,
                    "candidate_name": candidate_name,
                    "candidate_party": None,
                    "political_family": political_family,
                    "estimate_percent": estimate,
                    "lower_bound_percent": None,
                    "upper_bound_percent": None,
                    "margin_of_error": None,
                    "undecided_percent": None,
                    "abstention_estimate": None,
                    "registered_voters_basis": None,
                    "raw_text_context": f"{candidate_name} vs scenario {scenario_name}",
                    "extraction_confidence": 0.9,
                }
            )
    return pd.DataFrame(rows)


def parse_second_round_structured_sheet(frame: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for index, record in enumerate(frame.to_dict(orient="records"), start=1):
        fieldwork_start_date, fieldwork_end_date = _parse_fieldwork_dates(
            str(record.get("fieldwork") or ""),
            fallback_year=_publication_year_from_poll_id(record.get("poll_id")),
        )
        scenario_name = str(record.get("scenario") or f"second_round_{index}")
        poll_id = f"V2-SR-{_normalize_company_name(str(record.get('pollster') or 'unknown')).upper().replace(' ', '-')}-{index:03d}"
        for prefix in ("a", "b"):
            candidate_label = _clean_candidate_name(str(record.get(f"candidate_{prefix}") or ""))
            candidate_party = record.get(f"candidate_{prefix}_party")
            _, political_family, candidate_name = _guess_party_and_family(candidate_label)
            candidate_name, candidate_party, political_family = canonicalize_candidate_fields(
                candidate_name, candidate_party, political_family
            )
            rows.append(
                {
                    "poll_id": poll_id,
                    "source_url": record.get("source_url"),
                    "source_name": "wikipedia_excel_v2",
                    "polling_company": _normalize_company_name(str(record.get("pollster") or "")),
                    "commissioner": None,
                    "media_partner": None,
                    "fieldwork_start_date": fieldwork_start_date,
                    "fieldwork_end_date": fieldwork_end_date,
                    "publication_date": fieldwork_end_date or fieldwork_start_date,
                    "sample_size": _parse_sample_size(record.get("sample_size")),
                    "population": "unknown",
                    "collection_method": "unknown",
                    "quota_method": "unknown",
                    "round": "second_round",
                    "scenario_name": scenario_name,
                    "candidate_name": candidate_name,
                    "candidate_party": candidate_party,
                    "political_family": political_family,
                    "estimate_percent": record.get(f"candidate_{prefix}_score"),
                    "lower_bound_percent": None,
                    "upper_bound_percent": None,
                    "margin_of_error": None,
                    "undecided_percent": None,
                    "abstention_estimate": None,
                    "registered_voters_basis": None,
                    "raw_text_context": f"{scenario_name} / {candidate_name}",
                    "extraction_confidence": 0.9,
                }
            )
    return pd.DataFrame(rows)


def parse_first_round_raw_vectors_sheet(
    frame: pd.DataFrame,
    candidate_order_2025plus: list[str],
    candidate_order_until_2025: list[str],
) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for index, record in enumerate(frame.to_dict(orient="records"), start=1):
        section = str(record.get("source_section") or "first_round")
        order = candidate_order_2025plus if "2025" in section or "March 2025 onwards" in section else candidate_order_until_2025
        tokens = _tokenize_score_vector(str(record.get("scores_raw_vector") or ""))
        fieldwork_start_date, fieldwork_end_date = _parse_fieldwork_dates(
            str(record.get("fieldwork") or ""),
            fallback_year=_publication_year_from_poll_id(record.get("poll_id")),
        )
        poll_id = f"V2-FR-{_normalize_company_name(str(record.get('pollster') or 'unknown')).upper().replace(' ', '-')}-{index:03d}"
        scenario_name = _scenario_name_from_v2_row(section, str(record.get("pollster") or ""), record.get("scenario_index"))
        for candidate_name, token in zip(order, tokens):
            if token == "-":
                continue
            candidate_party, political_family, normalized_candidate = _guess_party_and_family(_clean_candidate_name(candidate_name))
            normalized_candidate, candidate_party, political_family = canonicalize_candidate_fields(
                normalized_candidate, candidate_party, political_family
            )
            rows.append(
                {
                    "poll_id": poll_id,
                    "source_url": record.get("source_url"),
                    "source_name": "wikipedia_excel_v2",
                    "polling_company": _normalize_company_name(str(record.get("pollster") or "")),
                    "commissioner": None,
                    "media_partner": None,
                    "fieldwork_start_date": fieldwork_start_date,
                    "fieldwork_end_date": fieldwork_end_date,
                    "publication_date": fieldwork_end_date or fieldwork_start_date,
                    "sample_size": _parse_sample_size(record.get("sample_size")),
                    "population": "unknown",
                    "collection_method": "unknown",
                    "quota_method": "unknown",
                    "round": "first_round",
                    "scenario_name": scenario_name,
                    "candidate_name": normalized_candidate,
                    "candidate_party": candidate_party,
                    "political_family": political_family,
                    "estimate_percent": token.replace(",", "."),
                    "lower_bound_percent": None,
                    "upper_bound_percent": None,
                    "margin_of_error": None,
                    "undecided_percent": None,
                    "abstention_estimate": None,
                    "registered_voters_basis": None,
                    "raw_text_context": str(record.get("scores_raw_vector") or ""),
                    "extraction_confidence": 0.8,
                }
            )
    return pd.DataFrame(rows)


def parse_scenario_polling_raw_sheet(frame: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for index, record in enumerate(frame.to_dict(orient="records"), start=1):
        order_reference = str(record.get("candidate_order_reference") or "")
        if "Generic" in order_reference:
            order = [chunk.strip() for chunk in order_reference.replace("Generic", "").split("/") if chunk.strip()]
        elif "LePen_runs_candidate_order" in order_reference:
            order = [
                "Arthaud", "Roussel", "Mélenchon", "Glucksmann", "Tondelier", "Attal",
                "Philippe", "Retailleau", "Dupont-Aignan", "Le Pen", "Zemmour"
            ]
        else:
            order = []
        tokens = _tokenize_score_vector(str(record.get("scores_raw_vector") or ""))
        fieldwork_start_date, fieldwork_end_date = _parse_fieldwork_dates(
            str(record.get("fieldwork") or ""),
            fallback_year=_publication_year_from_poll_id(record.get("poll_id")),
        )
        poll_id = f"V2-SP-{_normalize_company_name(str(record.get('pollster') or 'unknown')).upper().replace(' ', '-')}-{index:03d}"
        scenario_name = _scenario_name_from_v2_row(str(record.get("section") or "scenario"), str(record.get("pollster") or ""), record.get("scenario_index"))
        for candidate_name, token in zip(order, tokens):
            if token == "-":
                continue
            candidate_party, political_family, normalized_candidate = _guess_party_and_family(_clean_candidate_name(candidate_name))
            normalized_candidate, candidate_party, political_family = canonicalize_candidate_fields(
                normalized_candidate, candidate_party, political_family
            )
            rows.append(
                {
                    "poll_id": poll_id,
                    "source_url": record.get("source_url"),
                    "source_name": "wikipedia_excel_v2",
                    "polling_company": _normalize_company_name(str(record.get("pollster") or "")),
                    "commissioner": None,
                    "media_partner": None,
                    "fieldwork_start_date": fieldwork_start_date,
                    "fieldwork_end_date": fieldwork_end_date,
                    "publication_date": fieldwork_end_date or fieldwork_start_date,
                    "sample_size": _parse_sample_size(record.get("sample_size")),
                    "population": "unknown",
                    "collection_method": "unknown",
                    "quota_method": "unknown",
                    "round": "first_round",
                    "scenario_name": scenario_name,
                    "candidate_name": normalized_candidate,
                    "candidate_party": candidate_party,
                    "political_family": political_family,
                    "estimate_percent": token.replace(",", "."),
                    "lower_bound_percent": None,
                    "upper_bound_percent": None,
                    "margin_of_error": None,
                    "undecided_percent": None,
                    "abstention_estimate": None,
                    "registered_voters_basis": None,
                    "raw_text_context": str(record.get("scores_raw_vector") or ""),
                    "extraction_confidence": 0.7,
                }
            )
    return pd.DataFrame(rows)


def workbook_to_normalized_dataframe(workbook_path: Path) -> pd.DataFrame:
    sheets = load_workbook_sheets(workbook_path)
    frames: list[pd.DataFrame] = []
    if "first_round_raw_vectors" in sheets or "second_round_structured" in sheets:
        candidate_order_2025plus = _candidate_order_from_sheet(sheets.get("candidate_order_2025plus", pd.DataFrame()))
        candidate_order_until_2025 = _candidate_order_from_sheet(sheets.get("candidate_order_until_2025", pd.DataFrame()))
        if "first_round_raw_vectors" in sheets:
            frames.append(
                parse_first_round_raw_vectors_sheet(
                    sheets["first_round_raw_vectors"],
                    candidate_order_2025plus=candidate_order_2025plus,
                    candidate_order_until_2025=candidate_order_until_2025,
                )
            )
        if "second_round_structured" in sheets:
            frames.append(parse_second_round_structured_sheet(sheets["second_round_structured"]))
        if "scenario_polling_raw" in sheets:
            frames.append(parse_scenario_polling_raw_sheet(sheets["scenario_polling_raw"]))
    else:
        if "first_round" in sheets:
            frames.append(parse_first_round_sheet(sheets["first_round"]))
        if "second_round" in sheets:
            frames.append(parse_second_round_sheet(sheets["second_round"]))
    if not frames:
        return pd.DataFrame()
    normalized = pd.concat(frames, ignore_index=True)
    normalized = _correct_poll_units_by_scenario(normalized)
    normalized = _rewrite_first_round_scenario_names(normalized)
    ordered_columns = [
        "poll_id",
        "source_url",
        "source_name",
        "polling_company",
        "commissioner",
        "media_partner",
        "fieldwork_start_date",
        "fieldwork_end_date",
        "publication_date",
        "sample_size",
        "population",
        "collection_method",
        "quota_method",
        "round",
        "scenario_name",
        "candidate_name",
        "candidate_party",
        "political_family",
        "estimate_percent",
        "lower_bound_percent",
        "upper_bound_percent",
        "margin_of_error",
        "undecided_percent",
        "abstention_estimate",
        "registered_voters_basis",
        "raw_text_context",
        "extraction_confidence",
    ]
    return normalized.reindex(columns=ordered_columns)
