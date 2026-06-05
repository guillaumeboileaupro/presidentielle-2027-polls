from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from presidentielle2027.config import get_settings

_ENGINE_CACHE: dict[str, Engine] = {}
_SESSIONMAKER_CACHE: dict[str, sessionmaker[Session]] = {}


def get_engine(database_url: str | None = None) -> Engine:
    url = database_url or get_settings().database_url
    if url not in _ENGINE_CACHE:
        _ENGINE_CACHE[url] = create_engine(url, future=True)
    return _ENGINE_CACHE[url]


def get_session_factory(database_url: str | None = None) -> sessionmaker[Session]:
    url = database_url or get_settings().database_url
    if url not in _SESSIONMAKER_CACHE:
        _SESSIONMAKER_CACHE[url] = sessionmaker(bind=get_engine(url), autoflush=False, future=True)
    return _SESSIONMAKER_CACHE[url]


def get_session(database_url: str | None = None) -> Iterator[Session]:
    session = get_session_factory(database_url)()
    try:
        yield session
    finally:
        session.close()

