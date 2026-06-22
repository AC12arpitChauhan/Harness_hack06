"""review_quality — reviewer count, approval depth, change-request cycles.

Emits the hard-blocker ``no_reviews`` signal for an un-reviewed non-trivial change
(see scoring/policies.py). PURE.
"""
from __future__ import annotations

from app.analyzers.base import Analyzer
from app.domain.models import AnalysisContext, PullRequest, ReviewState
from app.domain.signals import AnalysisSignal, Severity

DEFAULT_TRIVIAL_LINES = 10       # <= this many changed lines => an un-reviewed PR doesn't block
DEFAULT_THIN_REVIEW_REVIEWERS = 2  # fewer distinct reviewers than this => thin review


class ReviewQualityAnalyzer(Analyzer):
    name = "review_quality"

    def __init__(
        self,
        trivial_lines: int = DEFAULT_TRIVIAL_LINES,
        thin_review_reviewers: int = DEFAULT_THIN_REVIEW_REVIEWERS,
    ) -> None:
        self.trivial_lines = trivial_lines
        self.thin_review_reviewers = thin_review_reviewers

    def analyze(self, pr: PullRequest, context: AnalysisContext) -> list[AnalysisSignal]:
        reviews = context.reviews
        reviewers = {r.reviewer for r in reviews}
        approvers = {r.reviewer for r in reviews if r.state is ReviewState.APPROVED}
        change_cycles = sum(1 for r in reviews if r.state is ReviewState.CHANGES_REQUESTED)
        n = len(reviewers)
        total_changes = context.diff.total_changes
        signals: list[AnalysisSignal] = []

        if n == 0:
            if total_changes <= self.trivial_lines:
                signals.append(
                    AnalysisSignal(
                        analyzer=self.name,
                        name="no_review_trivial",
                        severity=Severity.INFO,
                        explanation=f"No review, but only {total_changes} lines changed (trivial).",
                        value=0.0,
                        exceeds_threshold=False,
                    )
                )
            else:
                signals.append(
                    AnalysisSignal(
                        analyzer=self.name,
                        name="no_reviews",
                        severity=Severity.CRITICAL,
                        explanation=f"No reviewers on a {total_changes}-line change.",
                        value=0.0,
                        threshold=1.0,
                        exceeds_threshold=True,
                    )
                )
            return signals

        if not approvers:
            signals.append(
                AnalysisSignal(
                    analyzer=self.name,
                    name="no_approval",
                    severity=Severity.HIGH,
                    explanation=f"{n} reviewer(s) but no approval.",
                    value=0.0,
                    threshold=1.0,
                    exceeds_threshold=True,
                )
            )

        if n < self.thin_review_reviewers:
            signals.append(
                AnalysisSignal(
                    analyzer=self.name,
                    name="single_reviewer",
                    severity=Severity.LOW,
                    explanation=f"Only {n} distinct reviewer (< {self.thin_review_reviewers}).",
                    value=float(n),
                    threshold=float(self.thin_review_reviewers),
                    exceeds_threshold=True,
                )
            )

        if approvers and n >= self.thin_review_reviewers:
            signals.append(
                AnalysisSignal(
                    analyzer=self.name,
                    name="well_reviewed",
                    severity=Severity.INFO,
                    explanation=f"{n} reviewers, {len(approvers)} approval(s).",
                    value=float(n),
                    exceeds_threshold=False,
                    metadata={"approvals": len(approvers), "change_request_cycles": change_cycles},
                )
            )
        return signals
