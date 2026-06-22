"""Request/response DTOs (pydantic). These are the API contract — NOT domain models.

Dashboard response schemas are added in Phase D.
"""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class AnalyzeRequest(BaseModel):
    provider: str = Field(examples=["github"])
    repo: str = Field(examples=["owner/name"])
    pr_number: int
    commit_sha: str | None = None
    action: str | None = None  # e.g. "opened" | "synchronize" (informational)


class ScoreOut(BaseModel):
    health_score: float
    risk_score: float
    review_quality_score: float
    merge_readiness: float
    blocking_reason: str | None = None


class SignalOut(BaseModel):
    signal_name: str
    severity: str
    value: float | None = None
    threshold: float | None = None
    exceeds_threshold: bool = False
    explanation: str = ""


class AnalyzeResponse(BaseModel):
    provider: str
    repo: str
    pr_number: int
    repo_id: str
    pr_id: str
    run_id: str
    ready: bool
    scores: ScoreOut
    signals: list[SignalOut]


# --- dashboard DTOs --------------------------------------------------------
class ScoreSummary(BaseModel):
    health_score: float | None = None
    risk_score: float | None = None
    review_quality_score: float | None = None
    merge_readiness: float | None = None
    blocking_reason: str | None = None


class RepositoryOut(BaseModel):
    id: str
    provider: str
    name: str
    url: str
    pr_count: int
    avg_health_score: float | None = None


class PRListItem(BaseModel):
    pr_id: str
    provider_pr_id: str
    title: str
    author: str
    state: str
    merged_at: datetime | None = None
    score: ScoreSummary | None = None


class NarrativeOut(BaseModel):
    ai_summary: str
    ai_recommendation: str
    ai_model: str
    posted_at: datetime | None = None


class PRDetail(BaseModel):
    pr_id: str
    provider: str
    provider_pr_id: str
    title: str
    author: str
    state: str
    source_branch: str
    target_branch: str
    jira_issue_id: str | None = None
    score: ScoreSummary | None = None
    signals: list[SignalOut] = []
    narrative: NarrativeOut | None = None


class SignalTrendPoint(BaseModel):
    day: str
    count: int


class SignalTrendOut(BaseModel):
    repo_id: str
    signal_name: str
    period_days: int
    points: list[SignalTrendPoint]


class AuthorStatsOut(BaseModel):
    author: str
    pr_count: int
    avg_health_score: float | None = None
    avg_risk_score: float | None = None


class MergeReadinessOut(BaseModel):
    ready: bool
    health_score: float | None = None
    merge_readiness: float | None = None
    blocking_signals: list[str] = []
    override_available: bool = False


class BackfillRequest(BaseModel):
    provider: str = "github"
    repo: str
    since_days: int = 30


class BackfillAccepted(BaseModel):
    status: str
    provider: str
    repo: str
    since_days: int


class RepoHealthSummary(BaseModel):
    repo_id: str
    name: str
    provider: str
    url: str
    total_prs: int
    merged_prs: int
    avg_health_score: float | None = None
    avg_risk_score: float | None = None
    blocked_merges: int
    needs_attention: bool


class AuthorListItem(BaseModel):
    author: str
    pr_count: int
    avg_health_score: float | None = None
    avg_risk_score: float | None = None
