"""Scoring-config override: GET (effective), PUT/DELETE (auth-gated), and proof
that a saved override actually changes how a PR scores."""
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


class BigChangeProvider(SCMProvider):
    """A PR that is perfect everywhere EXCEPT change_size (600 lines => HIGH), so
    health depends on how heavily change_size is weighted."""

    name = "github"

    def get_pull_request(self, repo, pr_id):
        return PullRequest(
            provider="github", repo=repo, number=pr_id, title="big", description="",
            author="alice", state=PRState.MERGED, source_branch="f", target_branch="main",
            commit_sha="sha", opened_at=_OPENED, merged_at=_OPENED + timedelta(minutes=200),
            provider_pr_id=str(pr_id),
        )

    def get_diff(self, repo, pr_id):
        return Diff(files_changed=1, additions=600, deletions=0,
                    files=[DiffFile("a.py", 600, 0, "modified")])

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


def _analyze(client, auth_headers, monkeypatch, pr_number):
    monkeypatch.setattr("app.api.routes.analyze.get_provider", lambda name, s: BigChangeProvider())
    resp = client.post(
        "/api/v1/analyze",
        headers=auth_headers,
        json={"provider": "github", "repo": "owner/repo", "pr_number": pr_number},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


def test_get_defaults_when_no_override(client):
    body = client.get("/api/v1/scoring-config").json()
    assert body["customized"] is False
    assert body["health_weights"]["review_quality"] == 0.35
    assert body["thresholds"]["change_high_lines"] == 500


def test_put_requires_auth(client):
    assert client.put("/api/v1/scoring-config", json={"health_weights": {}}).status_code == 401


def test_put_normalizes_and_sets_customized(client, auth_headers):
    # Weights that don't sum to 1 must be normalized server-side.
    payload = {
        "health_weights": {"merge_speed": 1, "change_size": 1, "review_quality": 1, "ci_status": 1},
        "thresholds": {"change_high_lines": 800},
    }
    body = client.put("/api/v1/scoring-config", headers=auth_headers, json=payload).json()
    assert body["customized"] is True
    assert abs(sum(body["health_weights"].values()) - 1.0) < 1e-9
    assert body["health_weights"]["merge_speed"] == 0.25  # 1/4 after normalize
    assert body["thresholds"]["change_high_lines"] == 800
    # GET now reflects the override
    assert client.get("/api/v1/scoring-config").json()["customized"] is True


def test_delete_resets_to_defaults(client, auth_headers):
    client.put(
        "/api/v1/scoring-config",
        headers=auth_headers,
        json={"health_weights": {"change_size": 1}, "thresholds": {}},
    )
    body = client.delete("/api/v1/scoring-config", headers=auth_headers).json()
    assert body["customized"] is False
    assert body["health_weights"]["review_quality"] == 0.35


def test_override_changes_health_score(client, auth_headers, monkeypatch):
    # Default weighting: change_size counts 25%.
    default = _analyze(client, auth_headers, monkeypatch, pr_number=1)
    health_default = default["scores"]["health_score"]

    # Emphasize the imperfect analyzer (change_size) -> health should DROP.
    client.put(
        "/api/v1/scoring-config",
        headers=auth_headers,
        json={
            "health_weights": {"merge_speed": 1, "change_size": 97, "review_quality": 1, "ci_status": 1},
            "thresholds": {},
        },
    )
    emphasized = _analyze(client, auth_headers, monkeypatch, pr_number=2)
    assert emphasized["scores"]["health_score"] < health_default

    # De-emphasize change_size -> health should RISE above default.
    client.put(
        "/api/v1/scoring-config",
        headers=auth_headers,
        json={
            "health_weights": {"merge_speed": 33, "change_size": 1, "review_quality": 33, "ci_status": 33},
            "thresholds": {},
        },
    )
    deemphasized = _analyze(client, auth_headers, monkeypatch, pr_number=3)
    assert deemphasized["scores"]["health_score"] > health_default


def test_threshold_override_changes_signal(client, auth_headers, monkeypatch):
    # With a much higher change_high_lines threshold, the 600-line PR is no longer
    # "high" -> health improves vs the default threshold (500).
    default = _analyze(client, auth_headers, monkeypatch, pr_number=1)

    client.put(
        "/api/v1/scoring-config",
        headers=auth_headers,
        json={"health_weights": {}, "thresholds": {"change_high_lines": 5000, "change_critical_lines": 10000}},
    )
    relaxed = _analyze(client, auth_headers, monkeypatch, pr_number=2)
    assert relaxed["scores"]["health_score"] >= default["scores"]["health_score"]
