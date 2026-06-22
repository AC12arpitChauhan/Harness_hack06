"""Merge-readiness policy: the single place that decides what HARD-BLOCKS a merge.

PURE: stdlib + domain only. A hard blocker caps merge_readiness to a near-zero
floor regardless of the other scores. Blockers are matched by signal key
(``analyzer.name``) so the analyzers stay the source of truth for *detecting* the
condition and this module stays the source of truth for *policy*.
"""
from __future__ import annotations

from collections.abc import Iterable

from app.domain.signals import AnalysisSignal

# signal key -> human-readable blocking reason
BLOCKING_SIGNALS: dict[str, str] = {
    "ci_status.required_failing": "Required CI check is failing",
    "ci_status.merged_despite_failure": "Merged despite a failing required CI check",
    "review_quality.no_reviews": "No approving review on a non-trivial change",
}


def hard_blockers(signals: Iterable[AnalysisSignal]) -> list[str]:
    """Return the ordered, de-duplicated list of hard-blocker reasons present."""
    reasons: list[str] = []
    seen: set[str] = set()
    for signal in signals:
        reason = BLOCKING_SIGNALS.get(signal.key)
        if reason and reason not in seen:
            seen.add(reason)
            reasons.append(reason)
    return reasons
