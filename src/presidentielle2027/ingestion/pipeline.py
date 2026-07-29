from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import importlib.util
from pathlib import Path
import time
from types import ModuleType

import pandas as pd
from sqlalchemy.orm import Session, sessionmaker

from presidentielle2027.analytics.polling_average import compute_weighted_polling_averages, load_results_dataframe
from presidentielle2027.config import Settings
from presidentielle2027.db.init_db import init_database
from presidentielle2027.db.session import get_engine
from presidentielle2027.extraction.coverage import build_coverage_report_from_csv
from presidentielle2027.extraction.excel_parser import (
    raw_wikipedia_2027_tables_to_normalized_dataframe,
    workbook_to_normalized_dataframe,
)
from presidentielle2027.extraction.normalizer import normalize_csv_file, normalize_to_database
from presidentielle2027.ingestion.wikipedia_scraper import ingest_wikipedia_sources


GenerateWikiDatasetsCallable = Callable[[Path, Path], None]


def _load_generate_wiki_datasets() -> GenerateWikiDatasetsCallable:
    try:
        from make_wiki_datasets import generate_wiki_datasets as imported_generate_wiki_datasets

        return imported_generate_wiki_datasets
    except ModuleNotFoundError:
        module_path = Path(__file__).resolve().parents[3] / "make_wiki_datasets.py"
        spec = importlib.util.spec_from_file_location("make_wiki_datasets", module_path)
        if spec is None or spec.loader is None:
            raise ModuleNotFoundError(f"Unable to load make_wiki_datasets from {module_path}")
        module = importlib.util.module_from_spec(spec)
        loader = spec.loader
        assert isinstance(module, ModuleType)
        loader.exec_module(module)
        generate_wiki_datasets = getattr(module, "generate_wiki_datasets", None)
        if not callable(generate_wiki_datasets):
            raise AttributeError(f"generate_wiki_datasets not found in {module_path}")
        return generate_wiki_datasets


generate_wiki_datasets = _load_generate_wiki_datasets()


@dataclass(frozen=True)
class PipelineRunSummary:
    normalized_input: Path
    normalized_output: Path
    coverage_output: Path
    averages_output: Path
    persisted_rows: int


def run_refresh_pipeline(
    *,
    settings: Settings,
    session_factory: sessionmaker[Session],
) -> PipelineRunSummary:
    init_database(settings.database_url)

    session = session_factory()
    try:
        ingest_wikipedia_sources(session=session, raw_dir=settings.raw_dir)
    finally:
        session.close()

    generate_wiki_datasets(Path("."), settings.raw_dir / "wikipedia_html")

    normalized_input, normalized_output = _refresh_normalized_dataset(settings)

    session = session_factory()
    try:
        records = normalize_csv_file(normalized_output)
        persisted_rows = normalize_to_database(records, session=session)
    finally:
        session.close()

    coverage_output = settings.exports_dir / "coverage_report.csv"
    coverage_output.parent.mkdir(parents=True, exist_ok=True)
    coverage_report = build_coverage_report_from_csv(normalized_output)
    coverage_report.to_csv(coverage_output, index=False)

    averages_output = settings.exports_dir / "weighted_averages.csv"
    averages_output.parent.mkdir(parents=True, exist_ok=True)
    frame = load_results_dataframe(get_engine(settings.database_url))
    averages = compute_weighted_polling_averages(frame, lambda_=settings.recency_lambda)
    averages.to_csv(averages_output, index=False)

    return PipelineRunSummary(
        normalized_input=normalized_input,
        normalized_output=normalized_output,
        coverage_output=coverage_output,
        averages_output=averages_output,
        persisted_rows=persisted_rows,
    )


def run_periodic_refresh_pipeline(
    *,
    settings: Settings,
    session_factory: sessionmaker[Session],
    interval_minutes: int,
    max_runs: int | None = None,
    sleep_fn: Callable[[float], None] = time.sleep,
) -> int:
    if interval_minutes <= 0:
        raise ValueError("interval_minutes must be strictly positive")
    if max_runs is not None and max_runs <= 0:
        raise ValueError("max_runs must be positive when provided")

    executed_runs = 0
    while max_runs is None or executed_runs < max_runs:
        summary = run_refresh_pipeline(settings=settings, session_factory=session_factory)
        print(
            "[auto-refresh] completed: "
            f"normalized_input={summary.normalized_input}, "
            f"normalized_output={summary.normalized_output}, "
            f"persisted_rows={summary.persisted_rows}, "
            f"coverage_output={summary.coverage_output}, "
            f"averages_output={summary.averages_output}"
        )
        executed_runs += 1
        if max_runs is not None and executed_runs >= max_runs:
            break
        sleep_fn(interval_minutes * 60)
    return executed_runs


