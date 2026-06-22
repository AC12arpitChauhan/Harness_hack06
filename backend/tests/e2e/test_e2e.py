"""LAYER 3 — end-to-end, opt-in. Hits real GitHub and the real LLM/writeback per
your env. Gated so it never runs in normal CI.

Run:
    RUN_E2E=1 GITHUB_TOKEN=ghp_xxx E2E_REPO=owner/name E2E_PR=123 \
      ANTHROPIC_API_KEY=... LLM_ENABLED=true WRITEBACK_ENABLED=true \
      pytest tests/e2e -v

Asserts the full chain: POST /analyze -> live GitHub fetch -> analyze -> score ->
persist -> (background narrate + writeback) -> GET the PR back -> stored score
matches the response.
"""
from __future__ import annotations

import os

import pytest

_READY = (
    os.getenv("RUN_E2E") == "1"
    and bool(os.getenv("E2E_REPO"))
    and bool(os.getenv("E2E_PR"))
)
pytestmark = [
    pytest.mark.e2e,
    pytest.mark.skipif(not _READY, reason="set RUN_E2E=1, E2E_REPO, E2E_PR (and GITHUB_TOKEN)"),
]


def test_live_analyze_then_read_back(client, auth_headers):
    repo = os.environ["E2E_REPO"]
    pr_number = int(os.environ["E2E_PR"])

    resp = client.post(
        "/api/v1/analyze",
        headers=auth_headers,
        json={"provider": "github", "repo": repo, "pr_number": pr_number},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()

    # scores are present and in range
    for key in ("health_score", "risk_score", "review_quality_score", "merge_readiness"):
        assert 0.0 <= body["scores"][key] <= 100.0

    # read the PR back from the DB; stored score must match the response exactly
    detail = client.get(
        f"/api/v1/repositories/{body['repo_id']}/prs/{body['pr_id']}"
    ).json()
    assert detail["score"]["health_score"] == body["scores"]["health_score"]
    assert detail["score"]["merge_readiness"] == body["scores"]["merge_readiness"]

    # a narrative was produced (templated or LLM, depending on env)
    assert detail["narrative"] is not None
