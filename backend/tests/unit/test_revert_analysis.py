"""revert_correlation (Question 3): detect 'Revert … #N' PRs and correlate behaviours."""
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
    """PR #1 is a clean merged change; PR #2 reverts it ('Revert … (#1)')."""

    name = "github"

    def get_pull_request(self, repo, pr_id):
        revert = pr_id == 2
        return PullRequest(
            provider="github", repo=repo, number=pr_id,
            title='Revert "PROJ-1 add feature" (#1)' if revert else "PROJ-1 add feature",
            description="", author="alice", state=PRState.MERGED, source_branch="f",
            target_branch="main", commit_sha=f"sha{pr_id}", opened_at=_OPENED,
            merged_at=_OPENED + timedelta(minutes=200),
            jira_issue_id=None if revert else "PROJ-1", provider_pr_id=str(pr_id),
        )

    def get_diff(self, repo, pr_id):
        return Diff(files_changed=1, additions=30, deletions=5, files=[DiffFile("a.py", 30, 5, "modified")])

    def get_reviews(self, repo, pr_id):
        return [Review("bob", ReviewState.APPROVED), Review("cara", ReviewState.APPROVED)]

    def get_checks(self, repo, sha):
        return [Check("build", CheckStatus.SUCCESS, required=True)]

    def get_commits(self, repo, pr_id):
        return [Commit(f"sha{pr_id}", "alice", "msg")]

    def list_pull_requests(self, repo, since):
        return [PRRef("github", repo, 1), PRRef("github", repo, 2)]

    def post_comment(self, repo, pr_id, body):
        pass

    def set_status(self, repo, sha, state, context, description):
        pass


def test_revert_correlation_detects_and_correlates(client, auth_headers, monkeypatch):
    monkeypatch.setattr("app.api.routes.analyze.get_provider", lambda name, s: _Provider())
    repo_id = None
    for n in (1, 2):
        seeded = client.post(
            "/api/v1/analyze",
            headers=auth_headers,
            json={"provider": "github", "repo": "owner/repo", "pr_number": n},
        ).json()
        repo_id = seeded["repo_id"]

    body = client.get(f"/api/v1/repositories/{repo_id}/revert_analysis").json()
    assert body["repo_id"] == repo_id
    assert body["merged"] == 2
    assert body["reverted"] == 1  # PR #1 was reverted by PR #2

    behaviours = {b["behaviour"]: b for b in body["behaviours"]}
    assert set(behaviours) == {"passing_build", "linked_jira", "small_change", "unrushed_merge"}
    # both PRs pass CI, so all merged PRs "have" passing_build; 1 of 2 was reverted.
    pb = behaviours["passing_build"]
    assert pb["with_total"] == 2
    assert pb["with_rate"] == 50.0
