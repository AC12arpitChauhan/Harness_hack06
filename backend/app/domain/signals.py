"""Analysis signals — the deterministic observations analyzers emit.

PURE: stdlib + dataclasses only. No I/O, no external packages.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class Severity(str, Enum):
    """Ordered severity of a signal. Drives the deterministic scoring penalty.

    INFO     — observation only, zero health impact.
    LOW      — minor concern.
    MEDIUM   — notable concern.
    HIGH     — serious concern.
    CRITICAL — severe; candidate hard-blocker for merge readiness (see scoring/policies.py).

    Stored verbatim (the string value) in analysis_signals.severity.
    """

    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass(frozen=True)
class AnalysisSignal:
    """One deterministic observation produced by an analyzer.

    Same inputs always produce the same signal. Carries the measured ``value``,
    the ``threshold`` it was compared against, whether it ``exceeds_threshold``,
    a ``severity``, and a human-readable ``explanation``. ``metadata`` holds
    analyzer-specific extras (persisted as metadata_json).
    """

    analyzer: str
    name: str
    severity: Severity
    explanation: str
    value: float | None = None
    threshold: float | None = None
    exceeds_threshold: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def key(self) -> str:
        """Stable dotted id persisted as signal_name, e.g. ``merge_speed.fast_merge``."""
        return f"{self.analyzer}.{self.name}"