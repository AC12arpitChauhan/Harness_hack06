"""Dashboard read endpoints (open locally) + admin backfill (auth required).

All SQL lives in Repository; these handlers only shape ORM rows into DTOs.
"""
from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status

from app.api.deps import repository_dep, require_auth, settings_dep
from app.api.schemas import (
    AuthorStatsOut,
    BackfillAccepted,
    BackfillRequest,
    LLMCheckOut,
    MergeReadinessOut,
    NarrativeOut,
    OverviewOut,
    PRDetail,
    PRListItem,
    RepositoryOut,
    ScoreHistoryOut,
    ScoringConfigOut,
    ScoringConfigUpdate,
    ScoreSummary,
    SignalOut,
    SignalTrendOut,
)
from app.config import Settings
from app.llm.registry import build_narrator
from app.persistence import orm
from app.persistence.repository import Repository
from app.services.backfill_service import backfill_repo
from app.services.scoring_config import (
    effective_config,
    sanitize_thresholds,
    sanitize_weights,
)

router = APIRouter(prefix="/api/v1", tags=["dashboard"])


def _score_summary(row: orm.AnalysisScore | None) -> ScoreSummary | None:
    if row is None:
        return None
    return ScoreSummary(
        health_score=row.health_score,
        risk_score=row.risk_score,
        review_quality_score=row.review_quality_score,
        merge_readiness=row.merge_readiness,
        blocking_reason=row.blocking_reason,
    )


def _signal_out(row: orm.AnalysisSignal) -> SignalOut:
    return SignalOut(
        signal_name=row.signal_name,
        severity=row.severity,
        value=row.value,
        threshold=row.threshold,
        exceeds_threshold=row.exceeds_threshold,
        explanation=row.explanation,
    )


@router.get("/repositories", response_model=list[RepositoryOut])
def list_repositories(repository: Repository = Depends(repository_dep)) -> list[RepositoryOut]:
    out: list[RepositoryOut] = []
    for repo in repository.list_repositories():
        pairs = repository.list_prs_with_latest_score(repo.id, None, "created_at", 1000)
        healths = [s.health_score for _, s in pairs if s is not None]
        avg = round(sum(healths) / len(healths), 2) if healths else None
        out.append(
            RepositoryOut(
                id=repo.id, provider=repo.provider, name=repo.name, url=repo.url,
                pr_count=len(pairs), avg_health_score=avg,
            )
        )
    return out


@router.get("/repositories/{repo_id}/prs", response_model=list[PRListItem])
def list_prs(
    repo_id: str,
    state: str | None = Query(default=None),
    order_by: str = Query(default="created_at"),
    limit: int = Query(default=50, ge=1, le=500),
    repository: Repository = Depends(repository_dep),
) -> list[PRListItem]:
    _require_repo(repository, repo_id)
    pairs = repository.list_prs_with_latest_score(repo_id, state, order_by, limit)
    return [
        PRListItem(
            pr_id=pr.id, provider_pr_id=pr.provider_pr_id, title=pr.title, author=pr.author,
            state=pr.state, merged_at=pr.merged_at, score=_score_summary(score),
        )
        for pr, score in pairs
    ]


@router.get("/repositories/{repo_id}/prs/{pr_id}", response_model=PRDetail)
def pr_detail(
    repo_id: str, pr_id: str, repository: Repository = Depends(repository_dep)
) -> PRDetail:
    _require_repo(repository, repo_id)
    pr = repository.get_pull_request(pr_id)
    if pr is None or pr.repo_id != repo_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "PR not found")
    latest_run = repository.latest_run_for_pr(pr_id)
    signals = repository.signals_for_run(latest_run.id) if latest_run else []
    narrative = repository.narrative_for_pr(pr_id)
    return PRDetail(
        pr_id=pr.id, provider=pr.provider, provider_pr_id=pr.provider_pr_id, title=pr.title,
        author=pr.author, state=pr.state, source_branch=pr.source_branch,
        target_branch=pr.target_branch, jira_issue_id=pr.jira_issue_id,
        score=_score_summary(repository.latest_score_for_pr(pr_id)),
        signals=[_signal_out(s) for s in signals],
        narrative=(
            NarrativeOut(
                ai_summary=narrative.ai_summary, ai_recommendation=narrative.ai_recommendation,
                ai_model=narrative.ai_model, posted_at=narrative.posted_at,
            )
            if narrative
            else None
        ),
    )


@router.get("/repositories/{repo_id}/signal_trends", response_model=SignalTrendOut)
def signal_trends(
    repo_id: str,
    signal_name: str = Query(...),
    period_days: int = Query(default=30, ge=1, le=365),
    repository: Repository = Depends(repository_dep),
) -> SignalTrendOut:
    _require_repo(repository, repo_id)
    points = repository.signal_breach_trend(repo_id, signal_name, period_days)
    return SignalTrendOut(
        repo_id=repo_id, signal_name=signal_name, period_days=period_days, points=points
    )


@router.get("/authors/{author}/pr_stats", response_model=AuthorStatsOut)
def author_stats(author: str, repository: Repository = Depends(repository_dep)) -> AuthorStatsOut:
    return AuthorStatsOut(**repository.author_pr_stats(author))


@router.get("/repositories/{repo_id}/prs/{pr_id}/merge_readiness", response_model=MergeReadinessOut)
def merge_readiness(
    repo_id: str,
    pr_id: str,
    repository: Repository = Depends(repository_dep),
    settings: Settings = Depends(settings_dep),
) -> MergeReadinessOut:
    _require_repo(repository, repo_id)
    pr = repository.get_pull_request(pr_id)
    if pr is None or pr.repo_id != repo_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "PR not found")
    score = repository.latest_score_for_pr(pr_id)
    if score is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No analysis for this PR yet")
    blocking = score.blocking_reason.split("; ") if score.blocking_reason else []
    ready = score.blocking_reason is None and score.merge_readiness >= settings.ready_threshold
    return MergeReadinessOut(
        ready=ready,
        health_score=score.health_score,
        merge_readiness=score.merge_readiness,
        blocking_signals=blocking,
        override_available=score.blocking_reason is not None,
    )


