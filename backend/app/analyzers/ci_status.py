"""ci_status — required checks failing / merged despite failure / pending.

Emits the hard-blocker signals ``required_failing`` and ``merged_despite_failure``
(see scoring/policies.py). PURE.
"""
from __future__ import annotations

from app.analyzers.base import Analyzer
from app.domain.models import AnalysisContext, CheckStatus, PullRequest
from app.domain.signals import AnalysisSignal, Severity


class CiStatusAnalyzer(Analyzer):
    name = "ci_status"

    def analyze(self, pr: PullRequest, context: AnalysisContext) -> list[AnalysisSignal]:
        checks = context.checks
        if not checks:
            return [
                AnalysisSignal(
                    analyzer=self.name,
                    name="no_checks",
                    severity=Severity.INFO,
                    explanation="No CI checks reported for the head commit.",
                )
            ]

        required = [c for c in checks if c.required]
        failing_required = [c for c in required if c.status is CheckStatus.FAILURE]
        failing_optional = [c for c in checks if not c.required and c.status is CheckStatus.FAILURE]
        pending_required = [c for c in required if c.status is CheckStatus.PENDING]
        signals: list[AnalysisSignal] = []

        if failing_required:
            names = ", ".join(c.name for c in failing_required)
            signals.append(
                AnalysisSignal(
                    analyzer=self.name,
                    name="required_failing",
                    severity=Severity.CRITICAL,
                    explanation=f"Required check(s) failing: {names}.",
                    value=float(len(failing_required)),
                    threshold=0.0,
                    exceeds_threshold=True,
                )
            )
            if pr.is_merged:
                signals.append(
                    AnalysisSignal(
                        analyzer=self.name,
                        name="merged_despite_failure",
                        severity=Severity.CRITICAL,
                        explanation=f"PR was MERGED despite failing required check(s): {names}.",
                        value=float(len(failing_required)),
                        threshold=0.0,
                        exceeds_threshold=True,
                        metadata={"failing_checks": [c.name for c in failing_required]},
                    )
                )
            return signals

        if failing_optional:
            signals.append(
                AnalysisSignal(
                    analyzer=self.name,
                    name="optional_failing",
                    severity=Severity.MEDIUM,
                    explanation=f"{len(failing_optional)} non-required check(s) failing.",
                    value=float(len(failing_optional)),
                    exceeds_threshold=True,
                )
            )
            return signals

        if pending_required:
            signals.append(
                AnalysisSignal(
                    analyzer=self.name,
                    name="checks_pending",
                    severity=Severity.LOW,
                    explanation=f"{len(pending_required)} required check(s) still pending.",
                    value=float(len(pending_required)),
                    exceeds_threshold=True,
                )
            )
            return signals

        return [
            AnalysisSignal(
                analyzer=self.name,
                name="checks_passing",
                severity=Severity.INFO,
                explanation="All required checks passing.",
                exceeds_threshold=False,
            )
        ]
