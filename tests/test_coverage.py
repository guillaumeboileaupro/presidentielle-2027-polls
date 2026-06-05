from __future__ import annotations

from pathlib import Path

import pandas as pd

from presidentielle2027.extraction.coverage import build_coverage_report_from_csv


def test_build_coverage_report_from_csv_detects_missing_candidate(tmp_path: Path) -> None:
    csv_path = tmp_path / "coverage.csv"
    frame = pd.DataFrame(
        [
            {
                "poll_id": "poll-1",
                "source_url": "https://example.org/poll-1",
                "source_name": "test",
                "polling_company": "Ifop",
                "commissioner": None,
                "media_partner": None,
                "fieldwork_start_date": "2026-05-01",
                "fieldwork_end_date": "2026-05-02",
                "publication_date": "2026-05-03",
                "sample_size": 1000,
                "population": "registered_voters",
                "collection_method": "online",
                "quota_method": "true",
                "round": "first_round",
                "scenario_name": "Scenario test",
                "candidate_name": "Jordan Bardella",
                "candidate_party": "RN",
                "political_family": "droite_nationale",
                "estimate_percent": 35.0,
                "lower_bound_percent": None,
                "upper_bound_percent": None,
                "margin_of_error": None,
                "undecided_percent": None,
                "abstention_estimate": None,
                "registered_voters_basis": True,
                "raw_text_context": "Jordan Bardella 35; Édouard Philippe 18",
                "extraction_confidence": 0.9,
            }
        ]
    )
    frame.to_csv(csv_path, index=False)

    report = build_coverage_report_from_csv(csv_path)

    assert len(report) == 1
    assert bool(report.loc[0, "coverage_ok"]) is False
    assert report.loc[0, "missing_candidates"] == "Édouard Philippe"
