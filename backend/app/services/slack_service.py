"""Slack build-failure alerts. Stdlib-only (urllib), SCM-agnostic, disabled by default.

A no-op unless ``SLACK_WEBHOOK_URL`` is set (settings.slack_enabled). Ported from the
sibling Harness app's notify.py; the only coupling is the link-building, which points
at the GitHub PR + the dashboard's AI-fix deep link.
"""
from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request

from app.config import Settings

logger = logging.getLogger("pr_health.slack")

# In-memory dedup so one PR/commit raises at most one alert. Resets on process
# restart (documented trade-off — avoids a DB column/migration for the demo).
_notified: set[str] = set()


def reset_dedupe() -> None:
    """Clear the dedup set (used by tests)."""
    _notified.clear()


def _post(webhook_url: str, payload: dict) -> bool:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        webhook_url, data=data, headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:  # noqa: S310 (trusted webhook URL)
            ok = 200 <= resp.status < 300
    except urllib.error.URLError as exc:  # network/HTTP error — never raise into the caller
        logger.warning("slack post failed: %s", exc)
        return False
    logger.info("slack alert %s", "sent" if ok else "rejected")
    return ok


def _build_payload(number, title, target, author, failing_checks, pr_url, fix_url) -> dict:
    checks = ", ".join(failing_checks) if failing_checks else "build failed"
    head = f":rotating_light: Build failed — PR #{number}" if number else ":rotating_light: Build failed"
    lines = [
        f"*{title or '(no title)'}*",
        f"target `{target or '?'}`  ·  {author or 'unknown'}",
        f"failing checks: {checks}",
    ]
    links = []
    if pr_url:
        links.append(f"<{pr_url}|View PR>")
    if fix_url:
        links.append(f"<{fix_url}|:bulb: AI fix suggestion>")
    if links:
        lines.append("   ".join(links))
    return {
        "text": head,  # notification/preview fallback
        "blocks": [
            {"type": "section", "text": {"type": "mrkdwn", "text": head + "\n" + "\n".join(lines)}}
        ],
    }


def notify_build_failed(
    settings: Settings,
    *,
    number,
    title,
    target,
    author,
    failing_checks,
    pr_url: str | None = None,
    fix_url: str | None = None,
    dedupe_key: str | None = None,
) -> bool:
    """Post a build-failure alert to Slack. No-op (returns False) when Slack is not
    configured or when ``dedupe_key`` was already alerted. ``failing_checks`` is a
    list of check-name strings."""
    if not settings.slack_enabled:
        return False
    if dedupe_key is not None:
        if dedupe_key in _notified:
            return False
        _notified.add(dedupe_key)
    payload = _build_payload(number, title, target, author, failing_checks, pr_url, fix_url)
    return _post(settings.slack_webhook_url.strip(), payload)
