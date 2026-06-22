"""Dashboard read endpoints (open locally) + admin backfill (auth required).

All SQL lives in Repository; these handlers only shape ORM rows into DTOs.
"""
from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from fastapi.responses import HTMLResponse

from app.api.deps import repository_dep, require_auth, settings_dep
from app.api.schemas import (
    AuthorListItem,
    AuthorStatsOut,
    BackfillAccepted,
    BackfillRequest,
    MergeReadinessOut,
    NarrativeOut,
    PRDetail,
    PRListItem,
    RepositoryOut,
    RepoHealthSummary,
    ScoreSummary,
    SignalOut,
    SignalTrendOut,
)
from app.config import Settings
from app.persistence import orm
from app.persistence.repository import Repository
from app.services.backfill_service import backfill_repo

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


@router.get("/dashboard/summary", response_model=list[RepoHealthSummary])
def dashboard_summary(repository: Repository = Depends(repository_dep)) -> list[RepoHealthSummary]:
    """Repo-level health table — answers 'how healthy are our PR practices?'"""
    return [RepoHealthSummary(**row) for row in repository.dashboard_summary()]


@router.get("/authors", response_model=list[AuthorListItem])
def list_authors(repository: Repository = Depends(repository_dep)) -> list[AuthorListItem]:
    """All authors ranked by avg risk score — answers 'which teams need attention?'"""
    return [AuthorListItem(**row) for row in repository.list_authors()]


@router.get("/dashboard", response_class=HTMLResponse, include_in_schema=False)
def html_dashboard(repository: Repository = Depends(repository_dep)) -> HTMLResponse:
    """Serves the human-readable PR health dashboard."""
    summary = repository.dashboard_summary()
    authors = repository.list_authors()
    return HTMLResponse(_build_html(summary, authors))


# ---------------------------------------------------------------------------
# HTML dashboard renderer
# ---------------------------------------------------------------------------

def _health_label(score: float | None) -> str:
    if score is None:
        return "no data"
    if score >= 80:
        return "HEALTHY"
    if score >= 60:
        return "GOOD"
    if score >= 40:
        return "FAIR"
    return "POOR"


def _badge(score: float | None) -> str:
    label = _health_label(score)
    color = {"POOR": "#e5484d", "FAIR": "#f5a524", "GOOD": "#30a46c",
             "HEALTHY": "#30a46c", "no data": "#8b8b8b"}[label]
    return f'<span class="badge" style="background:{color}">{label}</span>'


def _bar(pct: float | None) -> str:
    v = max(0, min(100, pct or 0))
    return (f'<div class="bar"><div class="fill" style="width:{v:.0f}%;'
            f'background:{"#e5484d" if v < 60 else "#30a46c"}"></div>'
            f'<span>{v:.0f}</span></div>')


def _build_html(summary: list[dict], authors: list[dict]) -> str:
    repo_rows = "".join(
        f"<tr><td>{r['name']}</td><td>{r['provider']}</td>"
        f"<td>{r['merged_prs']}/{r['total_prs']}</td>"
        f"<td>{_bar(r['avg_health_score'])}</td>"
        f"<td>{r['avg_risk_score'] or 'n/a'}</td>"
        f"<td>{r['blocked_merges']}</td>"
        f"<td>{_badge(r['avg_health_score'])}</td></tr>"
        for r in summary
    ) or "<tr><td colspan='7'>No data yet — run a backfill or POST /api/v1/analyze</td></tr>"

    attention = "".join(
        f"<li><b>{r['name']}</b> — avg health {r['avg_health_score']:.1f}, "
        f"{r['blocked_merges']} blocked merge(s)</li>"
        for r in summary if r["needs_attention"]
    ) or "<li>No repositories below the attention threshold.</li>"

    author_rows = "".join(
        f"<tr><td>{a['author']}</td><td>{a['pr_count']}</td>"
        f"<td>{a['avg_health_score'] or 'n/a'}</td>"
        f"<td>{a['avg_risk_score'] or 'n/a'}</td></tr>"
        for a in authors[:15]
    ) or "<tr><td colspan='4'>No author data yet.</td></tr>"

    return f"""<!doctype html><html><head><meta charset="utf-8">
<title>PR Health Dashboard</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>
 body{{font-family:system-ui,Arial,sans-serif;margin:0;background:#0e1116;color:#e6e6e6}}
 header{{background:#161b22;padding:20px 32px;border-bottom:1px solid #30363d}}
 h1{{margin:0;font-size:22px}} h2{{font-size:15px;color:#9ecbff;margin-top:0}}
 .sub{{color:#8b949e;font-size:13px}} main{{padding:24px 32px;max-width:1100px}}
 section{{background:#161b22;border:1px solid #30363d;border-radius:10px;
          padding:18px 22px;margin-bottom:20px}}
 table{{width:100%;border-collapse:collapse}}
 th,td{{text-align:left;padding:8px 10px;border-bottom:1px solid #21262d;font-size:14px}}
 th{{color:#8b949e;font-weight:600}}
 .badge{{color:#fff;padding:2px 10px;border-radius:20px;font-size:12px;font-weight:600}}
 .bar{{position:relative;background:#21262d;border-radius:6px;height:18px;width:100px;display:inline-block}}
 .bar .fill{{height:100%;border-radius:6px}}
 .bar span{{position:absolute;left:8px;top:0;font-size:11px;line-height:18px}}
 ul{{margin:6px 0}} li{{font-size:14px;margin:3px 0}}
 a{{color:#58a6ff;text-decoration:none}}
</style></head><body>
<header>
  <h1>PR Health Dashboard</h1>
  <div class="sub">Powered by Harness SCM data &mdash;
    <a href="/docs">API docs</a> &middot;
    <a href="/api/v1/dashboard/summary">JSON summary</a>
  </div>
</header>
<main>
  <section>
    <h2>Repository health (worst first)</h2>
    <table>
      <tr><th>Repo</th><th>Provider</th><th>Merged/Total PRs</th>
          <th>Avg health</th><th>Avg risk</th><th>Blocked merges</th><th>Status</th></tr>
      {repo_rows}
    </table>
  </section>
  <section>
    <h2>Repositories needing attention</h2>
    <ul>{attention}</ul>
  </section>
  <section>
    <h2>Authors ranked by risk (worst first)</h2>
    <table>
      <tr><th>Author</th><th>PRs</th><th>Avg health</th><th>Avg risk</th></tr>
      {author_rows}
    </table>
    <p style="color:#8b949e;font-size:12px;margin-top:8px">
      Full author stats: <code>GET /api/v1/authors/&lt;name&gt;/pr_stats</code>
    </p>
  </section>
</main></body></html>"""
