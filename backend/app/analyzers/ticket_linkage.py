"""Ticket linkage — is the PR traceable to a Jira ticket?

The Jira-key regex helper is used by the provider mappers to populate
``PullRequest.jira_issue_id`` when a key is parseable from title/description/branch.
This analyzer surfaces a signal for that linkage: a LOW signal when no ticket is
linked (untraceable change), an INFO signal when one is.

IMPORTANT — surface-only by design: ``ticket_linkage`` is deliberately NOT in the
scoring weight map (scoring/engine.py DEFAULT_HEALTH_WEIGHTS), so these signals
appear in the signal list / severity breakdown / top-signals but do NOT move the
deterministic health/review_quality/merge_readiness scores. The engine records
them with ``counted_toward_score=False``.

PURE: stdlib + domain only.
"""
from __future__ import annotations

import re

from app.analyzers.base import Analyzer
from app.domain.models import AnalysisContext, PullRequest
from app.domain.signals import AnalysisSignal, Severity

# Jira issue keys: PROJECT-123 (uppercase project, digits). Word-bounded.
JIRA_KEY_RE = re.compile(r"\b([A-Z][A-Z0-9]{1,9}-\d+)\b")


def extract_jira_key(*texts: str | None) -> str | None:
    """Return the first Jira key found across the given texts, or None."""
    for text in texts:
        if not text:
            continue
        match = JIRA_KEY_RE.search(text)
        if match:
            return match.group(1)
    return None


class TicketLinkageAnalyzer(Analyzer):
    """Surfaces whether a PR is linked to a Jira ticket (no scoring weight)."""

    name = "ticket_linkage"

    def analyze(self, pr: PullRequest, context: AnalysisContext) -> list[AnalysisSignal]:
        # jira_issue_id is populated by the provider mapper (via extract_jira_key);
        # fall back to scanning the PR text here so the signal is self-contained.
        key = pr.jira_issue_id or extract_jira_key(pr.title, pr.description, pr.source_branch)

        if key:
            return [
                AnalysisSignal(
                    analyzer=self.name,
                    name="linked",
                    severity=Severity.INFO,
                    explanation=f"Linked to Jira ticket {key}.",
                    exceeds_threshold=False,
                    metadata={"jira_issue_id": key},
                )
            ]

        return [
            AnalysisSignal(
                analyzer=self.name,
                name="no_jira",
                severity=Severity.LOW,
                explanation=(
                    "No Jira ticket referenced in the title, description, or branch — "
                    "the change is hard to trace back to planned work."
                ),
                exceeds_threshold=True,
                metadata={"jira_issue_id": None},
            )
        ]
