"""Score value objects — the deterministic output of the scoring engine.

PURE: stdlib + dataclasses only.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ScoreBreakdown:
    """Transparent record of HOW each score was computed.

    Persisted verbatim as analysis_scores.score_breakdown_json so a reviewer can
    answer "why is health_score 47?" from stored data alone — no recomputation.
    """

    weights: dict[str, float]              # health weights per analyzer
    risk_weights: dict[str, float]         # risk weights per analyzer
    severity_penalties: dict[str, float]   # severity -> points deducted
    analyzer_subscores: dict[str, float]   # per-analyzer 0..100 sub-score
    penalties: list[dict[str, Any]]        # one entry per signal that deducted points
    components: dict[str, Any]             # per-score arithmetic (base / deductions / final)

    def as_dict(self) -> dict[str, Any]:
        return {
            "weights": self.weights,
            "risk_weights": self.risk_weights,
            "severity_penalties": self.severity_penalties,
            "analyzer_subscores": self.analyzer_subscores,
            "penalties": self.penalties,
            "components": self.components,
        }


@dataclass(frozen=True)
class Score:
    """The four deterministic PR scores plus a full explanation.

    All scores are 0..100 floats. ``merge_readiness`` is a composite readiness
    score; ``blocking_reason`` is non-null when a hard blocker (see policies.py)
    forced the readiness score down.
    """

    health_score: float
    risk_score: float
    review_quality_score: float
    merge_readiness: float
    blocking_reason: str | None
    breakdown: ScoreBreakdown