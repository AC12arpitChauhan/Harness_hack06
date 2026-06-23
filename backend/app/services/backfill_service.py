"""Backfill: pull recent PRs from a repo and run them through the SAME
analyze->score->persist path (NO writeback, NO live trigger). Shared by the
admin endpoint and scripts/backfill.py.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from app.config import Settings
from app.persistence.db import get_session_factory
from app.persistence.repository import Repository
from app.providers.registry import get_provider
from app.services.analysis_service import build_analyzers, build_engine, run_analysis
from app.services.scoring_config import effective_config

logger = logging.getLogger("pr_health.backfill")


def backfill_repo(provider_name: str, repo: str, since_days: int, settings: Settings) -> dict:
    """Analyze every PR created in the last ``since_days``. Each PR runs in its own
    transaction so one failure doesn't abort the batch. Returns a small summary."""
    provider = get_provider(provider_name, settings)
    # Resolve the team's scoring override once for the whole batch.
    cfg_session = get_session_factory()()
    try:
        config = effective_config(settings, Repository(cfg_session))
    finally:
        cfg_session.close()
    analyzers = build_analyzers(settings, config)
    engine = build_engine(settings, config)
    since = datetime.now(timezone.utc) - timedelta(days=since_days)
    repo_url = f"https://github.com/{repo}" if provider_name == "github" else ""
    analyzed = failed = 0
    refs = []
    try:
        refs = provider.list_pull_requests(repo, since)
        for ref in refs:
            session = get_session_factory()()
            try:
                run_analysis(
                    repo,
                    ref.number,
                    provider=provider,
                    repository=Repository(session),
                    analyzers=analyzers,
                    engine=engine,
                    repo_url=repo_url,
                )
                analyzed += 1
            except Exception:
                failed += 1
                logger.exception("backfill: failed on %s#%s", repo, ref.number)
            finally:
                session.close()
    finally:
        close = getattr(provider, "close", None)
        if callable(close):
            close()

    summary = {"provider": provider_name, "repo": repo, "found": len(refs), "analyzed": analyzed, "failed": failed}
    logger.info("backfill complete: %s", summary)
    return summary
