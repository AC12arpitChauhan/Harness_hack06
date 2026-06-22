"""Canonical domain models. Providers MUST return these — never provider-native JSON.

PURE: stdlib + dataclasses only. All provider-specific shape lives in providers/mappers/.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class PRState(str, Enum):
    OPEN = "open"
    CLOSED = "closed"
    MERGED = "merged"


class ReviewState(str, Enum):
    APPROVED = "approved"
    CHANGES_REQUESTED = "changes_requested"
    COMMENTED = "commented"
    DISMISSED = "dismissed"
    PENDING = "pending"


class CheckStatus(str, Enum):
    SUCCESS = "success"
    FAILURE = "failure"
    PENDING = "pending"
    ERROR = "error"
    SKIPPED = "skipped"
    NEUTRAL = "neutral"


@dataclass(frozen=True)
class DiffFile:
    filename: str
    additions: int
    deletions: int
    status: str  # added / modified / removed / renamed


@dataclass(frozen=True)
class Diff:
    files_changed: int
    additions: int
    deletions: int
    files: list[DiffFile] = field(default_factory=list)

    @property
    def total_changes(self) -> int:
        return self.additions + self.deletions


@dataclass(frozen=True)
class Review:
    reviewer: str
    state: ReviewState
    submitted_at: datetime | None = None
    lines_commented: int = 0


@dataclass(frozen=True)
class Check:
    name: str
    status: CheckStatus
    required: bool = False
    completed_at: datetime | None = None
    url: str | None = None


@dataclass(frozen=True)
class Commit:
    sha: str
    author: str
    message: str
    committed_at: datetime | None = None


@dataclass(frozen=True)
class PullRequest:
    """Canonical pull request. Identical shape regardless of source provider."""

    provider: str
    repo: str  # canonical repo identifier, e.g. "owner/name"
    number: int
    title: str
    description: str
    author: str
    state: PRState
    source_branch: str
    target_branch: str
    commit_sha: str  # head sha
    base_commit_sha: str = ""
    opened_at: datetime | None = None
    merged_at: datetime | None = None
    closed_at: datetime | None = None
    jira_issue_id: str | None = None
    provider_pr_id: str = ""  # provider-native id / node id, if any

    @property
    def is_merged(self) -> bool:
        return self.state == PRState.MERGED or self.merged_at is not None


@dataclass(frozen=True)
class PRRef:
    """Lightweight PR reference returned by list_pull_requests (backfill)."""

    provider: str
    repo: str
    number: int
    commit_sha: str = ""
    title: str = ""


@dataclass(frozen=True)
class AnalysisContext:
    """Everything an analyzer needs, fetched ONCE by the service and passed in.

    Keeps analyzers PURE: they never perform I/O — they read from this bundle.
    Note: the PullRequest is passed to ``analyze()`` separately (see analyzers/base.py).
    """

    diff: Diff
    reviews: list[Review] = field(default_factory=list)
    checks: list[Check] = field(default_factory=list)
    commits: list[Commit] = field(default_factory=list)