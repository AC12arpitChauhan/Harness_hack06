"""Scoring engine: known signals -> known scores, plus determinism."""
from __future__ import annotations

from app.domain.signals import AnalysisSignal, Severity
from app.scoring.engine import ScoringEngine


def _sig(analyzer, name, severity):
    return AnalysisSignal(analyzer=analyzer, name=name, severity=severity, explanation="x")


def test_perfect_pr_scores_100():
    score = ScoringEngine().compute([])
    assert score.health_score == 100.0
    assert score.review_quality_score == 100.0
    assert score.merge_readiness == 100.0
    assert score.blocking_reason is None


def test_known_signals_known_scores():
    # CRITICAL merge_speed (penalty 50) only; other analyzers perfect.
    signals = [_sig("merge_speed", "fast_merge", Severity.CRITICAL)]
    score = ScoringEngine().compute(signals)
    # merge_speed subscore 50 -> health = .2*50 + .25*100 + .35*100 + .2*100 = 90
    assert score.health_score == 90.0
    assert score.review_quality_score == 100.0
    assert score.merge_readiness == 90.0  # no hard blocker
    assert score.blocking_reason is None


def test_hard_blocker_caps_merge_readiness():
    signals = [_sig("review_quality", "no_reviews", Severity.CRITICAL)]
    score = ScoringEngine().compute(signals)
    assert score.blocking_reason == "No approving review on a non-trivial change"
    assert score.merge_readiness == 15.0  # capped to BLOCKED_CAP
    # health itself is 0.35*50 + rest 100 -> 82.5
    assert score.health_score == 82.5


def test_breakdown_explains_every_signal():
    signals = [_sig("merge_speed", "fast_merge", Severity.CRITICAL)]
    bd = ScoringEngine().compute(signals).breakdown.as_dict()
    assert bd["analyzer_subscores"]["merge_speed"] == 50.0
    assert any(p["signal"] == "merge_speed.fast_merge" and p["penalty"] == 50.0 for p in bd["penalties"])
    assert "weights" in bd and "components" in bd


def test_determinism():
    signals = [
        _sig("merge_speed", "fast_merge", Severity.CRITICAL),
        _sig("change_size", "large_diff", Severity.HIGH),
    ]
    a = ScoringEngine().compute(signals)
    b = ScoringEngine().compute(signals)
    assert (a.health_score, a.merge_readiness) == (
        b.health_score,
        b.merge_readiness,
    )
