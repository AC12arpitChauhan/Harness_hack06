"""Amazon Bedrock narrator (used when LLM_BACKEND=bedrock).

Authenticates with a Bedrock API key (bearer token) — the anthropic SDK sends it
as ``Authorization: Bearer <key>``, so no AWS access-key/secret or SigV4 is needed.
Model ids are Bedrock-style (``anthropic.`` prefixed, possibly an inference-profile
id like ``us.anthropic.claude-...``). Narration only — never touches scores.
"""
from __future__ import annotations

import anthropic

from app.domain.models import PullRequest
from app.domain.scores import Score
from app.domain.signals import AnalysisSignal
from app.llm import prompts
from app.llm.anthropic_provider import _split_sections
from app.llm.base import LLMProvider, Narrative


class BedrockNarrator(LLMProvider):
    def __init__(self, region: str, model: str, api_key: str, max_tokens: int = 1024) -> None:
        # api_key is the Bedrock API key (bearer); region picks the bedrock-runtime endpoint.
        self._client = anthropic.AnthropicBedrock(aws_region=region, api_key=api_key)
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
        return Narrative(summary=summary, recommendation=recommendation, model=getattr(resp, "model", self.model))

    def probe(self) -> str:
        """Tiny round-trip to verify Bedrock auth/model/region; returns the model id."""
        resp = self._client.messages.create(
            model=self.model,
            max_tokens=16,
            messages=[{"role": "user", "content": "Reply with the single word: OK"}],
        )
        return getattr(resp, "model", self.model)

    def suggest_fix(self, failing_checks, pr_title=None, log_text=None) -> str:
        resp = self._client.messages.create(
            model=self.model,
            max_tokens=max(self.max_tokens, 1500),
            system=prompts.SUGGEST_FIX_SYSTEM,
            messages=[
                {"role": "user", "content": prompts.build_fix_user(failing_checks, pr_title, log_text)}
            ],
        )
        text = "".join(b.text for b in resp.content if getattr(b, "type", None) == "text").strip()
        return text or prompts.templated_fix(failing_checks, pr_title)
