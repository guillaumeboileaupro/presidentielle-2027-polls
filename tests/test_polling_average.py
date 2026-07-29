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


def test_official_result_is_not_used_as_a_polling_average_input() -> None:
    frame = pd.DataFrame(
        [
            {
                "poll_id": "poll-1",
                "publication_date": "2022-04-01",
                "sample_size": 1000,
                "round": "first_round",
                "scenario_name": "Scénario A",
                "polling_company": "Ifop",
                "candidate_name": "Candidat A",
                "estimate_percent": 20.0,
            },
            {
                "poll_id": "RAW-FR-RÉSULTATS-01",
                "publication_date": "2022-04-10",
                "sample_size": 30_000_000,
                "round": "first_round",
                "scenario_name": "Résultats officiels",
                "polling_company": "Résultats",
                "candidate_name": "Candidat A",
                "estimate_percent": 30.0,
            },
        ]
    )

    averages = compute_weighted_polling_averages(
        frame,
        reference_date=pd.Timestamp("2022-04-10").date(),
    )

    assert averages["weighted_average"].tolist() == [20.0]
    assert averages["poll_count"].tolist() == [1]
