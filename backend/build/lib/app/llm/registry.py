"""Narrator selection behind the LLM_ENABLED toggle.

LLM_ENABLED=false (or no API key) -> deterministic TemplatedNarrator.
LLM_ENABLED=true with a key   -> AnthropicNarrator.
Either way the returned narrative is stored in pr_narratives; scores are unaffected.
"""
from __future__ import annotations

import logging

from app.config import Settings
from app.llm.base import LLMProvider
from app.llm.templated_fallback import TemplatedNarrator

logger = logging.getLogger("pr_health.llm")


def build_narrator(settings: Settings) -> LLMProvider:
    if not settings.llm_enabled:
        return TemplatedNarrator()

    if settings.llm_backend == "bedrock":
        key = settings.bedrock_api_key or settings.anthropic_api_key
        if not key:
            logger.warning("LLM_BACKEND=bedrock but no Bedrock API key; using templated fallback.")
            return TemplatedNarrator()
        from app.llm.bedrock_provider import BedrockNarrator  # lazy: needs anthropic[bedrock]

        return BedrockNarrator(
            settings.bedrock_region, settings.bedrock_model, key, settings.llm_max_tokens
        )

    if not settings.anthropic_api_key:
        logger.warning("LLM_ENABLED=true but ANTHROPIC_API_KEY is empty; using templated fallback.")
        return TemplatedNarrator()
    from app.llm.anthropic_provider import AnthropicNarrator  # lazy

    return AnthropicNarrator(
        settings.anthropic_api_key, settings.anthropic_model, settings.llm_max_tokens
    )
