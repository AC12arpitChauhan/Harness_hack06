"""FastAPI application factory.

Boots against ``sqlite:///./dev.db`` with zero setup: ``init_db()`` creates tables
on startup (Alembic remains authoritative for production). Mounts the analyze
router now; the dashboard router is added in Phase D.
"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import analyze, dashboard
from app.config import get_settings
from app.persistence.db import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


def create_app() -> FastAPI:
    app = FastAPI(title="PR Health Analytics", version="0.1.0", lifespan=lifespan)

    # CORS so the browser dashboard (different origin) can call the API.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=get_settings().cors_origins_list,
        allow_credentials=False,  # read-only dashboard; no cookies (wildcard-compatible)
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(analyze.router)
    app.include_router(dashboard.router)

    @app.get("/health", tags=["health"])
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
