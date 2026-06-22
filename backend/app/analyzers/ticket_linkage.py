"""Ticket linkage — detects PRs with no traceable Jira issue.

Checks title, description, and source branch for a Jira-style key (e.g. PROJ-123).
The mapper also pre-populates ``PullRequest.jira_issue_id`` when a key is found;
both paths are checked so the signal is consistent regardless of which field is set.

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
    name = "ticket_linkage"

    def analyze(self, pr: PullRequest, context: AnalysisContext) -> list[AnalysisSignal]:
        # Accept a key pre-parsed by the mapper OR found in free-text fields.
        key = pr.jira_issue_id or extract_jira_key(
            pr.title, pr.description, pr.source_branch
        )
        if key:
            return [
                AnalysisSignal(
                    analyzer=self.name,
                    name="jira_linked",
                    severity=Severity.INFO,
                    explanation=f"Linked to Jira issue {key}.",
                    exceeds_threshold=False,
                    metadata={"jira_key": key},
                )
            ]
        return [
            AnalysisSignal(
                analyzer=self.name,
                name="no_linked_jira_ticket",
                severity=Severity.MEDIUM,
                explanation=(
                    "No Jira issue key found in title, description, or branch name. "
                    "Unlinked changes are harder to trace to requirements."
                ),
                exceeds_threshold=True,
            )
        ]
