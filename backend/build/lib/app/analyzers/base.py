"""Analyzer port. PURE: abc + domain only — analyzers never perform I/O.

The service fetches everything once and hands it in via AnalysisContext, so each
analyze() is a pure function of (pr, context) -> signals.
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from app.domain.models import AnalysisContext, PullRequest
from app.domain.signals import AnalysisSignal


class Analyzer(ABC):
    #: stable analyzer identifier; also the prefix of every signal key it emits
    name: str

    @abstractmethod
    def analyze(self, pr: PullRequest, context: AnalysisContext) -> list[AnalysisSignal]:
        """Return zero or more deterministic signals for this PR."""
        raise NotImplementedError
