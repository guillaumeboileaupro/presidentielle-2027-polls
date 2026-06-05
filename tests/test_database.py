from pathlib import Path

from sqlalchemy import select

from presidentielle2027.db.init_db import init_database
from presidentielle2027.db.models import Poll, PollResult
from presidentielle2027.db.session import get_session_factory
from presidentielle2027.extraction.normalizer import normalize_csv_file, normalize_to_database


def test_database_roundtrip(tmp_path) -> None:
    database_url = f"sqlite:///{tmp_path / 'test.sqlite3'}"
    init_database(database_url)
    session = get_session_factory(database_url)()
    records = normalize_csv_file(Path("data/processed/sample_polls.csv"))
    try:
        inserted = normalize_to_database(records, session)
        assert inserted > 0
        assert session.scalar(select(Poll).limit(1)) is not None
        assert session.scalar(select(PollResult).limit(1)) is not None
    finally:
        session.close()

