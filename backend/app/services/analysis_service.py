"""The conductor: fetch -> analyze -> score -> persist, in one transaction.

Reads top-to-bottom like a flowchart; the I/O detail lives in the two helpers
below. Collaborators (provider, repository, analyzers, engine) are injected, so
this is trivially unit-testable with a fake provider + a SQLite-backed Repository.
The async narrate + writeback step runs after this returns (see api/routes/analyze).
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone

from app.analyzers.base import Analyzer
from app.analyzers.registry import enabled_analyzers
from app.config import Settings
from app.domain.models import AnalysisContext, Check, Commit, Diff, PullRequest, Review
from app.domain.scores import Score
from app.domain.signals import AnalysisSignal
from app.llm.base import LLMProvider
from app.llm.registry import build_narrator
from app.persistence.db import get_session_factory
from app.persistence.repository import Repository
from app.providers.base import SCMProvider
from app.providers.registry import get_provider
from app.scoring.engine import ScoringEngine
from app.services.scoring_config import default_config
from app.services import slack_service
from app.services.writeback_service import do_writeback

logger = logging.getLogger("pr_health.analysis")


@dataclass
class AnalysisResult:
    repo_id: str
    pr_id: str
    run_id: str
    pull_request: PullRequest
    score: Score
    signals: list[AnalysisSignal]


def build_analyzers(settings: Settings, config: dict | None = None) -> list[Analyzer]:
    """Assemble the enabled analyzers (one place, used by route + backfill).

    ``config`` is an effective scoring config (defaults overlaid with the team
    override); when omitted, the documented defaults apply.
    """
    t = (config or default_config(settings))["thresholds"]
    return enabled_analyzers(
        merge_fast_minutes=int(t["merge_fast_minutes"]),
        merge_slow_minutes=int(t["merge_slow_minutes"]),
        change_medium_lines=int(t["change_medium_lines"]),
        change_high_lines=int(t["change_high_lines"]),
        change_critical_lines=int(t["change_critical_lines"]),
        change_high_files=int(t["change_high_files"]),
        review_trivial_lines=int(t["review_trivial_lines"]),
        review_thin_reviewers=int(t["review_thin_reviewers"]),
    )


def build_engine(settings: Settings, config: dict | None = None) -> ScoringEngine:
    """Build the scoring engine from an effective config (team override or defaults)."""
    c = config or default_config(settings)
    return ScoringEngine(
        health_weights=c["health_weights"],
        risk_weights=c["risk_weights"],
        blocked_cap=settings.blocked_cap,
    )


def run_analysis(
    repo: str,
    pr_number: int,
    *,
    provider: SCMProvider,
    repository: Repository,
    analyzers: list[Analyzer],
    engine: ScoringEngine,
    repo_url: str = "",
) -> AnalysisResult:
    """Fetch PR data, score it deterministically, persist one run, return scores."""
    pr, ctx = _gather(provider, repo, pr_number)
    signals = [sig for analyzer in analyzers for sig in analyzer.analyze(pr, ctx)]
    score = engine.compute(signals)
    repo_id, pr_id, run_id = _persist(repository, provider.name, repo, repo_url, pr, ctx, signals, score)
    return AnalysisResult(repo_id, pr_id, run_id, pr, score, signals)


def _gather(provider: SCMProvider, repo: str, pr_number: int) -> tuple[PullRequest, AnalysisContext]:
    """Fetch everything an analyzer might need, exactly once, up front."""
    pr = provider.get_pull_request(repo, pr_number)
    diff: Diff = provider.get_diff(repo, pr_number)
    reviews: list[Review] = provider.get_reviews(repo, pr_number)
    checks: list[Check] = provider.get_checks(repo, pr.commit_sha) if pr.commit_sha else []
    commits: list[Commit] = provider.get_commits(repo, pr_number)
    return pr, AnalysisContext(diff=diff, reviews=reviews, checks=checks, commits=commits)


def _persist(
    repository: Repository,
    provider_name: str,
    repo: str,
    repo_url: str,
    pr: PullRequest,
    ctx: AnalysisContext,
    signals: list[AnalysisSignal],
    score: Score,
) -> tuple[str, str, str]:
    """Persist repo + PR + diff + reviews + checks + run + signals + score atomically."""
    session = repository.session
    try:
        repo_row = repository.upsert_repository(provider_name, repo, name=repo, url=repo_url)
        pr_row = repository.upsert_pull_request(repo_row.id, pr)
        repository.replace_diff(pr_row.id, ctx.diff)
        repository.replace_reviews(pr_row.id, ctx.reviews)
        repository.replace_checks(pr_row.id, ctx.checks)
        run = repository.create_run(pr_row.id)
        repository.save_signals(run.id, signals)
        repository.save_score(run.id, pr_row.id, score)
        repository.complete_run(run)
        session.commit()
        return repo_row.id, pr_row.id, run.id
    except Exception:
        session.rollback()
        raise


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def post_analysis(
    result: AnalysisResult,
    repo: str,
    *,
    narrator: LLMProvider,
    repository: Repository,
    provider: SCMProvider,
    writeback_enabled: bool,
    ready_threshold: float,
) -> None:
    """Narrate (no score influence) + persist narrative + writeback. Injected deps
    make this unit-testable; run_post_analysis wires the real ones."""
    narrative = narrator.narrate(result.pull_request, result.signals, result.score)
    repository.upsert_narrative(
        result.pr_id,
        result.run_id,
        narrative.summary,
        narrative.recommendation,
        narrative.model,
        posted_at=_now() if writeback_enabled else None,
    )
    repository.session.commit()

    # If CI is failing, enrich the write-back comment with an AI fix suggestion.
    # Best-effort: a failure here must never block the health comment from posting.
    fix_suggestion: str | None = None
    failing = [
        {"name": c.check_name, "status": c.status, "url": c.url}
        for c in repository.checks_for_pr(result.pr_id)
        if (c.status or "").lower() in {"failure", "error"}
    ]
    if failing:
        try:
            fix_suggestion = narrator.suggest_fix(failing, pr_title=result.pull_request.title)
        except Exception:  # pragma: no cover - defensive; never block writeback
            logger.warning(
                "fix-suggestion generation failed for %s#%s; posting without it",
                repo,
                result.pull_request.number,
            )

    do_writeback(
        provider,
        repo,
        result.pull_request,
        result.score,
        narrative,
        enabled=writeback_enabled,
        ready_threshold=ready_threshold,
        fix_suggestion=fix_suggestion,
    )


def _maybe_slack_alert(
    settings: Settings, repository: Repository, provider_name: str, repo: str, result: AnalysisResult
) -> None:
    """Fire a deduped Slack build-failure alert when CI checks failed. Independent of
    narration; a no-op when Slack is not configured. Never raises into the caller."""
    if not settings.slack_enabled:
        return
    try:
        failing = [
            c.check_name
            for c in repository.checks_for_pr(result.pr_id)
            if (c.status or "").lower() in {"failure", "error"}
        ]
        if not failing:
            return
        pr = result.pull_request
        pr_url = (
            f"https://github.com/{repo}/pull/{pr.number}" if provider_name == "github" else None
        )
        fix_url = (
            f"{settings.dashboard_url.rstrip('/')}/repos/{result.repo_id}/prs/{result.pr_id}"
            if settings.dashboard_url
            else None
        )
        slack_service.notify_build_failed(
            settings,
            number=pr.number,
            title=pr.title,
            target=pr.target_branch,
            author=pr.author,
            failing_checks=failing,
            pr_url=pr_url,
            fix_url=fix_url,
            dedupe_key=f"{result.pr_id}:{pr.commit_sha or ''}",
        )
    except Exception:  # pragma: no cover - defensive; alerts must never break the flow
        logger.warning("slack alert failed for %s#%s", repo, result.pull_request.number)


def run_post_analysis(provider_name: str, repo: str, result: AnalysisResult, settings: Settings) -> None:
    """Background entrypoint: builds its own session/provider/narrator and never
    raises into the caller (a narrate/writeback failure must not break the response)."""
    session = get_session_factory()()
    provider = None
    try:
        provider = get_provider(provider_name, settings)
        repository = Repository(session)
        _maybe_slack_alert(settings, repository, provider_name, repo, result)
        post_analysis(
            result,
            repo,
            narrator=build_narrator(settings),
            repository=repository,
            provider=provider,
            writeback_enabled=settings.writeback_enabled,
            ready_threshold=settings.ready_threshold,
        )
    except Exception:  # pragma: no cover - defensive: background must not crash
        logger.exception("post-analysis (narrate/writeback) failed for %s#%s", repo, result.pull_request.number)
    finally:
        session.close()
        close = getattr(provider, "close", None)
        if callable(close):
            close()
