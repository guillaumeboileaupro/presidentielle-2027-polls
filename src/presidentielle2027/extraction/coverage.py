from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from presidentielle2027.extraction.canonicalization import CANDIDATE_ALIASES, canonicalize_candidate_fields
from presidentielle2027.extraction.normalizer import normalize_csv_file
from presidentielle2027.extraction.validators import NormalizedPollRecord


@dataclass(frozen=True)
class PollCoverageRow:
    poll_id: str
    scenario_name: str
    round: str
    actual_candidate_count: int
    expected_candidate_count: int
    missing_candidates: tuple[str, ...]
    duplicate_candidates: tuple[str, ...]
    candidates_missing_party: tuple[str, ...]
    candidates_missing_family: tuple[str, ...]
    coverage_ok: bool


def _candidate_mentions_from_text(raw_text: str | None) -> set[str]:
    if not raw_text:
        return set()

    normalized_text = raw_text.casefold()
    mentions: set[str] = set()
    for alias in sorted(CANDIDATE_ALIASES, key=len, reverse=True):
        if alias.casefold() not in normalized_text:
            continue
        canonical_name, _, _ = canonicalize_candidate_fields(alias)
        if canonical_name:
            mentions.add(canonical_name)
    return mentions


def build_poll_coverage_report(records: list[NormalizedPollRecord]) -> list[PollCoverageRow]:
    grouped: dict[tuple[str, str, str], list[NormalizedPollRecord]] = defaultdict(list)
    for record in records:
        grouped[(record.poll_id, record.scenario_name, record.round)].append(record)

    report: list[PollCoverageRow] = []
    for (poll_id, scenario_name, round_name), scenario_records in grouped.items():
        actual_candidates = [record.candidate_name for record in scenario_records]
        unique_candidates = set(actual_candidates)
        expected_candidates: set[str] = set()
        for record in scenario_records:
            expected_candidates.update(_candidate_mentions_from_text(record.raw_text_context))

        duplicates = sorted({name for name in unique_candidates if actual_candidates.count(name) > 1})
        missing_candidates = sorted(expected_candidates - unique_candidates)
        missing_party = sorted({record.candidate_name for record in scenario_records if not record.candidate_party})
        missing_family = sorted({record.candidate_name for record in scenario_records if not record.political_family})

        report.append(
            PollCoverageRow(
                poll_id=poll_id,
                scenario_name=scenario_name,
                round=round_name,
                actual_candidate_count=len(unique_candidates),
                expected_candidate_count=len(expected_candidates),
                missing_candidates=tuple(missing_candidates),
                duplicate_candidates=tuple(duplicates),
                candidates_missing_party=tuple(missing_party),
                candidates_missing_family=tuple(missing_family),
                coverage_ok=not missing_candidates and not duplicates,
            )
        )

    return sorted(report, key=lambda row: (row.coverage_ok, row.poll_id, row.scenario_name))


def coverage_report_to_dataframe(report: list[PollCoverageRow]) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "poll_id": row.poll_id,
                "scenario_name": row.scenario_name,
                "round": row.round,
                "actual_candidate_count": row.actual_candidate_count,
                "expected_candidate_count": row.expected_candidate_count,
                "missing_candidates": "; ".join(row.missing_candidates),
                "duplicate_candidates": "; ".join(row.duplicate_candidates),
                "candidates_missing_party": "; ".join(row.candidates_missing_party),
                "candidates_missing_family": "; ".join(row.candidates_missing_family),
                "coverage_ok": row.coverage_ok,
            }
            for row in report
        ]
    )


def build_coverage_report_from_csv(csv_path: Path) -> pd.DataFrame:
    records = normalize_csv_file(csv_path)
    return coverage_report_to_dataframe(build_poll_coverage_report(records))
