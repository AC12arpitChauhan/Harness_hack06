"""Anthropic-backed narrator (used when LLM_ENABLED=true).

Simplest messages.create call: model + max_tokens + system + messages. On the
Opus-4.8 family this minimal shape is also the correct one — temperature/top_p/
thinking budgets are removed there, so we pass none of them.
"""
from __future__ import annotations

import anthropic

from app.domain.models import PullRequest
from app.domain.scores import Score
from app.domain.signals import AnalysisSignal
from app.llm import prompts
from app.llm.base import LLMProvider, Narrative


class AnthropicNarrator(LLMProvider):
    def __init__(self, api_key: str, model: str, max_tokens: int = 1024) -> None:
        # Anthropic() reads ANTHROPIC_API_KEY from env; pass explicitly when provided.
        self._client = anthropic.Anthropic(api_key=api_key) if api_key else anthropic.Anthropic()
        self.model = model
        self.max_tokens = max_tokens

    def narrate(self, pr: PullRequest, signals: list[AnalysisSignal], score: Score) -> Narrative:
        resp = self._client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            system=prompts.SYSTEM,
            messages=[{"role": "user", "content": prompts.build_user(pr, signals, score)}],
        )
        text = "".join(b.text for b in resp.content if getattr(b, "type", None) == "text")
        summary, recommendation = _split_sections(text)
        return Narrative(summary=summary, recommendation=recommendation, model=resp.model or self.model)

    def probe(self) -> str:
        """Tiny round-trip to verify the API key/model; returns the model id."""
        resp = self._client.messages.create(
            model=self.model,
            max_tokens=16,
            messages=[{"role": "user", "content": "Reply with the single word: OK"}],
        )
        return resp.model or self.model


def _split_sections(text: str) -> tuple[str, str]:
    """Parse 'SUMMARY: ... RECOMMENDATION: ...'; degrade gracefully if unformatted."""
    if "RECOMMENDATION:" in text:
        head, rec = text.split("RECOMMENDATION:", 1)
        summary = head.replace("SUMMARY:", "").strip()
        return summary, rec.strip()
    return text.replace("SUMMARY:", "").strip(), ""
