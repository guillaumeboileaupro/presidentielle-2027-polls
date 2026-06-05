from pathlib import Path

from presidentielle2027.extraction.normalizer import normalize_csv_file


def test_normalize_csv_file() -> None:
    records = normalize_csv_file(Path("data/processed/sample_polls.csv"))
    assert len(records) >= 3
    assert records[0].source_name == "sample_data"
    assert records[0].extraction_confidence == 0

