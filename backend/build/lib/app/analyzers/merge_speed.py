"""merge_speed — open->merge duration vs thresholds.

A very fast merge is a rubber-stamp risk (little time for real review); a moderate
one is a softer concern; anything slower (or an unmerged PR) is informational.
PURE: stdlib + domain only.
"""
from __future__ import annotations

from app.analyzers.base import Analyzer
from app.domain.models import AnalysisContext, PullRequest
from app.domain.signals import AnalysisSignal, Severity

DEFAULT_FAST_MERGE_MINUTES = 15
DEFAULT_SLOW_MERGE_MINUTES = 60


class MergeSpeedAnalyzer(Analyzer):
    name = "merge_speed"

    def __init__(
        self,
        fast_merge_minutes: int = DEFAULT_FAST_MERGE_MINUTES,
        slow_merge_minutes: int = DEFAULT_SLOW_MERGE_MINUTES,
    ) -> None:
        self.fast = fast_merge_minutes
        self.slow = slow_merge_minutes

    def analyze(self, pr: PullRequest, context: AnalysisContext) -> list[AnalysisSignal]:
        if pr.merged_at is None or pr.opened_at is None:
            return [
                AnalysisSignal(
                    analyzer=self.name,
                    name="not_merged",
                    severity=Severity.INFO,
                    explanation="PR is not merged yet; merge speed not applicable.",
                )
            ]

        minutes = round((pr.merged_at - pr.opened_at).total_seconds() / 60.0, 1)

        if minutes < self.fast:
            severity, name = Severity.CRITICAL, "fast_merge"
            explanation = (
                f"Merged in {minutes:.0f} min (< {self.fast} min) — too fast for meaningful review."
            )
            exceeds = True
        elif minutes < self.slow:
            severity, name = Severity.HIGH, "fast_merge"
            explanation = (
                f"Merged in {minutes:.0f} min (< {self.slow} min) — quick turnaround, limited review window."
            )
            exceeds = True
        else:
            severity, name = Severity.INFO, "healthy_pace"
            explanation = f"Merged in {minutes:.0f} min — healthy review window."
            exceeds = False

        return [
            AnalysisSignal(
                analyzer=self.name,
                name=name,
                severity=severity,
                explanation=explanation,
                value=minutes,
                threshold=float(self.fast),
                exceeds_threshold=exceeds,
                metadata={"duration_minutes": minutes},
            )
        ]
