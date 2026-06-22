"""Shared test fixtures. A throwaway SQLite DB is configured before the app is
imported; tables are recreated fresh per test for isolation."""
from __future__ import annotations

import os
import tempfile

# Configure env BEFORE importing app modules (settings + engine read it once).
_TMP = tempfile.mkdtemp(prefix="prhealth-test-")
os.environ.setdefault("DATABASE_URL", f"sqlite:///{_TMP}/test.db")
os.environ.setdefault("FASTAPI_AUTH_TOKEN", "test-token")
os.environ.setdefault("LLM_ENABLED", "false")
os.environ.setdefault("WRITEBACK_ENABLED", "false")

import pytest  # noqa: E402

from app.persistence.db import get_engine, get_session_factory  # noqa: E402
from app.persistence.orm import Base  # noqa: E402
from app.persistence.repository import Repository  # noqa: E402

AUTH_TOKEN = os.environ["FASTAPI_AUTH_TOKEN"]


@pytest.fixture(autouse=True)
def fresh_db():
    engine = get_engine()
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield


@pytest.fixture
def session():
    s = get_session_factory()()
    try:
        yield s
    finally:
        s.close()


@pytest.fixture
def repository(session):
    return Repository(session)


@pytest.fixture
def client():
    from fastapi.testclient import TestClient

    from app.main import app

    return TestClient(app)


@pytest.fixture
def auth_headers():
    return {"Authorization": f"Bearer {AUTH_TOKEN}"}
