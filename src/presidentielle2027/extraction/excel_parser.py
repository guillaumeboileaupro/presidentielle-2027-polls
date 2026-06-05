from __future__ import annotations

import re
from pathlib import Path

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


def _parse_fieldwork_dates(value: str) -> tuple[str | None, str | None]:
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
    match = re.search(r"(\d{1,2})-(\d{1,2})\s+([A-Za-zéûôîàç]+)\s+(\d{4})", normalized_value, flags=re.IGNORECASE)
    if match:
        start_day, end_day, month_name, year = match.groups()
        month = month_map.get(month_name.lower())
        if month is not None:
            start = pd.Timestamp(year=int(year), month=month, day=int(start_day)).date().isoformat()
            end = pd.Timestamp(year=int(year), month=month, day=int(end_day)).date().isoformat()
            return start, end
    match = re.search(r"(\d{1,2})\s+([A-Za-zéûôîàç]+)\s+(\d{4})", normalized_value, flags=re.IGNORECASE)
    if match:
        day, month_name, year = match.groups()
        month = month_map.get(month_name.lower())
        if month is not None:
            iso = pd.Timestamp(year=int(year), month=month, day=int(day)).date().isoformat()
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
        fieldwork_start_date, fieldwork_end_date = _parse_fieldwork_dates(str(record.get("fieldwork_dates") or ""))
        publication_date = _extract_publication_date_from_poll_id(str(record.get("poll_id") or ""))

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
        fieldwork_start_date, fieldwork_end_date = _parse_fieldwork_dates(str(record.get("fieldwork_dates") or ""))
        publication_date = _extract_publication_date_from_poll_id(str(record.get("poll_id") or ""))
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
        fieldwork_start_date, fieldwork_end_date = _parse_fieldwork_dates(str(record.get("fieldwork") or ""))
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
        fieldwork_start_date, fieldwork_end_date = _parse_fieldwork_dates(str(record.get("fieldwork") or ""))
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
        fieldwork_start_date, fieldwork_end_date = _parse_fieldwork_dates(str(record.get("fieldwork") or ""))
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
