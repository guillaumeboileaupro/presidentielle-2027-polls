import pandas as pd

from presidentielle2027.analytics.polling_average import compute_weighted_polling_averages


def test_compute_weighted_polling_averages() -> None:
    frame = pd.DataFrame(
        [
            {
                "poll_id": "a",
                "publication_date": "2026-01-10",
                "sample_size": 1000,
                "round": "first_round",
                "scenario_name": "Scenario A",
                "candidate_name": "Alex Martin",
                "estimate_percent": 20.0,
            },
            {
                "poll_id": "b",
                "publication_date": "2026-01-12",
                "sample_size": 1600,
                "round": "first_round",
                "scenario_name": "Scenario A",
                "candidate_name": "Alex Martin",
                "estimate_percent": 24.0,
            },
        ]
    )
    averages = compute_weighted_polling_averages(frame, reference_date=pd.Timestamp("2026-01-15").date())
    assert len(averages) == 1
    assert 20.0 < averages.loc[0, "weighted_average"] < 24.0

