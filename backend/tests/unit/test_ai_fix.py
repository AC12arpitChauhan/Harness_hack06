"""AI fix-suggester endpoint: derives failing checks from the persisted snapshot and
returns a suggestion. LLM is disabled in tests, so the deterministic templated path runs."""
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


class _Provider(SCMProvider):
    name = "github"

    def __init__(self, check_status: CheckStatus) -> None:
        self._cs = check_status

    def get_pull_request(self, repo, pr_id):
        return PullRequest(
            provider="github", repo=repo, number=pr_id, title="PROJ-9 add feature", description="",
            author="alice", state=PRState.MERGED, source_branch="f", target_branch="main",
            commit_sha="sha", opened_at=_OPENED, merged_at=_OPENED + timedelta(minutes=200),
            jira_issue_id="PROJ-9", provider_pr_id=str(pr_id),
        )

    def get_diff(self, repo, pr_id):
        return Diff(files_changed=1, additions=40, deletions=5, files=[DiffFile("a.py", 40, 5, "modified")])

    def get_reviews(self, repo, pr_id):
        return [Review("bob", ReviewState.APPROVED), Review("cara", ReviewState.APPROVED)]

    def get_checks(self, repo, sha):
        return [Check("build", self._cs, required=True)]

    def get_commits(self, repo, pr_id):
        return [Commit("sha", "alice", "msg")]

    def list_pull_requests(self, repo, since):
        return [PRRef("github", repo, 1)]

    def post_comment(self, repo, pr_id, body):
        pass

    def set_status(self, repo, sha, state, context, description):
        pass


def _seed(client, auth_headers, monkeypatch, check_status: CheckStatus):
    monkeypatch.setattr("app.api.routes.analyze.get_provider", lambda name, s: _Provider(check_status))
    resp = client.post(
        "/api/v1/analyze",
        headers=auth_headers,
        json={"provider": "github", "repo": "owner/repo", "pr_number": 1},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


def test_ai_fix_with_failing_check(client, auth_headers, monkeypatch):
    seeded = _seed(client, auth_headers, monkeypatch, CheckStatus.FAILURE)
    repo_id, pr_id = seeded["repo_id"], seeded["pr_id"]
    body = client.get(f"/api/v1/repositories/{repo_id}/prs/{pr_id}/ai_fix").json()
    assert body["pr_id"] == pr_id
    assert body["has_failures"] is True
    assert any(c["name"] == "build" and c["status"] == "failure" for c in body["failing_checks"])
    assert body["suggestion"]  # non-empty (templated heuristic in tests)
    assert body["model"]  # producer label present


def test_ai_fix_no_failures_is_empty(client, auth_headers, monkeypatch):
    seeded = _seed(client, auth_headers, monkeypatch, CheckStatus.SUCCESS)
    repo_id, pr_id = seeded["repo_id"], seeded["pr_id"]
    body = client.get(f"/api/v1/repositories/{repo_id}/prs/{pr_id}/ai_fix").json()
    assert body["has_failures"] is False
    assert body["failing_checks"] == []
    assert body["suggestion"] == ""


def test_ai_fix_unknown_repo_404(client):
    assert client.get("/api/v1/repositories/nope/prs/nope/ai_fix").status_code == 404