@router.get("/repositories/{repo_id}/overview", response_model=OverviewOut)
def repo_overview(
    repo_id: str,
    repository: Repository = Depends(repository_dep),
    settings: Settings = Depends(settings_dep),
) -> OverviewOut:
    repo = repository.get_repository(repo_id)
    if repo is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Repository not found")
    data = repository.repo_overview(repo_id, settings.ready_threshold)
    return OverviewOut(
        repo_id=repo.id,
        repo_name=repo.name,
        provider=repo.provider,
        counts=data["counts"],
        averages=data["averages"],
        severity_distribution=data["severity_distribution"],
        top_signals=data["top_signals"],
    )


@router.get("/repositories/{repo_id}/score_history", response_model=ScoreHistoryOut)
def score_history(
    repo_id: str,
    period_days: int = Query(default=30, ge=1, le=365),
    repository: Repository = Depends(repository_dep),
) -> ScoreHistoryOut:
    _require_repo(repository, repo_id)
    points = repository.score_history(repo_id, period_days)
    return ScoreHistoryOut(repo_id=repo_id, period_days=period_days, points=points)


def _scoring_config_out(settings: Settings, eff: dict) -> ScoringConfigOut:
    """Shape an effective-config dict into the API response."""
    return ScoringConfigOut(
        health_weights=eff["health_weights"],
        risk_weights=eff["risk_weights"],
        severity_penalties=settings.severity_penalties,
        blocked_cap=settings.blocked_cap,
        ready_threshold=settings.ready_threshold,
        thresholds=eff["thresholds"],
        customized=eff["customized"],
    )


@router.get("/scoring-config", response_model=ScoringConfigOut)
def get_scoring_config(
    repository: Repository = Depends(repository_dep),
    settings: Settings = Depends(settings_dep),
) -> ScoringConfigOut:
    """The scoring knobs currently in effect — engine defaults overlaid with the
    team override. ``customized`` is True when a team override is active. Open read."""
    return _scoring_config_out(settings, effective_config(settings, repository))


@router.put(
    "/scoring-config", response_model=ScoringConfigOut, dependencies=[Depends(require_auth)]
)
def put_scoring_config(
    body: ScoringConfigUpdate,
    repository: Repository = Depends(repository_dep),
    settings: Settings = Depends(settings_dep),
) -> ScoringConfigOut:
    """Save the team's scoring override. Weights are normalized to sum 1.0 and
    thresholds sanitized server-side, so future analyses always score in range.
    Auth-gated (changing scoring is a write)."""
    health = sanitize_weights(body.health_weights, settings.health_weights)
    risk = sanitize_weights(body.risk_weights, settings.risk_weights)
    thresholds = sanitize_thresholds(body.thresholds, settings)
    repository.upsert_scoring_config(health, risk, thresholds)
    repository.session.commit()
    return _scoring_config_out(settings, effective_config(settings, repository))


@router.delete(
    "/scoring-config", response_model=ScoringConfigOut, dependencies=[Depends(require_auth)]
)
def delete_scoring_config(
    repository: Repository = Depends(repository_dep),
    settings: Settings = Depends(settings_dep),
) -> ScoringConfigOut:
    """Forget the team override so engine defaults apply again. Auth-gated."""
    repository.clear_scoring_config()
    repository.session.commit()
    return _scoring_config_out(settings, effective_config(settings, repository))


@router.get(
    "/admin/llm_check", response_model=LLMCheckOut, dependencies=[Depends(require_auth)]
)
def llm_check(settings: Settings = Depends(settings_dep)) -> LLMCheckOut:
    """Live round-trip to the configured narrator so the /analyze->LLM path is
    verifiable with one call (the real narrate step runs in the background and
    swallows errors). Auth-gated because it makes a billable model call."""
    narrator = build_narrator(settings)
    is_bedrock = settings.llm_backend == "bedrock"
    backend = settings.llm_backend if settings.llm_enabled else "disabled"
    model_cfg = settings.bedrock_model if is_bedrock else settings.anthropic_model
    ok = False
    model_returned: str | None = None
    error: str | None = None
    try:
        model_returned = narrator.probe()
        ok = True
    except Exception as exc:  # surface the true error to the operator
        error = f"{type(exc).__name__}: {exc}"[:800]
    return LLMCheckOut(
        llm_enabled=settings.llm_enabled,
        backend=backend,
        narrator=type(narrator).__name__,
        model_configured=model_cfg,
        region=settings.bedrock_region if is_bedrock else None,
        key_present=bool(settings.bedrock_api_key or settings.anthropic_api_key),
        ok=ok,
        model_returned=model_returned,
        error=error,
    )


@router.post(
    "/admin/backfill", response_model=BackfillAccepted, dependencies=[Depends(require_auth)]
)
def admin_backfill(
    body: BackfillRequest,
    background_tasks: BackgroundTasks,
    settings: Settings = Depends(settings_dep),
) -> BackfillAccepted:
    background_tasks.add_task(backfill_repo, body.provider, body.repo, body.since_days, settings)
    return BackfillAccepted(
        status="accepted", provider=body.provider, repo=body.repo, since_days=body.since_days
    )


def _require_repo(repository: Repository, repo_id: str) -> None:
    if repository.get_repository(repo_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Repository not found")
