"""github_mapper: raw GitHub JSON -> canonical domain models."""
from __future__ import annotations

from app.domain.models import CheckStatus, PRState, ReviewState
from app.providers.mappers import github_mapper as gh

PR_JSON = {
    "number": 42,
    "title": "PROJ-123 Add caching layer",
    "body": "Implements the cache. Closes PROJ-123.",
    "state": "closed",
    "merged": True,
    "created_at": "2026-01-01T12:00:00Z",
    "merged_at": "2026-01-01T12:30:00Z",
    "closed_at": "2026-01-01T12:30:00Z",
    "user": {"login": "alice"},
    "head": {"ref": "feature/cache", "sha": "headsha123"},
    "base": {"ref": "main", "sha": "basesha456"},
    "additions": 100,
    "deletions": 20,
    "changed_files": 3,
}


def test_map_pull_request_maps_every_field():
    pr = gh.map_pull_request(PR_JSON, "owner/repo")
    assert pr.provider == "github"
    assert pr.repo == "owner/repo"
    assert pr.number == 42
    assert pr.provider_pr_id == "42"
    assert pr.title == "PROJ-123 Add caching layer"
    assert pr.author == "alice"
    assert pr.state is PRState.MERGED
    assert pr.source_branch == "feature/cache"
    assert pr.target_branch == "main"
    assert pr.commit_sha == "headsha123"
    assert pr.base_commit_sha == "basesha456"
    assert pr.jira_issue_id == "PROJ-123"
    assert pr.opened_at is not None and pr.merged_at is not None


def test_open_pr_state():
    pr = gh.map_pull_request({**PR_JSON, "state": "open", "merged": False, "merged_at": None}, "o/r")
    assert pr.state is PRState.OPEN


def test_map_diff_prefers_pr_totals():
    files = [
        {"filename": "a.py", "additions": 80, "deletions": 10, "status": "modified"},
        {"filename": "b.py", "additions": 20, "deletions": 10, "status": "added"},
    ]
    diff = gh.map_diff(files, PR_JSON)
    assert diff.files_changed == 3  # from PR totals, not len(files)
    assert diff.additions == 100
    assert diff.deletions == 20
    assert len(diff.files) == 2
    assert diff.total_changes == 120


def test_map_reviews():
    reviews = gh.map_reviews(
        [
            {"user": {"login": "bob"}, "state": "APPROVED", "submitted_at": "2026-01-01T12:10:00Z"},
            {"user": {"login": "cara"}, "state": "CHANGES_REQUESTED", "submitted_at": None},
        ]
    )
    assert reviews[0].reviewer == "bob"
    assert reviews[0].state is ReviewState.APPROVED
    assert reviews[1].state is ReviewState.CHANGES_REQUESTED


def test_map_checks_required_allowlist():
    payload = {
        "check_runs": [
            {"name": "build", "status": "completed", "conclusion": "failure", "html_url": "u1"},
            {"name": "lint", "status": "completed", "conclusion": "success", "html_url": "u2"},
            {"name": "deploy", "status": "in_progress", "conclusion": None},
        ]
    }
    checks = gh.map_checks(payload, required_checks=["build"])
    by_name = {c.name: c for c in checks}
    assert by_name["build"].status is CheckStatus.FAILURE
    assert by_name["build"].required is True
    assert by_name["lint"].status is CheckStatus.SUCCESS
    assert by_name["lint"].required is False
    assert by_name["deploy"].status is CheckStatus.PENDING


def test_map_checks_empty_allowlist_means_all_required():
    payload = {"check_runs": [{"name": "x", "status": "completed", "conclusion": "success"}]}
    assert gh.map_checks(payload, required_checks=[])[0].required is True


def test_map_commits():
    commits = gh.map_commits(
        [
            {
                "sha": "c1",
                "commit": {"message": "fix", "author": {"name": "Alice", "date": "2026-01-01T12:05:00Z"}},
                "author": {"login": "alice"},
            }
        ]
    )
    assert commits[0].sha == "c1"
    assert commits[0].author == "alice"
    assert commits[0].message == "fix"
    assert commits[0].committed_at is not None
