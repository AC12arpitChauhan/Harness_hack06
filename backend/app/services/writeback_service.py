"""Writeback: render a PR comment + set a commit status, behind WRITEBACK_ENABLED.

Disabled (default) => logs exactly what it WOULD post; makes no GitHub calls.
Enabled => posts the comment and sets the commit status via the provider.
"""
from __future__ import annotations

import logging
from collections.abc import Callable

import httpx

from app.domain.models import PullRequest
from app.domain.scores import Score
from app.llm.base import Narrative
from app.providers.base import SCMProvider

logger = logging.getLogger("pr_health.writeback")

STATUS_CONTEXT = "pr-health"


def render_comment(
    pr: PullRequest,
    score: Score,
    narrative: Narrative,
    ready: bool,
    fix_suggestion: str | None = None,
) -> str:
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
    ]
    if fix_suggestion:
        lines += [
            "",
            "**🤖 AI fix suggestion (CI failing).**",
            "",
            fix_suggestion,
        ]
    lines += [
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
    fix_suggestion: str | None = None,
) -> None:
    ready = score.blocking_reason is None and score.merge_readiness >= ready_threshold
    body = render_comment(pr, score, narrative, ready, fix_suggestion)
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

    # Comment and status are independent — a missing scope on one must not abort
    # the other, and each failure logs GitHub's actual reason (not a raw traceback).
    _attempt("comment", repo, pr.number, lambda: provider.post_comment(repo, pr.number, body))
    if pr.commit_sha:
        _attempt(
            "status",
            repo,
            pr.number,
            lambda: provider.set_status(repo, pr.commit_sha, state, STATUS_CONTEXT, description),
        )


def _attempt(action: str, repo: str, number: int, fn: Callable[[], None]) -> None:
    try:
        fn()
        logger.info("writeback: posted %s on %s#%s", action, repo, number)
    except httpx.HTTPStatusError as exc:
        body = ""
        try:
            body = exc.response.text[:300]
        except Exception:  # pragma: no cover - defensive
            pass
        logger.warning(
            "writeback: %s on %s#%s failed (%s) — %s",
            action,
            repo,
            number,
            exc.response.status_code,
            body or "check token scope (Pull requests / Commit statuses: write)",
        )
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("writeback: %s on %s#%s failed: %s", action, repo, number, exc)
