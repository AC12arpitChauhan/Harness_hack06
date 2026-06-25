"""Baseline anomaly — is this PR statistically abnormal *for this repository*?

Where the other analyzers compare a PR against fixed thresholds, this one compares
it against the repo's own history (mean/std of prior PRs) and flags deviations as
z-scores. It only fires in the *risky* direction of each metric:

* change size  — much LARGER than the repo norm  (z > 0)
* reviewers    — much FEWER  than the repo norm  (z < 0)
* merge speed  — much FASTER  than the repo norm  (z < 0, merged PRs only)

The repo baseline is computed by the service from the database and injected via
``AnalysisContext.baseline`` (None until there is enough history). The scoring
engine applies a small, bounded deduction for the signals this analyzer emits — see
app.scoring.engine — so a genuine outlier nudges the score without ever dominating it.

PURE: stdlib + domain only (the I/O to build the baseline happens in the service).
"""
from __future__ import annotations

from app.analyzers.base import Analyzer
from app.domain.models import AnalysisContext, PullRequest
from app.domain.signals import AnalysisSignal, Severity
from app.scoring.baseline import severity_for_z, zscore


def _distinct_reviewers(context: AnalysisContext) -> int:
    return len({r.reviewer for r in context.reviews if r.reviewer})


def _merge_minutes(pr: PullRequest) -> float | None:
    if pr.opened_at is None or pr.merged_at is None:
        return None
    minutes = (pr.merged_at - pr.opened_at).total_seconds() / 60.0
    return minutes if minutes >= 0 else None


class BaselineAnomalyAnalyzer(Analyzer):
    """Flags PRs that deviate from their repository's historical norms."""

    name = "baseline_anomaly"

    def analyze(self, pr: PullRequest, context: AnalysisContext) -> list[AnalysisSignal]:
        baseline = context.baseline
        if baseline is None or not baseline.has_any:
            return [
                AnalysisSignal(
                    analyzer=self.name,
                    name="insufficient_history",
                    severity=Severity.INFO,
                    explanation=(
                        "Not enough repository history yet to judge whether this PR is "
                        "abnormal — baseline anomaly scoring is inactive for this repo."
                    ),
                    exceeds_threshold=False,
                    metadata={"reason": "insufficient_history"},
                )
            ]

        signals: list[AnalysisSignal] = []

        # change size — risky when much LARGER than the repo norm
        if baseline.size is not None:
            value = float(context.diff.total_changes)
            z = zscore(value, baseline.size)
            sev = severity_for_z(abs(z)) if z > 0 else None
            if sev is not None:
                signals.append(
                    self._outlier(
                        name="size_outlier",
                        severity=sev,
                        value=value,
                        mean=baseline.size.mean,
                        z=z,
                        explanation=(
                            f"Changeset is {value:.0f} lines — {z:.1f}σ above this repo's "
                            f"average of {baseline.size.mean:.0f} (n={baseline.size.n})."
                        ),
                    )
                )

        # reviewer participation — risky when much FEWER reviewers than the repo norm
        if baseline.reviewers is not None:
            value = float(_distinct_reviewers(context))
            z = zscore(value, baseline.reviewers)
            sev = severity_for_z(abs(z)) if z < 0 else None
            if sev is not None:
                signals.append(
                    self._outlier(
                        name="thin_review_outlier",
                        severity=sev,
                        value=value,
                        mean=baseline.reviewers.mean,
                        z=z,
                        explanation=(
                            f"{value:.0f} distinct reviewer(s) — {abs(z):.1f}σ below this "
                            f"repo's average of {baseline.reviewers.mean:.1f} (n={baseline.reviewers.n})."
                        ),
                    )
                )

        # merge speed — risky when merged much FASTER than the repo norm
        if baseline.merge_minutes is not None:
            mins = _merge_minutes(pr)
            if mins is not None:
                z = zscore(mins, baseline.merge_minutes)
                sev = severity_for_z(abs(z)) if z < 0 else None
                if sev is not None:
                    signals.append(
                        self._outlier(
                            name="fast_merge_outlier",
                            severity=sev,
                            value=mins,
                            mean=baseline.merge_minutes.mean,
                            z=z,
                            explanation=(
                                f"Merged in {mins:.0f} min — {abs(z):.1f}σ faster than this "
                                f"repo's average of {baseline.merge_minutes.mean:.0f} min "
                                f"(n={baseline.merge_minutes.n})."
                            ),
                        )
                    )

        if signals:
            return signals

        return [
            AnalysisSignal(
                analyzer=self.name,
                name="within_norms",
                severity=Severity.INFO,
                explanation="PR size, reviewer count and merge speed are within this repo's normal range.",
                exceeds_threshold=False,
                metadata={},
            )
        ]

    def _outlier(
        self,
        *,
        name: str,
        severity: Severity,
        value: float,
        mean: float,
        z: float,
        explanation: str,
    ) -> AnalysisSignal:
        return AnalysisSignal(
            analyzer=self.name,
            name=name,
            severity=severity,
            explanation=explanation,
            value=round(value, 2),
            threshold=round(mean, 2),
            exceeds_threshold=True,
            metadata={"z_score": round(z, 2), "baseline_mean": round(mean, 2)},
        )
