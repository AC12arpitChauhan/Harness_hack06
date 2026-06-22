"""SQLAlchemy 2.0 declarative models. Portable across PostgreSQL and SQLite.

Only portable column types are used (String / Text / Integer / Float / Boolean /
DateTime / JSON). No Postgres-only types (e.g. JSONB). PKs are app-generated UUID
strings. Datetimes are stored as naive UTC for cross-dialect consistency.

NO TEAMS — author is a plain string; there is no team table or owning_team_id.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def _uuid() -> str:
    return str(uuid.uuid4())


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Base(DeclarativeBase):
    pass


class Repository(Base):
    __tablename__ = "repositories"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    provider: Mapped[str] = mapped_column(String(32), index=True)
    provider_id: Mapped[str] = mapped_column(String(255))
    name: Mapped[str] = mapped_column(String(512))
    url: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

    __table_args__ = (UniqueConstraint("provider", "provider_id", name="uq_repo_provider_id"),)


class PullRequest(Base):
    __tablename__ = "pull_requests"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    repo_id: Mapped[str] = mapped_column(ForeignKey("repositories.id"), index=True)
    provider: Mapped[str] = mapped_column(String(32), index=True)
    provider_pr_id: Mapped[str] = mapped_column(String(255))
    title: Mapped[str] = mapped_column(Text, default="")
    description: Mapped[str] = mapped_column(Text, default="")
    author: Mapped[str] = mapped_column(String(255), index=True)
    state: Mapped[str] = mapped_column(String(32), index=True)
    opened_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    merged_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    source_branch: Mapped[str] = mapped_column(String(512), default="")
    target_branch: Mapped[str] = mapped_column(String(512), default="")
    commit_sha: Mapped[str] = mapped_column(String(64), default="")
    base_commit_sha: Mapped[str] = mapped_column(String(64), default="")
    jira_issue_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    override_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    override_approved_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, onupdate=_utcnow)

    __table_args__ = (
        UniqueConstraint("repo_id", "provider_pr_id", name="uq_pr_repo_provider_pr_id"),
        Index("ix_pr_repo_state", "repo_id", "state"),
    )


class PrDiff(Base):
    __tablename__ = "pr_diffs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    pr_id: Mapped[str] = mapped_column(ForeignKey("pull_requests.id"), unique=True, index=True)
    files_changed: Mapped[int] = mapped_column(Integer, default=0)
    additions: Mapped[int] = mapped_column(Integer, default=0)
    deletions: Mapped[int] = mapped_column(Integer, default=0)
    files_json: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)


class AnalysisRun(Base):
    __tablename__ = "analysis_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    pr_id: Mapped[str] = mapped_column(ForeignKey("pull_requests.id"), index=True)
    status: Mapped[str] = mapped_column(String(32), default="pending")  # pending|completed|failed
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)


class AnalysisSignal(Base):
    __tablename__ = "analysis_signals"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    analysis_run_id: Mapped[str] = mapped_column(ForeignKey("analysis_runs.id"), index=True)
    signal_name: Mapped[str] = mapped_column(String(128), index=True)
    severity: Mapped[str] = mapped_column(String(32))
    value: Mapped[float | None] = mapped_column(Float, nullable=True)
    threshold: Mapped[float | None] = mapped_column(Float, nullable=True)
    exceeds_threshold: Mapped[bool] = mapped_column(Boolean, default=False)
    explanation: Mapped[str] = mapped_column(Text, default="")
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)


class AnalysisScore(Base):
    __tablename__ = "analysis_scores"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    analysis_run_id: Mapped[str] = mapped_column(
        ForeignKey("analysis_runs.id"), unique=True, index=True
    )
    pr_id: Mapped[str] = mapped_column(ForeignKey("pull_requests.id"), index=True)
    health_score: Mapped[float] = mapped_column(Float)
    risk_score: Mapped[float] = mapped_column(Float)
    review_quality_score: Mapped[float] = mapped_column(Float)
    merge_readiness: Mapped[float] = mapped_column(Float)
    score_breakdown_json: Mapped[dict] = mapped_column(JSON, default=dict)
    blocking_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    computed_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)


class PrReview(Base):
    __tablename__ = "pr_reviews"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    pr_id: Mapped[str] = mapped_column(ForeignKey("pull_requests.id"), index=True)
    reviewer: Mapped[str] = mapped_column(String(255))
    state: Mapped[str] = mapped_column(String(32))
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    lines_commented: Mapped[int] = mapped_column(Integer, default=0)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)


class PrCheck(Base):
    __tablename__ = "pr_checks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    pr_id: Mapped[str] = mapped_column(ForeignKey("pull_requests.id"), index=True)
    check_name: Mapped[str] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(32))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    url: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)


class PrNarrative(Base):
    __tablename__ = "pr_narratives"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    pr_id: Mapped[str] = mapped_column(ForeignKey("pull_requests.id"), unique=True, index=True)
    analysis_run_id: Mapped[str] = mapped_column(ForeignKey("analysis_runs.id"))
    ai_summary: Mapped[str] = mapped_column(Text, default="")
    ai_recommendation: Mapped[str] = mapped_column(Text, default="")
    ai_model: Mapped[str] = mapped_column(String(64), default="")
    posted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    was_accurate: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    feedback_explanation: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)


class RepositoryMetric(Base):
    __tablename__ = "repository_metrics"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    repo_id: Mapped[str] = mapped_column(ForeignKey("repositories.id"), index=True)
    period_start: Mapped[datetime] = mapped_column(DateTime)
    period_end: Mapped[datetime] = mapped_column(DateTime)
    pr_count: Mapped[int] = mapped_column(Integer, default=0)
    avg_health_score: Mapped[float] = mapped_column(Float, default=0.0)
    median_merge_time_minutes: Mapped[float] = mapped_column(Float, default=0.0)
    review_skipped_rate: Mapped[float] = mapped_column(Float, default=0.0)
    ci_failure_rate: Mapped[float] = mapped_column(Float, default=0.0)
    avg_review_quality_score: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

    __table_args__ = (UniqueConstraint("repo_id", "period_start", name="uq_metric_repo_period"),)
