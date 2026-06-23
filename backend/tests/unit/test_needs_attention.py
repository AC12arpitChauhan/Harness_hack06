"""needs_attention ranking (Question 2): violations mapped from our signals."""
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


class _BadProvider(SCMProvider):
    """A merged PR that shipped with a failing required check and no Jira ticket."""

    name = "github"

    def get_pull_request(self, repo, pr_id):
        return PullRequest(
            provider="github", repo=repo, number=pr_id, title="add feature", description="",
            author="alice", state=PRState.MERGED, source_branch="feature/x", target_branch="main",
            commit_sha="sha", opened_at=_OPENED, merged_at=_OPENED + timedelta(minutes=200),
            jira_issue_id=None, provider_pr_id=str(pr_id),
        )

    def get_diff(self, repo, pr_id):
        return Diff(files_changed=1, additions=20, deletions=5, files=[DiffFile("a.py", 20, 5, "modified")])

    def get_reviews(self, repo, pr_id):
        return [Review("bob", ReviewState.APPROVED), Review("cara", ReviewState.APPROVED)]

    def get_checks(self, repo, sha):
        return [Check("build", CheckStatus.FAILURE, required=True)]

    def get_commits(self, repo, pr_id):
        return [Commit("sha", "alice", "msg")]

    def list_pull_requests(self, repo, since):
        return [PRRef("github", repo, 1)]

    def post_comment(self, repo, pr_id, body):
        pass

    def set_status(self, repo, sha, state, context, description):
        pass


def test_needs_attention_ranks_build_violations(client, auth_headers, monkeypatch):
    monkeypatch.setattr("app.api.routes.analyze.get_provider", lambda name, s: _BadProvider())
    seeded = client.post(
        "/api/v1/analyze",
        headers=auth_headers,
        json={"provider": "github", "repo": "owner/repo", "pr_number": 1},
    ).json()
    repo_id = seeded["repo_id"]

    rows = client.get("/api/v1/repositories/needs_attention").json()
    row = next(r for r in rows if r["repo_id"] == repo_id)
    assert row["merged_prs"] == 1
    assert row["build_violation_rate"] == 100.0  # shipped without a passing build
    assert row["signal_counts"]["merged_without_passing_build"] == 1
    assert row["signal_counts"]["no_linked_jira_ticket"] == 1  # no Jira key
    assert row["attention_score"] > 0
    assert any("merged without passing build" in r for r in row["reasons"])
