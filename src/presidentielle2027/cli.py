from __future__ import annotations

from pathlib import Path
from typing import Annotated
import subprocess
import sys

import pandas as pd
import typer
from streamlit.web.bootstrap import run

from presidentielle2027.analytics.polling_average import compute_weighted_polling_averages, load_results_dataframe
from presidentielle2027.config import get_settings
from presidentielle2027.db.init_db import init_database
from presidentielle2027.db.session import get_engine, get_session_factory
from presidentielle2027.extraction.coverage import build_coverage_report_from_csv
from presidentielle2027.extraction.excel_parser import workbook_to_normalized_dataframe
from presidentielle2027.extraction.normalizer import normalize_csv_file, normalize_to_database
from presidentielle2027.ingestion.pdf_collector import download_pdf
from presidentielle2027.ingestion.wikipedia_scraper import ingest_wikipedia_sources

app = typer.Typer(help="CLI for polling ingestion, normalization and dashboard operations.")


@app.command("init-db")
def init_db() -> None:
    init_database()
    typer.echo("Database initialized.")


@app.command("ingest-wikipedia")
def ingest_wikipedia() -> None:
    settings = get_settings()
    session = get_session_factory()()
    try:
        artifacts = ingest_wikipedia_sources(session=session, raw_dir=settings.raw_dir)
    finally:
        session.close()
    typer.echo(f"Ingested {len(artifacts)} Wikipedia sources.")


@app.command("ingest-pdf")
def ingest_pdf(url: Annotated[str, typer.Option("--url")]) -> None:
    pdf_path = download_pdf(url)
    typer.echo(f"Downloaded PDF to {pdf_path}")


@app.command("normalize")
def normalize(
    input_csv: Annotated[Path, typer.Option("--input-csv")] = Path("data/processed/sample_polls.csv"),
    input_xlsx: Annotated[Path | None, typer.Option("--input-xlsx")] = None,
) -> None:
    if input_xlsx is not None:
        frame = workbook_to_normalized_dataframe(input_xlsx)
        export_path = get_settings().processed_dir / "wikipedia_2027_polls_normalized.csv"
        export_path.parent.mkdir(parents=True, exist_ok=True)
        frame.to_csv(export_path, index=False)
        records = normalize_csv_file(export_path)
    else:
        records = normalize_csv_file(input_csv)
    session = get_session_factory()()
    try:
        persisted = normalize_to_database(records, session=session)
    finally:
        session.close()
    typer.echo(f"Persisted {persisted} poll result rows.")


@app.command("verify-coverage")
def verify_coverage(
    input_csv: Annotated[Path, typer.Option("--input-csv")] = Path("data/processed/wikipedia_2027_polls_normalized_v2.csv"),
    output_csv: Annotated[Path | None, typer.Option("--output-csv")] = None,
) -> None:
    report = build_coverage_report_from_csv(input_csv)
    if output_csv is not None:
        output_csv.parent.mkdir(parents=True, exist_ok=True)
        report.to_csv(output_csv, index=False)
        typer.echo(f"Coverage report written to {output_csv}")

    failed = report.loc[~report["coverage_ok"]]
    typer.echo(
        f"Coverage check: {len(report) - len(failed)}/{len(report)} scénarios complets, "
        f"{len(failed)} incomplets."
    )
    if not failed.empty:
        preview_columns = ["poll_id", "scenario_name", "missing_candidates", "duplicate_candidates"]
        typer.echo(failed[preview_columns].head(20).to_string(index=False))


@app.command("compute-averages")
def compute_averages(
    export_path: Annotated[Path, typer.Option("--export-path")] = Path("data/exports/weighted_averages.csv"),
) -> None:
    export_path.parent.mkdir(parents=True, exist_ok=True)
    frame = load_results_dataframe(get_engine())
    averages = compute_weighted_polling_averages(frame, lambda_=get_settings().recency_lambda)
    averages.to_csv(export_path, index=False)
    typer.echo(f"Computed weighted averages at {export_path}")


@app.command("train-adjustment-model")
def train_model(
    training_csv: Annotated[Path, typer.Option("--training-csv")] = Path("data/processed/sample_polls.csv"),
    target_column: Annotated[str, typer.Option("--target-column")] = "observed_bias",
    model_type: Annotated[str, typer.Option("--model-type")] = "ridge",
) -> None:
    try:
        from presidentielle2027.ml.train import train_adjustment_model
    except ModuleNotFoundError as exc:
        missing_name = getattr(exc, "name", "scikit-learn/scipy")
        raise typer.BadParameter(
            "Le module ML n'est pas installé. Réinstalle avec `pip install -e \".[ml,dev]\"` "
            f"pour activer `train-adjustment-model` (dépendance manquante: {missing_name})."
        ) from exc

    frame = pd.read_csv(training_csv)
    if target_column not in frame.columns:
        frame[target_column] = 0.0
    session = get_session_factory()()
    try:
        _, metrics, artifact_path = train_adjustment_model(
            training_frame=frame,
            session=session,
            target_column=target_column,
            model_type=model_type,
        )
    finally:
        session.close()
    typer.echo(f"Model saved to {artifact_path} with metrics {metrics}")


@app.command("run-dashboard")
def run_dashboard() -> None:
    dashboard_path = Path(__file__).parent / "dashboard" / "app.py"
    run(
        str(dashboard_path),
        False,
        args=[
            "--server.port",
            str(get_settings().dashboard_port),
            "--server.address",
            get_settings().dashboard_host,
        ],
        flag_options={},
    )


@app.command("install-notebook-kernel")
def install_notebook_kernel(
    kernel_name: Annotated[str, typer.Option("--kernel-name")] = "presidentielle2027-polls",
    display_name: Annotated[str, typer.Option("--display-name")] = "Présidentielle 2027 (.venv)",
) -> None:
    subprocess.run(
        [
            sys.executable,
            "-m",
            "ipykernel",
            "install",
            "--user",
            "--name",
            kernel_name,
            "--display-name",
            display_name,
        ],
        check=True,
    )
    typer.echo(f"Installed Jupyter kernel '{display_name}' ({kernel_name}).")


if __name__ == "__main__":
    app()
