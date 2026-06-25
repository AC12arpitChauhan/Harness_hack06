"""Enabled-analyzer assembly. PURE: takes plain threshold args (no config import),
so the analyzers package stays free of external deps. The API layer passes
settings-derived values in.

Six analyzers are wired here. ticket_linkage emits a Jira-linkage signal but is
intentionally NOT in the scoring weight maps (scoring/engine.py), so its signals
surface in the breakdown without moving the deterministic scores. baseline_anomaly
is likewise outside the weight maps; the engine applies a separate bounded health
deduction for its repository-deviation signals (see scoring/engine.py).
"""
from __future__ import annotations

from app.analyzers.base import Analyzer
from app.analyzers.baseline_anomaly import BaselineAnomalyAnalyzer
from app.analyzers.change_size import (
    DEFAULT_CRITICAL_LINES,
    DEFAULT_HIGH_FILES,
    DEFAULT_HIGH_LINES,
    DEFAULT_MEDIUM_LINES,
    ChangeSizeAnalyzer,
)
from app.analyzers.ci_status import CiStatusAnalyzer
from app.analyzers.merge_speed import (
    DEFAULT_FAST_MERGE_MINUTES,
    DEFAULT_SLOW_MERGE_MINUTES,
    MergeSpeedAnalyzer,
)
from app.analyzers.review_quality import (
    DEFAULT_THIN_REVIEW_REVIEWERS,
    DEFAULT_TRIVIAL_LINES,
    ReviewQualityAnalyzer,
)
from app.analyzers.ticket_linkage import TicketLinkageAnalyzer


def enabled_analyzers(
    *,
    merge_fast_minutes: int = DEFAULT_FAST_MERGE_MINUTES,
    merge_slow_minutes: int = DEFAULT_SLOW_MERGE_MINUTES,
    change_medium_lines: int = DEFAULT_MEDIUM_LINES,
    change_high_lines: int = DEFAULT_HIGH_LINES,
    change_critical_lines: int = DEFAULT_CRITICAL_LINES,
    change_high_files: int = DEFAULT_HIGH_FILES,
    review_trivial_lines: int = DEFAULT_TRIVIAL_LINES,
    review_thin_reviewers: int = DEFAULT_THIN_REVIEW_REVIEWERS,
) -> list[Analyzer]:
    return [
        MergeSpeedAnalyzer(merge_fast_minutes, merge_slow_minutes),
        ChangeSizeAnalyzer(
            change_medium_lines, change_high_lines, change_critical_lines, change_high_files
        ),
        ReviewQualityAnalyzer(review_trivial_lines, review_thin_reviewers),
        CiStatusAnalyzer(),
        TicketLinkageAnalyzer(),
        BaselineAnomalyAnalyzer(),
    ]
