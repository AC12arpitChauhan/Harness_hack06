"""harness_mapper: Harness Code (Gitness) JSON -> the SAME canonical models as GitHub."""
from __future__ import annotations

from app.domain.models import CheckStatus, PRState, ReviewState
from app.providers.mappers import harness_mapper as hm

PULLREQ = {
    "number": 5,
    "title": "PROJ-9 add caching",
    "description": "body referencing PROJ-9",
    "state": "merged",
    "source_branch": "feat/cache",
    "target_branch": "main",
    "source_sha": "abc123",
    "merge_base_sha": "base456",
    "author": {"display_name": "Alice", "email": "a@x.com"},
    "created": 1767268800000,
    "merged": 1767270600000,
    "stats": {"commits": 2, "files_changed": 3, "additions": 50, "deletions": 5},
}


def test_map_pull_request():
    pr = hm.map_pull_request(PULLREQ, "acct/org/proj/repo")
    assert pr.provider == "harness"
    assert pr.number == 5
    assert pr.provider_pr_id == "5"
    assert pr.author == "Alice"
    assert pr.state is PRState.MERGED
    assert pr.commit_sha == "abc123"
    assert pr.base_commit_sha == "base456"
    assert pr.jira_issue_id == "PROJ-9"
    assert pr.opened_at is not None and pr.merged_at is not None
    assert pr.merged_at > pr.opened_at


def test_map_diff_uses_stats():
    files = [{"path": "a.py", "additions": 50, "deletions": 5, "status": "modified"}]
    diff = hm.map_diff(files, PULLREQ["stats"])
    assert diff.files_changed == 3
    assert diff.additions == 50
    assert diff.deletions == 5


def test_map_reviews_decisions():
    reviews = hm.map_reviews(
        [
            {"reviewer": {"display_name": "Bob"}, "review_decision": "approved"},
            {"reviewer": {"display_name": "Cara"}, "review_decision": "changereq"},
        ]
    )
    assert reviews[0].state is ReviewState.APPROVED
    assert reviews[1].state is ReviewState.CHANGES_REQUESTED


def test_map_checks():
    checks = hm.map_checks(
        [{"identifier": "build", "status": "failure", "required": True}], required_checks=[]
    )
    assert checks[0].name == "build"
    assert checks[0].status is CheckStatus.FAILURE
    assert checks[0].required is True


def test_map_commits():
    commits = hm.map_commits(
        [{"sha": "c1", "title": "fix", "author": {"identity": {"name": "Alice"}, "when": 1767268800000}}]
    )
    assert commits[0].sha == "c1"
    assert commits[0].author == "Alice"
