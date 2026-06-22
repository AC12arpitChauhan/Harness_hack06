"""Tiny builders for analyzer unit tests (no network, no DB)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.domain.models import (
    AnalysisContext,
    Check,
    CheckStatus,
    Diff,
    PRState,
    PullRequest,
    Review,
    ReviewState,
)

_OPENED = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)


def make_pr(*, merged: bool = False, merged_after_min: int = 120) -> PullRequest:
    merged_at = _OPENED + timedelta(minutes=merged_after_min) if merged else None
    return PullRequest(
        provider="github",
        repo="o/r",
        number=1,
        title="t",
        description="",
        author="a",
        state=PRState.MERGED if merged else PRState.OPEN,
        source_branch="f",
        target_branch="main",
        commit_sha="sha",
        opened_at=_OPENED,
        merged_at=merged_at,
    )


def make_diff(additions: int = 0, deletions: int = 0, files_changed: int = 1) -> Diff:
    return Diff(files_changed=files_changed, additions=additions, deletions=deletions)


def make_ctx(diff: Diff | None = None, reviews=None, checks=None) -> AnalysisContext:
    return AnalysisContext(
        diff=diff or make_diff(),
        reviews=reviews or [],
        checks=checks or [],
    )


def review(name: str, state: ReviewState) -> Review:
    return Review(reviewer=name, state=state)


def check(name: str, status: CheckStatus, required: bool = True) -> Check:
    return Check(name=name, status=status, required=required)
