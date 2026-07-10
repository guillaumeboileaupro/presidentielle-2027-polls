from __future__ import annotations

from datetime import date
from pathlib import Path
import re

import pandas as pd

from presidentielle2027.extraction.canonicalization import canonicalize_candidate_fields
from presidentielle2027.ingestion.source_registry import get_default_sources
from presidentielle2027.ingestion.wikipedia_scraper import fetch_wikipedia_tables


WIKIPEDIA_SOURCE_NAME = "wikipedia_fr_2027_polls"
WIKIPEDIA_NORMALIZED_FILENAME = "wikipedia_2027_polls_normalized_live.csv"


def _strip_annotations(value: object) -> str:
    return re.sub(r"\[[^\]]+\]", "", str(value or "")).strip()


def _parse_sample_size(value: object) -> int | None:
    text = str(value or "").strip().split("/", 1)[0]
    digits = re.sub(r"[^\d]", "", text)
    return int(digits) if digits else None


def _parse_percent(value: object) -> float | None:
    text = str(value or "").replace("\xa0", " ").strip()
    if not text or text in {"—", "-", "nan", "NaN"}:
        return None
    match = re.search(r"(\d+(?:[.,]\d+)?)", text)
    if not match:
        return None
    parsed = float(match.group(1).replace(",", "."))
    while parsed > 100:
        parsed /= 10.0
    return parsed


def _parse_fieldwork_dates(value: object, fallback_year: int) -> tuple[str | None, str | None]:
    text = str(value or "").replace("–", "-").replace("—", "-").strip()
    months = {
        "janvier": 1,
        "février": 2,
        "fevrier": 2,
        "mars": 3,
        "avril": 4,
        "mai": 5,
        "juin": 6,
        "juillet": 7,
        "août": 8,
        "aout": 8,
        "septembre": 9,
        "octobre": 10,
        "novembre": 11,
        "décembre": 12,
        "decembre": 12,
    }
    year_match = re.search(r"(20\d{2})", text)
    year = int(year_match.group(1)) if year_match else fallback_year
    match = re.search(
        r"(\d{1,2})-(\d{1,2})\s+([A-Za-zéûôîàç]+)(?:\s+20\d{2})?",
        text,
        flags=re.IGNORECASE,
    )
    if match:
        start_day, end_day, month_name = match.groups()
        month = months.get(month_name.lower())
        if month is not None:
            return (
                pd.Timestamp(year=year, month=month, day=int(start_day)).date().isoformat(),
                pd.Timestamp(year=year, month=month, day=int(end_day)).date().isoformat(),
            )
    match = re.search(
        r"(\d{1,2})\s+([A-Za-zéûôîàç]+)(?:\s+20\d{2})?",
        text,
        flags=re.IGNORECASE,
    )
    if match:
        day, month_name = match.groups()
        month = months.get(month_name.lower())
        if month is not None:
            parsed = pd.Timestamp(year=year, month=month, day=int(day)).date().isoformat()
            return parsed, parsed
    parsed = pd.to_datetime(text, errors="coerce", dayfirst=True)
    if pd.notna(parsed):
        iso = parsed.date().isoformat()
        return iso, iso
    return None, None


def _candidate_fields(label: object, header_hint: str | None = None) -> tuple[str, str | None, str | None]:
    cleaned = _strip_annotations(label)
    party_hint: str | None = None
    match = re.match(r"^(.*?)\s*\(([^)]+)\)$", cleaned)
    if match:
        cleaned = match.group(1).strip()
        party_hint = match.group(2).strip()
    if header_hint and header_hint.startswith("Candidat "):
        party_hint = header_hint.replace("Candidat ", "").strip()
    return canonicalize_candidate_fields(cleaned, party_hint, None)


def _row_looks_like_poll(pollster: object, date_text: object, sample_size: object) -> bool:
    pollster_text = str(pollster or "").strip()
    return bool(
        pollster_text
        and str(date_text or "").strip()
        and len(pollster_text) <= 40
        and _parse_sample_size(sample_size) is not None
    )


def _normalized_row(
    *,
    poll_id: str,
    source_url: str,
    pollster: str,
    fieldwork_start: str,
    fieldwork_end: str,
    sample_size: int | None,
    round_name: str,
    scenario_name: str,
    candidate_name: str,
    candidate_party: str | None,
    political_family: str | None,
    estimate: float,
    raw_text: str,
) -> dict[str, object]:
    return {
        "poll_id": poll_id,
        "source_url": source_url,
        "source_name": "wikipedia_fr_live",
        "polling_company": pollster,
        "commissioner": None,
        "media_partner": None,
        "fieldwork_start_date": fieldwork_start,
        "fieldwork_end_date": fieldwork_end,
        "publication_date": fieldwork_end,
        "sample_size": sample_size,
        "population": "unknown",
        "collection_method": "unknown",
        "quota_method": "unknown",
        "round": round_name,
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
        "raw_text_context": raw_text,
        "extraction_confidence": 0.6,
    }


