"""Ticket linkage — FUTURE, not implemented this round.

The Jira-key regex helper below IS in place and is used by the provider mappers
to populate ``PullRequest.jira_issue_id`` when a key is trivially parseable. The
analyzer itself returns no signals and is NOT wired into scoring weights this
round; full linkage validation (key exists, matches branch, etc.) lands later.

PURE: stdlib + domain only.
"""
from __future__ import annotations

import re

from app.analyzers.base import Analyzer
from app.domain.models import AnalysisContext, PullRequest
from app.domain.signals import AnalysisSignal

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
    """FUTURE — not implemented this round. Emits no signals."""

    name = "ticket_linkage"

    def analyze(self, pr: PullRequest, context: AnalysisContext) -> list[AnalysisSignal]:
        return []
