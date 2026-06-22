"""change_size — (additions + deletions) and files changed vs thresholds.

Large PRs are harder to review well; very large PRs are a real risk. PURE.
"""
from __future__ import annotations

from app.analyzers.base import Analyzer
from app.domain.models import AnalysisContext, PullRequest
from app.domain.signals import AnalysisSignal, Severity

DEFAULT_MEDIUM_LINES = 250
DEFAULT_HIGH_LINES = 500
DEFAULT_CRITICAL_LINES = 1000
DEFAULT_HIGH_FILES = 30


class ChangeSizeAnalyzer(Analyzer):
    name = "change_size"

    def __init__(
        self,
        medium_lines: int = DEFAULT_MEDIUM_LINES,
        high_lines: int = DEFAULT_HIGH_LINES,
        critical_lines: int = DEFAULT_CRITICAL_LINES,
        high_files: int = DEFAULT_HIGH_FILES,
    ) -> None:
        self.medium_lines = medium_lines
        self.high_lines = high_lines
        self.critical_lines = critical_lines
        self.high_files = high_files

    def analyze(self, pr: PullRequest, context: AnalysisContext) -> list[AnalysisSignal]:
        total = context.diff.total_changes
        files = context.diff.files_changed
        signals: list[AnalysisSignal] = []

        if total >= self.critical_lines:
            severity, exceeds, threshold = Severity.CRITICAL, True, self.critical_lines
        elif total >= self.high_lines:
            severity, exceeds, threshold = Severity.HIGH, True, self.high_lines
        elif total >= self.medium_lines:
            severity, exceeds, threshold = Severity.MEDIUM, True, self.medium_lines
        else:
            severity, exceeds, threshold = Severity.INFO, False, self.medium_lines

        name = "large_diff" if exceeds else "small_diff"
        signals.append(
            AnalysisSignal(
                analyzer=self.name,
                name=name,
                severity=severity,
                explanation=f"{total} lines changed across {files} files.",
                value=float(total),
                threshold=float(threshold),
                exceeds_threshold=exceeds,
                metadata={"additions": context.diff.additions, "deletions": context.diff.deletions, "files": files},
            )
        )

        if files >= self.high_files:
            signals.append(
                AnalysisSignal(
                    analyzer=self.name,
                    name="many_files",
                    severity=Severity.MEDIUM,
                    explanation=f"{files} files touched (>= {self.high_files}); broad blast radius.",
                    value=float(files),
                    threshold=float(self.high_files),
                    exceeds_threshold=True,
                )
            )
        return signals
