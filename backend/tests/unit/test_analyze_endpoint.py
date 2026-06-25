"""POST /api/v1/analyze end-to-end through the app with a MOCKED provider.

Asserts both the response DTO shape and the persisted rows (SQLite test DB).
No network: the provider is replaced with one returning fixture-derived models.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.domain.models import (
    AnalysisContext,  # noqa: F401  (kept for parity with provider contract)
    Check,
    Commit,
    Diff,
    DiffFile,
    PRRef,
    PRState,
    PullRequest,
    Review,
)
from app.persistence import orm
from app.persistence.db import get_session_factory
from app.providers.base import SCMProvider

_OPENED = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)


class FakeGitHubProvider(SCMProvider):
    """Returns canonical models for a PR merged 3 minutes after opening."""

    name = "github"

    def get_pull_request(self, repo, pr_id):
        return PullRequest(
            provider="github",
            repo=repo,
            number=pr_id,
            title="PROJ-7 quick fix",
            description="",
            author="alice",
            state=PRState.MERGED,
            source_branch="fix/x",
            target_branch="main",
            commit_sha="headsha",
            base_commit_sha="basesha",
            opened_at=_OPENED,
            merged_at=_OPENED + timedelta(minutes=3),
            jira_issue_id="PROJ-7",
            provider_pr_id=str(pr_id),
        )

    def get_diff(self, repo, pr_id):
        return Diff(
            files_changed=1,
            additions=5,
            deletions=1,
            files=[DiffFile(filename="x.py", additions=5, deletions=1, status="modified")],
        )

    def get_reviews(self, repo, pr_id) -> list[Review]:
        return []

    def get_checks(self, repo, sha) -> list[Check]:
        return []

    def get_commits(self, repo, pr_id) -> list[Commit]:
        return []

    def list_pull_requests(self, repo, since) -> list[PRRef]:
        return []

    def post_comment(self, repo, pr_id, body) -> None:
        pass

    def set_status(self, repo, sha, state, context, description) -> None:
        pass


def test_analyze_returns_scores_and_persists(client, auth_headers, monkeypatch):
    monkeypatch.setattr(
        "app.api.routes.analyze.get_provider", lambda name, settings: FakeGitHubProvider()
    )

    resp = client.post(
        "/api/v1/analyze",
        headers=auth_headers,
        json={"provider": "github", "repo": "owner/repo", "pr_number": 7},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()

    # --- response DTO ---
    assert body["provider"] == "github"
    assert body["pr_number"] == 7
    # Phase A: only merge_speed is enabled -> other dimensions default to perfect.
    assert body["scores"]["health_score"] == 90.0
    assert body["scores"]["risk_score"] == 10.0
    assert body["scores"]["review_quality_score"] == 100.0
    assert body["scores"]["merge_readiness"] == 90.0
    assert body["scores"]["blocking_reason"] is None
    assert body["ready"] is True
    names = {s["signal_name"]: s for s in body["signals"]}
    assert names["merge_speed.fast_merge"]["severity"] == "critical"

    # --- persisted rows ---
    session = get_session_factory()()
    try:
        pr_rows = list(session.scalars(select(orm.PullRequest)))
        assert len(pr_rows) == 1
        assert pr_rows[0].provider_pr_id == "7"
        assert pr_rows[0].jira_issue_id == "PROJ-7"

        runs = list(session.scalars(select(orm.AnalysisRun)))
        assert len(runs) == 1 and runs[0].status == "completed"

        scores = list(session.scalars(select(orm.AnalysisScore)))
        assert len(scores) == 1 and scores[0].health_score == 90.0
        assert scores[0].score_breakdown_json["analyzer_subscores"]["merge_speed"] == 50.0

        sigs = list(session.scalars(select(orm.AnalysisSignal)))
        assert any(s.signal_name == "merge_speed.fast_merge" for s in sigs)

        diff = session.scalar(select(orm.PrDiff))
        assert diff is not None and diff.files_changed == 1
    finally:
        session.close()


def test_analyze_requires_auth(client):
    resp = client.post("/api/v1/analyze", json={"provider": "github", "repo": "o/r", "pr_number": 1})
    assert resp.status_code == 401


def test_unknown_provider_is_400(client, auth_headers):
    resp = client.post(
        "/api/v1/analyze",
        headers=auth_headers,
        json={"provider": "gitlab", "repo": "o/r", "pr_number": 1},
    )
    assert resp.status_code == 400
