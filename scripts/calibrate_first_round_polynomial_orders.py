from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from presidentielle2027.analytics.trends import build_polynomial_degree_diagnostics
from presidentielle2027.config import get_settings
from presidentielle2027.extraction.canonicalization import canonicalize_candidate_fields, is_generic_bloc_label


OUTPUT_FILENAME = "first_round_polynomial_orders.json"


def _load_base_frame() -> pd.DataFrame:
    settings = get_settings()
    normalized_v2_path = settings.processed_dir / "wikipedia_2027_polls_normalized_v2.csv"
    normalized_path = settings.processed_dir / "wikipedia_2027_polls_normalized.csv"
    sample_path = settings.processed_dir / "sample_polls.csv"

    if normalized_v2_path.exists():
        return pd.read_csv(normalized_v2_path)
    if normalized_path.exists():
        return pd.read_csv(normalized_path)
    return pd.read_csv(sample_path)


def _prepare_frame(frame: pd.DataFrame) -> pd.DataFrame:
    working = frame.copy()
    canonical = working.apply(
        lambda row: canonicalize_candidate_fields(
            row.get("candidate_name"),
            row.get("candidate_party"),
            row.get("political_family"),
        ),
        axis=1,
        result_type="expand",
    )
    canonical.columns = ["candidate_name", "candidate_party", "political_family"]
    working[["candidate_name", "candidate_party", "political_family"]] = canonical
    working["is_generic_bloc"] = working["candidate_name"].map(is_generic_bloc_label)
    working["publication_date"] = pd.to_datetime(working["publication_date"], errors="coerce")
    working["estimate_percent"] = pd.to_numeric(working["estimate_percent"], errors="coerce")
    working = working.loc[(working["round"] == "first_round") & (~working["is_generic_bloc"])].copy()
    return working


def main() -> None:
    settings = get_settings()
    frame = _prepare_frame(_load_base_frame())
    diagnostics = build_polynomial_degree_diagnostics(
        frame=frame,
        group_column="candidate_party",
        value_column="estimate_percent",
        max_degree=9,
    )
    if diagnostics.empty:
        raise SystemExit("Aucun diagnostic polynomial exploitable.")

    best = (
        diagnostics.sort_values(["candidate_party", "penalized_score", "degree"], ascending=[True, True, True])
        .groupby("candidate_party", dropna=False)
        .head(1)
        .copy()
    )
    output_path = settings.processed_dir / OUTPUT_FILENAME
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "orders": {str(row["candidate_party"]): int(row["degree"]) for _, row in best.iterrows()},
        "details": best.sort_values("candidate_party").to_dict(orient="records"),
    }
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Calibration écrite dans {output_path}")


if __name__ == "__main__":
    main()
