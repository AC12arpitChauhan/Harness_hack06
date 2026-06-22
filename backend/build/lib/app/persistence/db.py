"""Engine + session factory, driven by DATABASE_URL.

Works against both ``sqlite:///./dev.db`` (zero-setup local default) and
``postgresql+psycopg2://...`` with the same models. ``init_db()`` creates all
tables (used by tests and as a dev convenience); Alembic is authoritative for
production migrations.
"""
from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings
from app.persistence.orm import Base

_engine: Engine | None = None
_SessionLocal: sessionmaker[Session] | None = None


def _build_engine(database_url: str) -> Engine:
    connect_args: dict = {}
    if database_url.startswith("sqlite"):
        # FastAPI runs sync handlers across threads; allow cross-thread use.
        connect_args["check_same_thread"] = False
    return create_engine(database_url, connect_args=connect_args, future=True)


def get_engine() -> Engine:
    global _engine
    if _engine is None:
        _engine = _build_engine(get_settings().database_url)
    return _engine


def get_session_factory() -> sessionmaker[Session]:
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(bind=get_engine(), autoflush=False, expire_on_commit=False)
    return _SessionLocal


def init_db() -> None:
    """Create all tables if absent (idempotent)."""
    Base.metadata.create_all(get_engine())


def get_db() -> Iterator[Session]:
    """FastAPI dependency: yields a session and always closes it."""
    session = get_session_factory()()
    try:
        yield session
    finally:
        session.close()
