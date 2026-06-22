"""merge_speed analyzer boundary cases."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.analyzers.merge_speed import MergeSpeedAnalyzer
from app.domain.models import AnalysisContext, Diff, PRState, PullRequest
from app.domain.signals import Severity

OPENED = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
EMPTY_CTX = AnalysisContext(diff=Diff(files_changed=0, additions=0, deletions=0))


def _pr(merged_after_minutes: int | None) -> PullRequest:
    merged = OPENED + timedelta(minutes=merged_after_minutes) if merged_after_minutes is not None else None
    return PullRequest(
        provider="github",
        repo="o/r",
        number=1,
        title="t",
        description="",
        author="a",
        state=PRState.MERGED if merged else PRState.OPEN,
        source_branch="f",
        target_branch="main",
        commit_sha="sha",
        opened_at=OPENED,
        merged_at=merged,
    )


def test_very_fast_merge_is_critical():
    sig = MergeSpeedAnalyzer().analyze(_pr(3), EMPTY_CTX)[0]
    assert sig.key == "merge_speed.fast_merge"
    assert sig.severity is Severity.CRITICAL
    assert sig.exceeds_threshold is True
    assert sig.value == 3.0


def test_moderate_merge_is_high():
    sig = MergeSpeedAnalyzer().analyze(_pr(40), EMPTY_CTX)[0]
    assert sig.severity is Severity.HIGH
    assert sig.exceeds_threshold is True


def test_slow_merge_is_healthy_info():
    sig = MergeSpeedAnalyzer().analyze(_pr(180), EMPTY_CTX)[0]
    assert sig.key == "merge_speed.healthy_pace"
    assert sig.severity is Severity.INFO
    assert sig.exceeds_threshold is False


def test_open_pr_is_not_applicable():
    sig = MergeSpeedAnalyzer().analyze(_pr(None), EMPTY_CTX)[0]
    assert sig.key == "merge_speed.not_merged"
    assert sig.severity is Severity.INFO


def test_thresholds_are_configurable():
    # With a 5-minute fast threshold, a 10-minute merge is no longer critical.
    sig = MergeSpeedAnalyzer(fast_merge_minutes=5, slow_merge_minutes=30).analyze(_pr(10), EMPTY_CTX)[0]
    assert sig.severity is Severity.HIGH
