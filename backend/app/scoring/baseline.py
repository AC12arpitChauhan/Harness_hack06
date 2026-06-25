"""Repository-aware statistical baselines (z-score anomaly detection).

PURE: stdlib (``statistics``) + domain value objects only. No I/O, no config.

The idea (the next rung above a fixed-threshold rule): instead of asking "is this
PR big?" we ask "is this PR *abnormal for THIS repository*?". A 1000-line change is
routine in an infra repo and alarming in a small frontend repo, so every repo gets
its own mean/std and we measure each PR's deviation as a z-score::

    z = (x - mean) / std

The service computes a RepoBaseline from the repo's prior PRs (current PR excluded)
and hands it to the baseline_anomaly analyzer via AnalysisContext. This module owns
two pure pieces: building the baseline from raw samples, and mapping a z magnitude
to a Severity. Nothing here touches the database or the network.
"""
from __future__ import annotations

import statistics

from app.domain.models import MetricBaseline, RepoBaseline
from app.domain.signals import Severity

# --- Tunable constants (documented single source of truth) ---------------
# Need at least this many historical samples for a metric before we trust its
# baseline; below this we stay silent rather than flag noise on a cold repo.
MIN_HISTORY: int = 5

# z-score magnitude thresholds -> severity. Deliberately conservative: a PR has to
# be a genuine outlier (>=1.5 sigma) before it costs anything.
Z_LOW: float = 1.5
Z_MEDIUM: float = 2.0
Z_HIGH: float = 3.0


def _metric(samples: list[float]) -> MetricBaseline | None:
    """Build one metric's baseline, or None if there isn't enough usable history.

    Uses population std (pstdev): we're describing the repo's own distribution, not
    inferring about a wider population. A zero-spread metric (everyone identical) is
    treated as no-baseline so we never divide by zero or flag a constant as anomalous.
    """
    if len(samples) < MIN_HISTORY:
        return None
    mean = statistics.fmean(samples)
    std = statistics.pstdev(samples)
    if std <= 0.0:
        return None
    return MetricBaseline(n=len(samples), mean=round(mean, 4), std=round(std, 4))


def build_repo_baseline(
    sizes: list[float],
    reviewers: list[float],
    merge_minutes: list[float],
) -> RepoBaseline | None:
    """Assemble per-metric baselines from raw history samples.

    Returns None when no metric has enough history (a brand-new / barely-used repo),
    so the analyzer can short-circuit to a single "insufficient history" observation.
    """
    baseline = RepoBaseline(
        size=_metric(sizes),
        reviewers=_metric(reviewers),
        merge_minutes=_metric(merge_minutes),
    )
    return baseline if baseline.has_any else None


def zscore(value: float, metric: MetricBaseline) -> float:
    """Signed deviation of ``value`` from the metric mean, in standard deviations."""
    return (value - metric.mean) / metric.std


def severity_for_z(z_abs: float) -> Severity | None:
    """Map an absolute z-score to a Severity, or None when within normal range."""
    if z_abs >= Z_HIGH:
        return Severity.HIGH
    if z_abs >= Z_MEDIUM:
        return Severity.MEDIUM
    if z_abs >= Z_LOW:
        return Severity.LOW
    return None