def _parse_table(path: Path, source_url: str, fallback_year: int) -> pd.DataFrame:
    frame = pd.read_csv(path, header=None, dtype=str, keep_default_na=False)
    if frame.empty or str(frame.iat[0, 0]).strip() != "Sondeur" or frame.shape[1] < 5:
        return pd.DataFrame()

    table_match = re.search(r"table-(\d+)\.csv$", path.name)
    table_index = table_match.group(1) if table_match else "00"
    rows: list[dict[str, object]] = []

    if frame.shape[1] == 5:
        headers = [_strip_annotations(value) for value in frame.iloc[0, 3:5].tolist()]
        if any(header.startswith("Unnamed:") for header in headers):
            return pd.DataFrame()
        for row_index in range(1, len(frame)):
            pollster, date_text, sample = frame.iloc[row_index, :3].tolist()
            if not _row_looks_like_poll(pollster, date_text, sample):
                continue
            start, end = _parse_fieldwork_dates(date_text, fallback_year)
            if start is None or end is None:
                continue
            scenario = f"{headers[0]} / {headers[1]}"
            for offset, header in enumerate(headers, start=3):
                estimate = _parse_percent(frame.iat[row_index, offset])
                if estimate is None:
                    continue
                candidate, party, family = _candidate_fields(header)
                rows.append(
                    _normalized_row(
                        poll_id=f"LIVE-SR-{table_index}-{row_index:03d}",
                        source_url=source_url,
                        pollster=str(pollster).strip(),
                        fieldwork_start=start,
                        fieldwork_end=end,
                        sample_size=_parse_sample_size(sample),
                        round_name="second_round",
                        scenario_name=scenario,
                        candidate_name=candidate,
                        candidate_party=party,
                        political_family=family,
                        estimate=estimate,
                        raw_text=str(frame.iat[row_index, offset]),
                    )
                )
        return pd.DataFrame(rows)

    headers = [_strip_annotations(value) for value in frame.iloc[1, 3:].tolist()]
    scenario_counters: dict[tuple[str, str], int] = {}
    for row_index in range(2, len(frame)):
        pollster, date_text, sample = frame.iloc[row_index, :3].tolist()
        if not _row_looks_like_poll(pollster, date_text, sample):
            continue
        start, end = _parse_fieldwork_dates(date_text, fallback_year)
        if start is None or end is None:
            continue
        pollster_label = str(pollster).strip()
        key = (pollster_label, str(date_text))
        scenario_counters[key] = scenario_counters.get(key, 0) + 1
        scenario_index = scenario_counters[key]
        scenario = f"{pollster_label} · {date_text} · scénario {scenario_index}"
        for column_index, header in enumerate(headers, start=3):
            cell_text = str(frame.iat[row_index, column_index] or "").strip()
            estimate = _parse_percent(cell_text)
            if estimate is None:
                continue
            generic_header = header.startswith("Candidat ") or header in {"Autre", "Autres"}
            fragment = re.sub(r"^\s*\d+(?:[.,]\d+)?\s*", "", _strip_annotations(cell_text)).strip()
            label = fragment if generic_header and fragment not in {"", "—", "-"} else header
            candidate, party, family = _candidate_fields(label, header if generic_header else None)
            rows.append(
                _normalized_row(
                    poll_id=f"LIVE-FR-{table_index}-{row_index:03d}",
                    source_url=source_url,
                    pollster=pollster_label,
                    fieldwork_start=start,
                    fieldwork_end=end,
                    sample_size=_parse_sample_size(sample),
                    round_name="first_round",
                    scenario_name=scenario,
                    candidate_name=candidate,
                    candidate_party=party,
                    political_family=family,
                    estimate=estimate,
                    raw_text=cell_text,
                )
            )
    return pd.DataFrame(rows)


def refresh_wikipedia_2027_dataset(raw_dir: Path, processed_dir: Path) -> tuple[pd.DataFrame, Path]:
    source = next(source for source in get_default_sources() if source.source_name == WIKIPEDIA_SOURCE_NAME)
    artifact = fetch_wikipedia_tables(source, raw_dir=raw_dir)
    frames = [_parse_table(path, source.source_url, date.today().year) for path in artifact.csv_paths]
    frames = [frame for frame in frames if not frame.empty]
    if not frames:
        raise ValueError("Aucun tableau de sondages 2027 exploitable dans la page Wikipédia fraîchement téléchargée.")

    normalized = pd.concat(frames, ignore_index=True)
    normalized["publication_date"] = pd.to_datetime(normalized["publication_date"], errors="coerce")
    normalized = normalized.loc[normalized["publication_date"].notna()].copy()
    normalized = normalized.loc[normalized["publication_date"].dt.date <= date.today()].copy()
    normalized["publication_date"] = normalized["publication_date"].dt.date.astype(str)
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
    output_path = processed_dir / WIKIPEDIA_NORMALIZED_FILENAME
    output_path.parent.mkdir(parents=True, exist_ok=True)
    normalized.to_csv(output_path, index=False)
    return normalized, output_path
