from __future__ import annotations

from pathlib import Path

import pandas as pd

from presidentielle2027.dashboard.views import analysis_2024_projection_logic as logic


def test_official_2024_local_exports_are_loaded_without_download_zip(
    monkeypatch,
    tmp_path: Path,
) -> None:
    circo_path = tmp_path / "official_2024_legislatives_circo_results.csv"
    t2_path = tmp_path / "official_2024_legislatives_t2_candidates.csv"
    pd.DataFrame(
        [
            {
                "Code département": "01",
                "Libellé département": "Ain",
                "Code circonscription législative": "0101",
                "Libellé circonscription législative": "1ère circonscription",
                "Inscrits": 1000,
                "Votants": 700,
                "Abstentions": 300,
                "Exprimés": 680,
            }
        ]
    ).to_csv(circo_path, sep=";", index=False)
    pd.DataFrame(
        [
            {
                "Code département": "01",
                "Département": "Ain",
                "Code circonscription": "0101",
                "Libellé circonscription": "1ère circonscription",
                "Nom du candidat": "DUPONT",
                "Prénom du candidat": "Camille",
                "Code nuance": "ENS",
            }
        ]
    ).to_csv(t2_path, sep=";", index=False)

    monkeypatch.setattr(logic, "OFFICIAL_2024_CIRCO_RESULTS_LOCAL_PATHS", [circo_path])
    monkeypatch.setattr(logic, "OFFICIAL_2024_T2_CANDIDATURES_LOCAL_PATHS", [t2_path])
    monkeypatch.setattr(logic, "OFFICIAL_2024_LEGISLATIVE_ZIP_PATHS", [])
    logic._load_official_circo_results_from_zip.clear()
    logic._load_official_t2_candidatures_from_zip.clear()

    circo = logic._load_official_circo_results_from_zip()
    candidates_t2 = logic._load_official_t2_candidatures_from_zip()

    assert len(circo) == 1
    assert circo.iloc[0]["Libellé département"] == "Ain"
    assert len(candidates_t2) == 1
    assert candidates_t2.iloc[0]["Nom du candidat"] == "DUPONT"
