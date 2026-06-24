"""POST /api/v1/analyze — the synchronous scoring entrypoint (auth required).

Resolves the provider, runs the deterministic analyze->score->persist path, and
returns scores synchronously. The async narrate + writeback step is scheduled
onto BackgroundTasks (wired in Phase C).
"""
from __future__ import annotations

import httpx
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status

from app.api.deps import repository_dep, require_auth, settings_dep
from app.api.schemas import AnalyzeRequest, AnalyzeResponse, ScoreOut, SignalOut
from app.config import Settings
from app.persistence.repository import Repository
from app.providers.registry import get_provider
from app.services.analysis_service import (
    AnalysisResult,
    build_analyzers,
    build_engine,
    run_analysis,
    run_post_analysis,
)
from app.services.scoring_config import effective_config

router = APIRouter(prefix="/api/v1", tags=["analyze"])


@router.post("/analyze", response_model=AnalyzeResponse, dependencies=[Depends(require_auth)])
def analyze(
    body: AnalyzeRequest,
    background_tasks: BackgroundTasks,
    settings: Settings = Depends(settings_dep),
    repository: Repository = Depends(repository_dep),
) -> AnalyzeResponse:
    try:
        provider = get_provider(body.provider, settings)
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc

    # Apply the team's scoring override (if any) to this analysis.
    config = effective_config(settings, repository)
    try:
        result = run_analysis(
            body.repo,
            body.pr_number,
            provider=provider,
            repository=repository,
            analyzers=build_analyzers(settings, config),
            engine=build_engine(settings, config),
            repo_url=f"https://github.com/{body.repo}" if body.provider == "github" else "",
        )
    except httpx.HTTPStatusError as exc:
        code = exc.response.status_code
        raise HTTPException(
            status.HTTP_404_NOT_FOUND if code == 404 else status.HTTP_502_BAD_GATEWAY,
            f"Provider error: {code}",
        ) from exc
    finally:
        close = getattr(provider, "close", None)
        if callable(close):
            close()

    # Async: narrate (LLM or templated fallback) + writeback (if enabled). Never blocks the response.
    background_tasks.add_task(run_post_analysis, body.provider, body.repo, result, settings)

    return _to_response(body, result, settings.ready_threshold)


def _to_response(body: AnalyzeRequest, result: AnalysisResult, ready_threshold: float) -> AnalyzeResponse:
    score = result.score
    ready = score.blocking_reason is None and score.merge_readiness >= ready_threshold
    return AnalyzeResponse(
        provider=body.provider,
        repo=body.repo,
        pr_number=body.pr_number,
        repo_id=result.repo_id,
        pr_id=result.pr_id,
        run_id=result.run_id,
        ready=ready,
        scores=ScoreOut(
            health_score=score.health_score,
            review_quality_score=score.review_quality_score,
            merge_readiness=score.merge_readiness,
            blocking_reason=score.blocking_reason,
        ),
        signals=[
            SignalOut(
                signal_name=s.key,
                severity=s.severity.value,
                value=s.value,
                threshold=s.threshold,
                exceeds_threshold=s.exceeds_threshold,
                explanation=s.explanation,
            )
            for s in result.signals
        ],
    )
