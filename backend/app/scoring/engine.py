"""Deterministic scoring engine.

PURE: stdlib + domain only. Same signals in => same Score out, always. The LLM
never touches anything here.

HOW THE SCORES ARE COMPUTED (the one readable formula)
------------------------------------------------------
1. Each signal carries a Severity. Severity maps to a penalty in points:
       INFO 0 · LOW 5 · MEDIUM 15 · HIGH 30 · CRITICAL 50
2. Each analyzer gets a sub-score:
       subscore[a] = max(0, 100 - sum(penalty of a's signals))
3. health_score = Σ HEALTH_WEIGHTS[a] * subscore[a]          (weighted "goodness")
4. review_quality_score = subscore["review_quality"]         (the standalone lens)
5. Repository-baseline deduction (statistical anomaly). The baseline_anomaly
   analyzer (NOT in the weight maps) flags metrics that deviate from the repo's
   own history as z-scores. We sum the penalties of those signals, cap the total
   at BASELINE_MAX_PENALTY, and subtract it from health_score (floored at 0).
   This is 0 when a repo lacks history or the PR is within norms, so it never
   perturbs the deterministic core in those cases.
6. merge_readiness:
       blockers = policies.hard_blockers(signals)
       if blockers: merge_readiness = min(health_score, BLOCKED_CAP); reason set
       else:        merge_readiness = health_score;                    reason None

Weights sum to 1.0 so the weighted mean lands in [0, 100]; the bounded baseline
deduction keeps the adjusted health in range too. All knobs below are the
documented single source of truth; config.py re-exposes them for env tuning.
"""
from __future__ import annotations

from collections.abc import Iterable

from app.domain.scores import Score, ScoreBreakdown
from app.domain.signals import AnalysisSignal, Severity
from app.scoring import policies

# --- Tunable constants (single source of truth) --------------------------
DEFAULT_SEVERITY_PENALTIES: dict[Severity, float] = {
    Severity.INFO: 0.0,
    Severity.LOW: 5.0,
    Severity.MEDIUM: 15.0,
    Severity.HIGH: 30.0,
    Severity.CRITICAL: 50.0,
}

DEFAULT_HEALTH_WEIGHTS: dict[str, float] = {
    "merge_speed": 0.20,
    "change_size": 0.25,
    "review_quality": 0.35,
    "ci_status": 0.20,
}

DEFAULT_BLOCKED_CAP: float = 15.0  # merge_readiness ceiling when a hard blocker fires

# Repository-baseline anomaly: the analyzer whose signals drive the deduction, and
# the maximum points a PR can lose to repo-relative anomalies (keeps a multi-metric
# outlier from dominating the weighted score).
BASELINE_ANALYZER: str = "baseline_anomaly"
DEFAULT_BASELINE_MAX_PENALTY: float = 20.0


def _round(value: float) -> float:
    return round(value, 2)


class ScoringEngine:
    """Combines analyzer signals into the four deterministic scores."""

    def __init__(
        self,
        health_weights: dict[str, float] | None = None,
        severity_penalties: dict[Severity, float] | None = None,
        blocked_cap: float = DEFAULT_BLOCKED_CAP,
        baseline_max_penalty: float = DEFAULT_BASELINE_MAX_PENALTY,
    ) -> None:
        self.health_weights = dict(health_weights or DEFAULT_HEALTH_WEIGHTS)
        self.severity_penalties = dict(severity_penalties or DEFAULT_SEVERITY_PENALTIES)
        self.blocked_cap = blocked_cap
        self.baseline_max_penalty = baseline_max_penalty

    def compute(self, signals: Iterable[AnalysisSignal]) -> Score:
        signals = list(signals)

        # Per-analyzer penalty totals. Seed every weighted analyzer at 0 so a
        # silent analyzer scores a perfect sub-score rather than vanishing.
        penalties: dict[str, float] = {a: 0.0 for a in self.health_weights}
        penalty_records: list[dict[str, object]] = []
        for sig in signals:
            pts = self.severity_penalties.get(sig.severity, 0.0)
            counted = sig.analyzer in penalties
            if counted:
                penalties[sig.analyzer] += pts
            penalty_records.append(
                {
                    "signal": sig.key,
                    "analyzer": sig.analyzer,
                    "severity": sig.severity.value,
                    "penalty": pts,
                    "counted_toward_score": counted,
                }
            )

        subscores = {a: max(0.0, 100.0 - p) for a, p in penalties.items()}

        base_health = _round(
            sum(self.health_weights[a] * subscores[a] for a in self.health_weights)
        )
        review_quality = _round(subscores.get("review_quality", 100.0))

        # Repository-baseline deduction: bounded penalty from baseline_anomaly signals.
        # 0 when the repo lacks history or the PR is within norms, so the deterministic
        # core is untouched in those cases.
        baseline_penalty = _round(
            min(
                self.baseline_max_penalty,
                sum(
                    self.severity_penalties.get(sig.severity, 0.0)
                    for sig in signals
                    if sig.analyzer == BASELINE_ANALYZER
                ),
            )
        )
        health = _round(max(0.0, base_health - baseline_penalty))

        blockers = policies.hard_blockers(signals)
        if blockers:
            blocking_reason: str | None = "; ".join(blockers)
            merge_readiness = _round(min(health, self.blocked_cap))
        else:
            blocking_reason = None
            merge_readiness = health

        breakdown = ScoreBreakdown(
            weights=dict(self.health_weights),
            severity_penalties={s.value: p for s, p in self.severity_penalties.items()},
            analyzer_subscores={a: _round(s) for a, s in subscores.items()},
            penalties=penalty_records,
            components={
                "health": {
                    "weights": self.health_weights,
                    "base_value": base_health,
                    "baseline_penalty": baseline_penalty,
                    "value": health,
                },
                "review_quality": {"source": "review_quality", "value": review_quality},
                "baseline_adjustment": {
                    "analyzer": BASELINE_ANALYZER,
                    "penalty": baseline_penalty,
                    "max_penalty": self.baseline_max_penalty,
                },
                "merge_readiness": {
                    "base_health": health,
                    "blocked_cap": self.blocked_cap,
                    "blockers": blockers,
                    "value": merge_readiness,
                },
            },
        )

        return Score(
            health_score=health,
            review_quality_score=review_quality,
            merge_readiness=merge_readiness,
            blocking_reason=blocking_reason,
            breakdown=breakdown,
        )
