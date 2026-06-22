"""LAYER 1 -> LAYER 2: load captured GitHub JSON fixtures, map to canonical models,
run the full analyzer+scoring pipeline, and assert the deterministic outcome.

The fixtures under tests/fixtures/github/ are the ground truth (regenerate from a
real PR with scripts/capture_fixtures.py)."""
from __future__ import annotations

import json
import pathlib

from app.analyzers.registry import enabled_analyzers
from app.domain.models import AnalysisContext, CheckStatus, PRState, ReviewState
from app.providers.mappers import github_mapper as gh
from app.scoring.engine import ScoringEngine

FIXTURES = pathlib.Path(__file__).resolve().parent.parent / "fixtures" / "github"


def _load(name: str):
    return json.loads((FIXTURES / f"{name}.json").read_text())


def _context_and_pr():
    pull = _load("pull")
    pr = gh.map_pull_request(pull, "owner/repo")
    ctx = AnalysisContext(
        diff=gh.map_diff(_load("files"), pull),
        reviews=gh.map_reviews(_load("reviews")),
        checks=gh.map_checks(_load("check_runs"), required_checks=[]),
        commits=gh.map_commits(_load("commits")),
    )
    return pr, ctx


def test_fixtures_map_to_canonical_models():
    pr, ctx = _context_and_pr()
    assert pr.state is PRState.MERGED
    assert pr.jira_issue_id == "PROJ-42"
    assert pr.commit_sha == "deadbeefcafe0001"
    assert ctx.diff.files_changed == 12
    assert ctx.diff.total_changes == 720
    assert len(ctx.reviews) == 1 and ctx.reviews[0].state is ReviewState.APPROVED
    statuses = {c.name: c.status for c in ctx.checks}
    assert statuses["build"] is CheckStatus.SUCCESS
    assert statuses["test"] is CheckStatus.FAILURE


def test_fixtures_full_pipeline_scores():
    pr, ctx = _context_and_pr()
    signals = [s for a in enabled_analyzers() for s in a.analyze(pr, ctx)]
    score = ScoringEngine().compute(signals)
    # merge_speed CRIT(50)->50, change_size HIGH(30)->70, review LOW(5)->95, ci 100->0
    assert score.health_score == 60.75
    assert score.review_quality_score == 95.0
    assert score.merge_readiness == 15.0  # blocked
    assert "Required CI" in score.blocking_reason
    assert "Merged despite" in score.blocking_reason
