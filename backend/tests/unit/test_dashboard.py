"""Dashboard endpoints over data seeded through /analyze (mocked provider)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.domain.models import (
    Check,
    CheckStatus,
    Commit,
    Diff,
    DiffFile,
    PRRef,
    PRState,
    PullRequest,
    Review,
    ReviewState,
)
from app.providers.base import SCMProvider

_OPENED = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)


class SeedProvider(SCMProvider):
    name = "github"

    def get_pull_request(self, repo, pr_id):
        return PullRequest(
            provider="github", repo=repo, number=pr_id, title="PROJ-1 seed", description="",
            author="alice", state=PRState.MERGED, source_branch="f", target_branch="main",
            commit_sha="sha", opened_at=_OPENED, merged_at=_OPENED + timedelta(minutes=200),
            jira_issue_id="PROJ-1", provider_pr_id=str(pr_id),
        )

    def get_diff(self, repo, pr_id):
        return Diff(files_changed=1, additions=40, deletions=5,
                    files=[DiffFile("a.py", 40, 5, "modified")])

    def get_reviews(self, repo, pr_id):
        return [Review("bob", ReviewState.APPROVED), Review("cara", ReviewState.APPROVED)]

    def get_checks(self, repo, sha):
        return [Check("build", CheckStatus.SUCCESS, required=True)]

    def get_commits(self, repo, pr_id):
        return [Commit("sha", "alice", "msg")]

    def list_pull_requests(self, repo, since):
        return [PRRef("github", repo, 1)]

    def post_comment(self, repo, pr_id, body):
        pass

    def set_status(self, repo, sha, state, context, description):
        pass


def _seed(client, auth_headers, monkeypatch, pr_number=1):
    monkeypatch.setattr("app.api.routes.analyze.get_provider", lambda name, s: SeedProvider())
    resp = client.post(
        "/api/v1/analyze",
        headers=auth_headers,
        json={"provider": "github", "repo": "owner/repo", "pr_number": pr_number},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


def test_repositories_and_prs_and_detail(client, auth_headers, monkeypatch):
    seeded = _seed(client, auth_headers, monkeypatch)
    repo_id, pr_id = seeded["repo_id"], seeded["pr_id"]

    repos = client.get("/api/v1/repositories").json()
    assert any(r["id"] == repo_id and r["pr_count"] >= 1 for r in repos)
    assert repos[0]["avg_health_score"] is not None

    prs = client.get(f"/api/v1/repositories/{repo_id}/prs").json()
    assert len(prs) == 1
    assert prs[0]["pr_id"] == pr_id
    assert prs[0]["score"]["health_score"] == 100.0

    detail = client.get(f"/api/v1/repositories/{repo_id}/prs/{pr_id}").json()
    assert detail["jira_issue_id"] == "PROJ-1"
    assert detail["score"]["health_score"] == 100.0
    assert len(detail["signals"]) >= 1
    # background templated narrative was persisted
    assert detail["narrative"] is not None
    assert detail["narrative"]["ai_model"] == "templated-fallback"


def test_merge_readiness_ready(client, auth_headers, monkeypatch):
    seeded = _seed(client, auth_headers, monkeypatch)
    repo_id, pr_id = seeded["repo_id"], seeded["pr_id"]
    mr = client.get(f"/api/v1/repositories/{repo_id}/prs/{pr_id}/merge_readiness").json()
    assert mr["ready"] is True
    assert mr["blocking_signals"] == []
    assert mr["override_available"] is False


def test_author_stats(client, auth_headers, monkeypatch):
    _seed(client, auth_headers, monkeypatch)
    stats = client.get("/api/v1/authors/alice/pr_stats").json()
    assert stats["author"] == "alice"
    assert stats["pr_count"] == 1
    assert stats["avg_health_score"] == 100.0


def test_unknown_repo_is_404(client):
    assert client.get("/api/v1/repositories/does-not-exist/prs").status_code == 404


def test_signal_trends_endpoint(client, auth_headers, monkeypatch):
    # Exercises signal_breach_trend (the Postgres-portable, Python-bucketed query).
    seeded = _seed(client, auth_headers, monkeypatch)
    repo_id = seeded["repo_id"]
    r = client.get(
        f"/api/v1/repositories/{repo_id}/signal_trends"
        "?signal_name=merge_speed.fast_merge&period_days=30"
    )
    assert r.status_code == 200
    body = r.json()
    assert body["signal_name"] == "merge_speed.fast_merge"
    assert isinstance(body["points"], list)


def test_overview_endpoint(client, auth_headers, monkeypatch):
    seeded = _seed(client, auth_headers, monkeypatch)
    repo_id = seeded["repo_id"]
    body = client.get(f"/api/v1/repositories/{repo_id}/overview").json()
    assert body["repo_id"] == repo_id
    assert body["counts"]["total"] == 1
    assert body["counts"]["analyzed"] == 1
    assert body["averages"]["health"] == 100.0
    assert set(body["severity_distribution"]) == {"critical", "high", "medium", "low", "info"}
    assert isinstance(body["top_signals"], list)


def test_score_history_endpoint(client, auth_headers, monkeypatch):
    seeded = _seed(client, auth_headers, monkeypatch)
    repo_id = seeded["repo_id"]
    body = client.get(f"/api/v1/repositories/{repo_id}/score_history?period_days=30").json()
    assert body["repo_id"] == repo_id
    assert len(body["points"]) >= 1
    assert body["points"][0]["avg_health"] == 100.0


def test_cors_header_present(client):
    r = client.get("/api/v1/repositories", headers={"Origin": "http://localhost:5173"})
    assert r.headers.get("access-control-allow-origin") in ("*", "http://localhost:5173")


def test_backfill_requires_auth_and_accepts(client, auth_headers, monkeypatch):
    calls = []
    monkeypatch.setattr(
        "app.api.routes.dashboard.backfill_repo",
        lambda provider, repo, since_days, settings: calls.append((provider, repo, since_days)),
    )
    # no auth
    assert client.post("/api/v1/admin/backfill", json={"repo": "o/r"}).status_code == 401
    # with auth
    resp = client.post(
        "/api/v1/admin/backfill", headers=auth_headers, json={"repo": "o/r", "since_days": 7}
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "accepted"
    assert calls == [("github", "o/r", 7)]
