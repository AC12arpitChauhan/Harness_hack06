"""Deterministic, zero-cost narrator used when LLM_ENABLED=false.

Builds a stable narrative string straight from the scores/signals — no network,
so tests are reproducible. Output never affects scores.
"""
from __future__ import annotations

from app.domain.models import PullRequest
from app.domain.scores import Score
from app.domain.signals import AnalysisSignal, Severity
from app.llm.base import LLMProvider, Narrative

_SEVERITY_RANK = {
    Severity.CRITICAL: 0,
    Severity.HIGH: 1,
    Severity.MEDIUM: 2,
    Severity.LOW: 3,
    Severity.INFO: 4,
}


class TemplatedNarrator(LLMProvider):
    MODEL = "templated-fallback"

    def probe(self) -> str:
        """No network — the templated narrator is always live."""
        return self.MODEL

    def narrate(self, pr: PullRequest, signals: list[AnalysisSignal], score: Score) -> Narrative:
        issues = sorted(
            (s for s in signals if s.exceeds_threshold or s.severity is not Severity.INFO),
            key=lambda s: _SEVERITY_RANK[s.severity],
        )
        summary = (
            f'PR #{pr.number} "{pr.title}" scored {score.health_score:.0f}/100 health '
            f"(review quality {score.review_quality_score:.0f}, "
            f"merge readiness {score.merge_readiness:.0f})."
        )
        if score.blocking_reason:
            summary += f" Blocked: {score.blocking_reason}."

        if issues:
            top = issues[:3]
            recommendation = "Address the top issues:\n" + "\n".join(
                f"- {s.explanation}" for s in top
            )
        else:
            recommendation = "No blocking issues detected; the PR looks healthy."

        return Narrative(summary=summary, recommendation=recommendation, model=self.MODEL)
