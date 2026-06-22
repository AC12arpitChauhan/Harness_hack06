"""LLMProvider port + Narrative value object.

A narrator reads the PR and its ALREADY-COMPUTED scores/signals and produces human
prose. It returns NO scores — the deterministic engine is the sole score authority.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from app.domain.models import PullRequest
from app.domain.scores import Score
from app.domain.signals import AnalysisSignal


@dataclass(frozen=True)
class Narrative:
    summary: str
    recommendation: str
    model: str  # which narrator produced this (e.g. "templated-fallback" or a model id)


class LLMProvider(ABC):
    @abstractmethod
    def narrate(
        self, pr: PullRequest, signals: list[AnalysisSignal], score: Score
    ) -> Narrative:
        """Return a human-readable narrative. MUST NOT compute or alter scores."""
        raise NotImplementedError
