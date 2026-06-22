"""ci_status analyzer boundary cases."""
from __future__ import annotations

from app.analyzers.ci_status import CiStatusAnalyzer
from app.domain.models import CheckStatus
from app.domain.signals import Severity
from tests.unit._builders import check, make_ctx, make_pr


def _names(checks, *, merged=False):
    ctx = make_ctx(checks=checks)
    return {s.name: s for s in CiStatusAnalyzer().analyze(make_pr(merged=merged), ctx)}


def test_no_checks_is_info():
    assert _names([])["no_checks"].severity is Severity.INFO


def test_required_failing_is_critical():
    sigs = _names([check("build", CheckStatus.FAILURE, required=True)])
    assert sigs["required_failing"].severity is Severity.CRITICAL
    assert "merged_despite_failure" not in sigs


def test_merged_despite_failure_adds_second_blocker():
    sigs = _names([check("build", CheckStatus.FAILURE, required=True)], merged=True)
    assert sigs["required_failing"].severity is Severity.CRITICAL
    assert sigs["merged_despite_failure"].severity is Severity.CRITICAL


def test_optional_failing_is_medium():
    sigs = _names([check("flaky", CheckStatus.FAILURE, required=False)])
    assert sigs["optional_failing"].severity is Severity.MEDIUM


def test_pending_required_is_low():
    sigs = _names([check("build", CheckStatus.PENDING, required=True)])
    assert sigs["checks_pending"].severity is Severity.LOW


def test_all_passing_is_info():
    sigs = _names([check("build", CheckStatus.SUCCESS, required=True)])
    assert sigs["checks_passing"].severity is Severity.INFO


def test_merged_with_failed_legacy_status_is_flagged():
    """The headline metric: a PR merged while a build (sourced from a legacy
    commit status, e.g. Harness) was failing."""
    from app.providers.mappers import github_mapper as gh

    payload = {
        "state": "failure",
        "statuses": [
            {"context": "harness-ci", "state": "failure"},
            {"context": "pr-health", "state": "failure"},  # our own — excluded
        ],
    }
    checks = gh.map_statuses(payload, required_checks=[], exclude_contexts={"pr-health"})
    sigs = {s.name: s for s in CiStatusAnalyzer().analyze(make_pr(merged=True), make_ctx(checks=checks))}

    assert sigs["required_failing"].severity is Severity.CRITICAL
    assert sigs["merged_despite_failure"].severity is Severity.CRITICAL
    assert sigs["merged_despite_failure"].metadata["failing_checks"] == ["harness-ci"]
