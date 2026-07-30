from __future__ import annotations

import shutil
from pathlib import Path

import pandas as pd

from presidentielle2027.extraction.canonicalization import canonicalize_candidate_fields

NORMALIZATION_VERSION = 2


def canonicalize_normalized_frame(frame: pd.DataFrame) -> pd.DataFrame:
    """Apply the current idempotent normalization schema to an existing dataset."""
    migrated = frame.copy()
    if migrated.empty:
        migrated["normalization_version"] = NORMALIZATION_VERSION
        return migrated

    canonical = migrated.apply(
        lambda row: canonicalize_candidate_fields(
            row.get("candidate_name"),
            row.get("candidate_party"),
            row.get("political_family"),
        ),
        axis=1,
        result_type="expand",
    )
    canonical.columns = ["candidate_name", "candidate_party", "political_family"]
    migrated[canonical.columns] = canonical
    migrated["normalization_version"] = NORMALIZATION_VERSION
    return migrated


def build_migration_report(before: pd.DataFrame, after: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for column in ("candidate_party", "political_family"):
        before_values = before.get(column, pd.Series(dtype=object))
        after_values = after.get(column, pd.Series(dtype=object))
        labels = sorted(
            set(before_values.dropna().astype(str)) | set(after_values.dropna().astype(str))
        )
        for label in labels:
            rows.append(
                {
                    "column": column,
                    "value": label,
                    "count_before": int(before_values.astype(str).eq(label).sum()),
                    "count_after": int(after_values.astype(str).eq(label).sum()),
                }
            )
    return pd.DataFrame(rows)


def build_percentage_correction_report(frame: pd.DataFrame) -> pd.DataFrame:
    columns = [
        "poll_id",
        "round",
        "scenario_name",
        "polling_company",
        "candidate_name",
        "raw_text_context",
        "estimate_percent_original",
        "estimate_percent_corrected",
        "scenario_total_before",
        "scenario_total_after",
        "percentage_correction_applied",
        "percentage_correction_reason",
        "parse_status",
        "parse_error",
    ]
    available = [column for column in columns if column in frame]
    if not available:
        return pd.DataFrame(columns=columns)
    applied_raw = frame.get(
        "percentage_correction_applied",
        pd.Series(False, index=frame.index),
    )
    applied = applied_raw.astype("boolean").fillna(False)
    reason = frame.get(
        "percentage_correction_reason",
        pd.Series("", index=frame.index),
    ).astype(str)
    parse_status = frame.get(
        "parse_status",
        pd.Series("parsed", index=frame.index),
    ).astype(str)
    report = frame.loc[
        applied | reason.str.contains("ambiguous") | parse_status.ne("parsed"),
        available,
    ].copy()
    return report.reindex(columns=columns)


def migrate_normalized_csv(
    csv_path: Path,
    *,
    report_path: Path | None = None,
    backup: bool = True,
) -> pd.DataFrame:
    """Migrate a processed CSV in place, retaining one pre-v2 backup."""
    before = pd.read_csv(csv_path)
    after = canonicalize_normalized_frame(before)
    if backup:
        backup_path = csv_path.with_suffix(f"{csv_path.suffix}.v1.bak")
        if not backup_path.exists():
            shutil.copy2(csv_path, backup_path)
    after.to_csv(csv_path, index=False)
    if report_path is not None:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        build_migration_report(before, after).to_csv(report_path, index=False)
    return after
