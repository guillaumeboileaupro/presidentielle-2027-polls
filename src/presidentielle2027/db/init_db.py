from __future__ import annotations

from presidentielle2027.db.models import Base
from presidentielle2027.db.session import get_engine


def init_database(database_url: str | None = None) -> None:
    engine = get_engine(database_url)
    Base.metadata.create_all(engine)

