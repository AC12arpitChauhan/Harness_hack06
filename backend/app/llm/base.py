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

    def probe(self) -> str:
        """Liveness check for the narration path. Real LLM providers override this
        to make a tiny API call and return the responding model id (raising on
        failure, so an operator sees the true error); no-network providers just
        return their model tag."""
        return getattr(self, "model", "unknown")

    def suggest_fix(
        self,
        failing_checks: list[dict],
        pr_title: str | None = None,
        log_text: str | None = None,
    ) -> str:
        """Suggest how to make failing checks pass. The default returns deterministic
        templated guidance (used by the no-network narrator); LLM providers override
        this to return a model-generated, cause-specific suggestion."""
        from app.llm import prompts

        return prompts.templated_fix(failing_checks, pr_title)
