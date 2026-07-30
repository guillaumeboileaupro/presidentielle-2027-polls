import pandas as pd

from presidentielle2027.extraction.migration import (
    NORMALIZATION_VERSION,
    canonicalize_normalized_frame,
)


def test_migration_is_idempotent_and_removes_forbidden_categories() -> None:
    frame = pd.DataFrame(
        {
            "candidate_name": [
                "Marine Tondelier",
                "Raphaël Glucksmann",
                "Édouard Philippe",
            ],
            "candidate_party": ["LE", "PS-PP", "EPR"],
            "political_family": ["greens", "centre_left", "centre"],
        }
    )
    migrated = canonicalize_normalized_frame(frame)
    migrated_twice = canonicalize_normalized_frame(migrated)

    assert migrated.equals(migrated_twice)
    assert migrated["candidate_party"].tolist() == ["EELV", "PP", "HOR"]
    assert migrated["political_family"].tolist() == [
        "écologistes",
        "centre_gauche",
        "centre",
    ]
    assert migrated["normalization_version"].eq(NORMALIZATION_VERSION).all()
