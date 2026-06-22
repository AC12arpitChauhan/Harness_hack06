"""Prompt templates for the Anthropic narrator.

The system prompt forbids inventing or recomputing metrics: the model only
narrates the numbers it is handed.
"""
from __future__ import annotations

from app.domain.models import PullRequest
from app.domain.scores import Score
from app.domain.signals import AnalysisSignal, Severity

SYSTEM = (
    "You are a senior engineer writing a concise pull-request health review for a teammate. "
    "You are given pre-computed scores and signals. NEVER invent, recompute, or contradict any "
    "score or metric — describe only what you are given. Be specific and actionable. "
    "Output EXACTLY two sections in this format:\n"
    "SUMMARY: <2-3 sentences>\n"
    "RECOMMENDATION: <1-3 short, actionable bullet points, each on its own line starting with '- '>"
)


def build_user(pr: PullRequest, signals: list[AnalysisSignal], score: Score) -> str:
    notable = [s for s in signals if s.severity is not Severity.INFO or s.exceeds_threshold]
    notable.sort(key=lambda s: s.severity.value)
    signal_lines = "\n".join(
        f"- [{s.severity.value.upper()}] {s.key}: {s.explanation}" for s in notable
    ) or "- (no notable issues)"
    blocker = score.blocking_reason or "none"
    return (
        f"PR #{pr.number}: {pr.title}\n"
        f"Author: {pr.author} | {pr.source_branch} -> {pr.target_branch} | state: {pr.state.value}\n\n"
        f"Scores (0-100, do not change these):\n"
        f"- health: {score.health_score}\n"
        f"- risk: {score.risk_score}\n"
        f"- review_quality: {score.review_quality_score}\n"
        f"- merge_readiness: {score.merge_readiness}\n"
        f"- hard blocker: {blocker}\n\n"
        f"Signals:\n{signal_lines}\n"
    )
