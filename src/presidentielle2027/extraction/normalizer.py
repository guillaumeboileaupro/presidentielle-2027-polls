from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from presidentielle2027.db.models import Candidate, Poll, PollResult, PollScenario, PollingCompany, Source
from presidentielle2027.extraction.canonicalization import canonicalize_candidate_fields
from presidentielle2027.extraction.table_parser import clean_table
from presidentielle2027.extraction.validators import NormalizedPollRecord


def _parse_date(value: Any) -> datetime | None:
    if value is None or value == "" or pd.isna(value):
        return None
    return pd.to_datetime(value, errors="coerce").to_pydatetime() if pd.notna(pd.to_datetime(value, errors="coerce")) else None


def _parse_bool(value: Any) -> bool | None:
    if value is None or value == "" or pd.isna(value):
        return None
    normalized = str(value).strip().lower()
    if normalized in {"true", "1", "yes", "y", "registered_voters", "registered"}:
        return True
    if normalized in {"false", "0", "no", "n"}:
        return False
    return None


def _parse_quota_method(value: Any) -> str:
    parsed = _parse_bool(value)
    if parsed is None:
        return "unknown"
    return "true" if parsed else "false"


def _parse_float(value: Any) -> float | None:
    if value is None or value == "" or pd.isna(value):
        return None
    text = str(value).replace("%", "").replace(",", ".").strip()
    try:
        return float(text)
    except ValueError:
        return None


def _parse_int(value: Any) -> int | None:
    number = _parse_float(value)
    return int(number) if number is not None else None


def _none_if_na(value: Any) -> Any:
    if value is None or value == "" or pd.isna(value):
        return None
    return value


def normalize_row(row: dict[str, Any]) -> NormalizedPollRecord:
    candidate_name, candidate_party, political_family = canonicalize_candidate_fields(
        row["candidate_name"],
        _none_if_na(row.get("candidate_party")),
        _none_if_na(row.get("political_family")),
    )
    payload = {
        "poll_id": row["poll_id"],
        "source_url": row["source_url"],
        "source_name": row["source_name"],
        "polling_company": row["polling_company"],
        "commissioner": _none_if_na(row.get("commissioner")),
        "media_partner": _none_if_na(row.get("media_partner")),
        "fieldwork_start_date": _parse_date(row.get("fieldwork_start_date")),
        "fieldwork_end_date": _parse_date(row.get("fieldwork_end_date")),
        "publication_date": _parse_date(row.get("publication_date")),
        "sample_size": _parse_int(row.get("sample_size")),
        "population": _none_if_na(row.get("population")),
        "collection_method": _none_if_na(row.get("collection_method", "unknown")) or "unknown",
        "quota_method": _parse_quota_method(row.get("quota_method", "unknown")),
        "round": row["round"],
        "scenario_name": row["scenario_name"],
        "candidate_name": candidate_name,
        "candidate_party": candidate_party,
        "political_family": political_family,
        "estimate_percent": _parse_float(row.get("estimate_percent")) or 0.0,
        "lower_bound_percent": _parse_float(row.get("lower_bound_percent")),
        "upper_bound_percent": _parse_float(row.get("upper_bound_percent")),
        "margin_of_error": _parse_float(row.get("margin_of_error")),
        "undecided_percent": _parse_float(row.get("undecided_percent")),
        "abstention_estimate": _parse_float(row.get("abstention_estimate")),
        "registered_voters_basis": _parse_bool(row.get("registered_voters_basis")),
        "raw_text_context": _none_if_na(row.get("raw_text_context")),
        "extraction_confidence": _parse_float(row.get("extraction_confidence")) or 0.0,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }
    return NormalizedPollRecord.model_validate(payload)


def normalize_dataframe(frame: pd.DataFrame) -> list[NormalizedPollRecord]:
    cleaned = clean_table(frame)
    return [normalize_row(record) for record in cleaned.to_dict(orient="records")]


def normalize_csv_file(csv_path: Path) -> list[NormalizedPollRecord]:
    frame = pd.read_csv(csv_path)
    return normalize_dataframe(frame)


def _get_or_create_source(session: Session, record: NormalizedPollRecord) -> Source:
    source = session.scalar(select(Source).where(Source.source_url == str(record.source_url)))
    if source is None:
        source = Source(source_name=record.source_name, source_url=str(record.source_url), source_type="dataset")
        session.add(source)
        session.flush()
    return source


def _get_or_create_polling_company(session: Session, record: NormalizedPollRecord) -> PollingCompany:
    company = session.scalar(select(PollingCompany).where(PollingCompany.name == record.polling_company))
    if company is None:
        company = PollingCompany(name=record.polling_company)
        session.add(company)
        session.flush()
    return company


def _get_or_create_candidate(session: Session, record: NormalizedPollRecord) -> Candidate:
    candidate = session.scalar(
        select(Candidate).where(
            Candidate.candidate_name == record.candidate_name,
            Candidate.candidate_party == record.candidate_party,
        )
    )
    if candidate is None:
        candidate = Candidate(
            candidate_name=record.candidate_name,
            candidate_party=record.candidate_party,
            political_family=record.political_family,
        )
        session.add(candidate)
        session.flush()
    return candidate


def normalize_to_database(records: Iterable[NormalizedPollRecord], session: Session) -> int:
    persisted_rows = 0
    poll_cache: dict[str, Poll] = {}
    scenario_cache: dict[tuple[str, str], PollScenario] = {}

    for record in records:
        source = _get_or_create_source(session, record)
        company = _get_or_create_polling_company(session, record)
        poll = poll_cache.get(record.poll_id) or session.scalar(select(Poll).where(Poll.poll_id == record.poll_id))
        if poll is None:
            poll = Poll(
                poll_id=record.poll_id,
                source_id=source.id,
                polling_company_id=company.id,
                commissioner=record.commissioner,
                media_partner=record.media_partner,
                fieldwork_start_date=record.fieldwork_start_date,
                fieldwork_end_date=record.fieldwork_end_date,
                publication_date=record.publication_date,
                sample_size=record.sample_size,
                population=record.population,
                collection_method=record.collection_method,
                quota_method=record.quota_method,
                round=record.round,
                undecided_percent=record.undecided_percent,
                abstention_estimate=record.abstention_estimate,
                registered_voters_basis=record.registered_voters_basis,
                raw_text_context=record.raw_text_context,
                extraction_confidence=record.extraction_confidence,
            )
            session.add(poll)
            session.flush()
        poll_cache[record.poll_id] = poll

        scenario_key = (record.poll_id, record.scenario_name)
        scenario = scenario_cache.get(scenario_key) or session.scalar(
            select(PollScenario).where(
                PollScenario.poll_id == poll.id,
                PollScenario.scenario_name == record.scenario_name,
            )
        )
        if scenario is None:
            scenario = PollScenario(poll_id=poll.id, scenario_name=record.scenario_name, round=record.round)
            session.add(scenario)
            session.flush()
        scenario_cache[scenario_key] = scenario

        candidate = _get_or_create_candidate(session, record)
        existing = session.scalar(
            select(PollResult).where(
                PollResult.scenario_id == scenario.id,
                PollResult.candidate_id == candidate.id,
            )
        )
        if existing is None:
            existing = PollResult(
                scenario_id=scenario.id,
                candidate_id=candidate.id,
                estimate_percent=record.estimate_percent,
                lower_bound_percent=record.lower_bound_percent,
                upper_bound_percent=record.upper_bound_percent,
                margin_of_error=record.margin_of_error,
            )
            session.add(existing)
            persisted_rows += 1
    session.commit()
    return persisted_rows
