"""Full analyze->score pipeline (all four analyzers + engine), no network/DB."""
from __future__ import annotations

from app.analyzers.registry import enabled_analyzers
from app.domain.models import CheckStatus
from app.scoring.engine import ScoringEngine
from tests.unit._builders import check, make_ctx, make_diff, make_pr


def test_terrible_pr_scores_low_and_is_blocked():
    pr = make_pr(merged=True, merged_after_min=3)  # rubber-stamp speed
    ctx = make_ctx(
        diff=make_diff(additions=1500, deletions=0, files_changed=40),  # huge
        reviews=[],  # unreviewed
        checks=[check("build", CheckStatus.FAILURE, required=True)],  # required CI failing
    )
    signals = [s for a in enabled_analyzers() for s in a.analyze(pr, ctx)]
    score = ScoringEngine().compute(signals)

    assert score.health_score < 40
    assert score.risk_score > 50
    assert score.merge_readiness == 15.0  # capped by hard blockers
    assert score.blocking_reason is not None
    for fragment in ("Required CI", "Merged despite", "No approving"):
        assert fragment in score.blocking_reason


def test_excellent_pr_scores_high_and_ready():
    from app.domain.models import ReviewState
    from tests.unit._builders import review

    pr = make_pr(merged=True, merged_after_min=600)  # healthy pace
    ctx = make_ctx(
        diff=make_diff(additions=40, deletions=10, files_changed=3),
        reviews=[review("bob", ReviewState.APPROVED), review("cara", ReviewState.APPROVED)],
        checks=[check("build", CheckStatus.SUCCESS, required=True)],
    )
    signals = [s for a in enabled_analyzers() for s in a.analyze(pr, ctx)]
    score = ScoringEngine().compute(signals)

    assert score.health_score == 100.0
    assert score.risk_score == 0.0
    assert score.merge_readiness == 100.0
    assert score.blocking_reason is None