def _refresh_normalized_dataset(settings: Settings) -> tuple[Path, Path]:
    processed_dir = settings.processed_dir
    processed_dir.mkdir(parents=True, exist_ok=True)

    v2_xlsx = settings.raw_dir / "presidentielle_2027_sondages_wikipedia_extraction_v2.xlsx"
    v1_xlsx = settings.raw_dir / "presidentielle_2027_sondages_wikipedia_extraction.xlsx"
    normalized_v2_csv = processed_dir / "wikipedia_2027_polls_normalized_v2.csv"
    normalized_csv = processed_dir / "wikipedia_2027_polls_normalized.csv"

    if normalized_v2_csv.exists() and (not v2_xlsx.exists() or normalized_v2_csv.stat().st_mtime >= v2_xlsx.stat().st_mtime):
        frame = pd.read_csv(normalized_v2_csv)
        frame = _merge_with_latest_raw_wikipedia_tables(frame, settings.raw_dir)
        frame.to_csv(normalized_v2_csv, index=False)
        return normalized_v2_csv, normalized_v2_csv
    if v2_xlsx.exists():
        frame = workbook_to_normalized_dataframe(v2_xlsx)
        frame = _merge_with_latest_raw_wikipedia_tables(frame, settings.raw_dir)
        frame.to_csv(normalized_v2_csv, index=False)
        return v2_xlsx, normalized_v2_csv
    if normalized_csv.exists() and (not v1_xlsx.exists() or normalized_csv.stat().st_mtime >= v1_xlsx.stat().st_mtime):
        frame = pd.read_csv(normalized_csv)
        frame = _merge_with_latest_raw_wikipedia_tables(frame, settings.raw_dir)
        frame.to_csv(normalized_csv, index=False)
        return normalized_csv, normalized_csv
    if v1_xlsx.exists():
        frame = workbook_to_normalized_dataframe(v1_xlsx)
        frame = _merge_with_latest_raw_wikipedia_tables(frame, settings.raw_dir)
        frame.to_csv(normalized_csv, index=False)
        return v1_xlsx, normalized_csv

    raise FileNotFoundError(
        "No normalization source available. Expected one of: "
        "data/raw/presidentielle_2027_sondages_wikipedia_extraction_v2.xlsx, "
        "data/raw/presidentielle_2027_sondages_wikipedia_extraction.xlsx, "
        "data/processed/wikipedia_2027_polls_normalized_v2.csv, "
        "data/processed/wikipedia_2027_polls_normalized.csv."
    )


def _merge_with_latest_raw_wikipedia_tables(frame: pd.DataFrame, raw_dir: Path) -> pd.DataFrame:
    raw_frame = raw_wikipedia_2027_tables_to_normalized_dataframe(raw_dir)
    if frame.empty:
        return raw_frame
    if raw_frame.empty:
        return frame

    cleaned_frame = frame.copy()
    if "poll_id" in cleaned_frame.columns:
        raw_poll_mask = cleaned_frame["poll_id"].fillna("").astype(str).str.startswith(("RAW-FR-", "RAW-SR-"))
        superseded_first_round = pd.Series(False, index=cleaned_frame.index)
        if "round" in cleaned_frame.columns and raw_frame["round"].eq("first_round").any():
            legacy_v2_poll = cleaned_frame["poll_id"].fillna("").astype(str).str.startswith(("V2-FR-", "V2-SP-"))
            superseded_first_round = legacy_v2_poll & cleaned_frame["round"].eq("first_round")
            if "source_name" in cleaned_frame.columns:
                superseded_first_round |= cleaned_frame["source_name"].eq("wikipedia_excel_v2") & cleaned_frame[
                    "round"
                ].eq("first_round")
        cleaned_frame = cleaned_frame.loc[~(raw_poll_mask | superseded_first_round)].copy()

    merged = pd.concat([cleaned_frame, raw_frame], ignore_index=True, sort=False)
    merged = merged.drop_duplicates(
        subset=[
            "poll_id",
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
    return merged
