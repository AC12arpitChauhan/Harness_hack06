"""Writeback: render a PR comment + set a commit status, behind WRITEBACK_ENABLED.

Disabled (default) => logs exactly what it WOULD post; makes no GitHub calls.
Enabled => posts the comment and sets the commit status via the provider.
"""
from __future__ import annotations

import logging

from app.domain.models import PullRequest
from app.domain.scores import Score
from app.llm.base import Narrative
from app.providers.base import SCMProvider

logger = logging.getLogger("pr_health.writeback")

STATUS_CONTEXT = "pr-health"


def render_comment(pr: PullRequest, score: Score, narrative: Narrative, ready: bool) -> str:
    badge = "✅" if ready else "⚠️"
    lines = [
        f"## PR Health: {score.health_score:.0f}/100 {badge}",
        "",
        f"| Health | Risk | Review quality | Merge readiness |",
        f"|---|---|---|---|",
        f"| {score.health_score:.0f} | {score.risk_score:.0f} | "
        f"{score.review_quality_score:.0f} | {score.merge_readiness:.0f} |",
    ]
    if score.blocking_reason:
        lines += ["", f"> 🚫 **Blocked:** {score.blocking_reason}"]
    lines += [
        "",
        f"**Summary.** {narrative.summary}",
        "",
        "**Recommendation.**",
        narrative.recommendation,
        "",
        f"<sub>Scores computed deterministically · narrative by `{narrative.model}`</sub>",
    ]
    return "\n".join(lines)


def do_writeback(
    provider: SCMProvider,
    repo: str,
    pr: PullRequest,
    score: Score,
    narrative: Narrative,
    *,
    enabled: bool,
    ready_threshold: float,
) -> None:
    ready = score.blocking_reason is None and score.merge_readiness >= ready_threshold
    body = render_comment(pr, score, narrative, ready)
    state = "success" if ready else "failure"
    description = f"Health {score.health_score:.0f}/100" + (
        "" if ready else f" — {score.blocking_reason or 'not ready'}"
    )

    if not enabled:
        logger.info(
            "[writeback disabled] would comment on %s#%s and set status '%s'=%s (%s)",
            repo,
            pr.number,
            STATUS_CONTEXT,
            state,
            description,
        )
        return

    provider.post_comment(repo, pr.number, body)
    if pr.commit_sha:
        provider.set_status(repo, pr.commit_sha, state, STATUS_CONTEXT, description)
