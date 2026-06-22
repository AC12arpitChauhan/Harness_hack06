"""review_quality analyzer boundary cases."""
from __future__ import annotations

from app.analyzers.review_quality import ReviewQualityAnalyzer
from app.domain.models import ReviewState
from app.domain.signals import Severity
from tests.unit._builders import make_ctx, make_diff, make_pr, review

PR = make_pr()


def _names(reviews, additions=100):
    ctx = make_ctx(make_diff(additions), reviews=reviews)
    return {s.name: s for s in ReviewQualityAnalyzer().analyze(PR, ctx)}


def test_no_reviews_nontrivial_is_critical_blocker():
    sigs = _names([], additions=100)
    assert sigs["no_reviews"].severity is Severity.CRITICAL
    assert sigs["no_reviews"].exceeds_threshold is True


def test_no_reviews_trivial_is_info():
    sigs = _names([], additions=5)
    assert "no_reviews" not in sigs
    assert sigs["no_review_trivial"].severity is Severity.INFO


def test_reviewers_without_approval_is_high():
    sigs = _names([review("bob", ReviewState.CHANGES_REQUESTED)])
    assert sigs["no_approval"].severity is Severity.HIGH


def test_single_approver_is_thin_review():
    sigs = _names([review("bob", ReviewState.APPROVED)])
    assert sigs["single_reviewer"].severity is Severity.LOW
    assert "well_reviewed" not in sigs


def test_two_approvers_is_well_reviewed():
    sigs = _names([review("bob", ReviewState.APPROVED), review("cara", ReviewState.APPROVED)])
    assert sigs["well_reviewed"].severity is Severity.INFO
    assert "single_reviewer" not in sigs
    assert "no_approval" not in sigs
