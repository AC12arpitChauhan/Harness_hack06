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


# --- overview / trends (dashboard hero widgets) ----------------------------
class OverviewCounts(BaseModel):
    total: int = 0
    open: int = 0
    merged: int = 0
    closed: int = 0
    ready: int = 0
    blocked: int = 0
    analyzed: int = 0


class OverviewAverages(BaseModel):
    health: float | None = None
    risk: float | None = None
    review_quality: float | None = None
    merge_readiness: float | None = None


class SeverityDistribution(BaseModel):
    critical: int = 0
    high: int = 0
    medium: int = 0
    low: int = 0
    info: int = 0


class TopSignal(BaseModel):
    signal_name: str
    count: int


class OverviewOut(BaseModel):
    repo_id: str
    repo_name: str
    provider: str
    counts: OverviewCounts
    averages: OverviewAverages
    severity_distribution: SeverityDistribution
    top_signals: list[TopSignal] = []


class ScoreHistoryPoint(BaseModel):
    day: str
    runs: int
    avg_health: float


class ScoreHistoryOut(BaseModel):
    repo_id: str
    period_days: int
    points: list[ScoreHistoryPoint] = []


class ScoringConfigOut(BaseModel):
    """The active scoring knobs — the weights every PR is scored against plus the
    analyzer thresholds. Reflects engine defaults overlaid with the team override;
    ``customized`` is True when a team override is in effect."""
    health_weights: dict[str, float]
    risk_weights: dict[str, float]
    severity_penalties: dict[str, float]
    blocked_cap: float
    ready_threshold: float
    thresholds: dict[str, float]
    customized: bool = False


class ScoringConfigUpdate(BaseModel):
    """Team override submitted from the Settings page. Weights are normalized and
    thresholds sanitized server-side, so partial/odd input can't break scoring."""
    health_weights: dict[str, float] = Field(default_factory=dict)
    risk_weights: dict[str, float] = Field(default_factory=dict)
    thresholds: dict[str, float] = Field(default_factory=dict)


class LLMCheckOut(BaseModel):
    """Synchronous diagnostic for the /analyze -> narrate path. `ok` means a live
    round-trip to the configured narrator succeeded; `error` carries the real
    exception when it didn't (the background narrate step otherwise swallows it)."""
    llm_enabled: bool
    backend: str  # "bedrock" | "anthropic" | "disabled"
    narrator: str  # concrete class chosen (BedrockNarrator / TemplatedNarrator / ...)
    model_configured: str
    region: str | None = None
    key_present: bool
    ok: bool
    model_returned: str | None = None
    error: str | None = None
