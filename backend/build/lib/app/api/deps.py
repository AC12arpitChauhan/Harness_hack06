"""FastAPI dependencies: settings, DB-backed Repository, and bearer-token auth.

Auth gates POST routes only (analyze, admin/backfill). Dashboard GETs are open
locally per the spec.
"""
from __future__ import annotations

from collections.abc import Iterator

from fastapi import Depends, Header, HTTPException, status

from app.config import Settings, get_settings
from app.persistence.db import get_db
from app.persistence.repository import Repository
from sqlalchemy.orm import Session


def settings_dep() -> Settings:
    return get_settings()


def repository_dep(session: Session = Depends(get_db)) -> Iterator[Repository]:
    yield Repository(session)


def require_auth(
    authorization: str | None = Header(default=None),
    settings: Settings = Depends(settings_dep),
) -> None:
    """Validate ``Authorization: Bearer <FASTAPI_AUTH_TOKEN>`` on protected routes."""
    expected = settings.fastapi_auth_token
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing bearer token")
    token = authorization.split(" ", 1)[1].strip()
    if token != expected:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid token")
