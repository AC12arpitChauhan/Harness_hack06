"""ticket_linkage analyzer: surfaces Jira linkage, never moves the score."""
from __future__ import annotations

from datetime import datetime, timezone

from app.analyzers.registry import enabled_analyzers
from app.analyzers.ticket_linkage import TicketLinkageAnalyzer
from app.domain.models import AnalysisContext, Diff, PRState, PullRequest
from app.domain.signals import Severity
from app.scoring.engine import ScoringEngine

OPENED = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
EMPTY_CTX = AnalysisContext(diff=Diff(files_changed=1, additions=10, deletions=0))


def _pr(*, title="add retry logic", description="", branch="feature/x", jira=None) -> PullRequest:
    return PullRequest(
        provider="github",
        repo="o/r",
        number=1,
        title=title,
        description=description,
        author="a",
        state=PRState.MERGED,
        source_branch=branch,
        target_branch="main",
        commit_sha="sha",
        opened_at=OPENED,
        merged_at=OPENED,
        jira_issue_id=jira,
    )


def test_no_jira_emits_low_signal():
    sig = TicketLinkageAnalyzer().analyze(_pr(), EMPTY_CTX)[0]
    assert sig.key == "ticket_linkage.no_jira"
    assert sig.severity is Severity.LOW
    assert sig.exceeds_threshold is True


def test_explicit_jira_id_emits_info_linked():
    sig = TicketLinkageAnalyzer().analyze(_pr(jira="PROJ-1"), EMPTY_CTX)[0]
    assert sig.key == "ticket_linkage.linked"
    assert sig.severity is Severity.INFO
    assert sig.metadata["jira_issue_id"] == "PROJ-1"


def test_key_detected_in_title_or_branch_without_explicit_id():
    sig = TicketLinkageAnalyzer().analyze(_pr(title="PROJ-42 add cache"), EMPTY_CTX)[0]
    assert sig.key == "ticket_linkage.linked"
    assert sig.metadata["jira_issue_id"] == "PROJ-42"

    sig2 = TicketLinkageAnalyzer().analyze(_pr(branch="feature/ABC-9-thing"), EMPTY_CTX)[0]
    assert sig2.key == "ticket_linkage.linked"
    assert sig2.metadata["jira_issue_id"] == "ABC-9"


def test_ticket_linkage_is_surfaced_but_zero_weight():
    """The Jira signal must NOT change the deterministic scores (it has no weight)."""
    pr = _pr()  # no jira -> would emit a LOW no_jira signal
    others = [
        s
        for a in enabled_analyzers()
        if a.name != "ticket_linkage"
        for s in a.analyze(pr, EMPTY_CTX)
    ]
    all_signals = [s for a in enabled_analyzers() for s in a.analyze(pr, EMPTY_CTX)]

    # The Jira signal is present in the full set...
    assert any(s.key == "ticket_linkage.no_jira" for s in all_signals)
    assert not any(s.key.startswith("ticket_linkage") for s in others)

    # ...but the four scores are identical with and without it.
    engine = ScoringEngine()
    before = engine.compute(others)
    after = engine.compute(all_signals)
    assert (after.health_score, after.risk_score, after.review_quality_score, after.merge_readiness) == (
        before.health_score,
        before.risk_score,
        before.review_quality_score,
        before.merge_readiness,
    )
    # And the penalty record marks it as not counted toward the score.
    rec = next(r for r in after.breakdown.penalties if r["signal"] == "ticket_linkage.no_jira")
    assert rec["counted_toward_score"] is False
