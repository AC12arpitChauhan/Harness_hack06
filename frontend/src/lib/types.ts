// API contract — mirrors backend app/api/schemas.py exactly. All GET, no auth.

export type PRStateValue = "open" | "merged" | "closed" | string;
export type SeverityValue =
  | "critical"
  | "high"
  | "medium"
  | "low"
  | "info"
  | string;

export interface ScoreSummary {
  health_score: number | null;
  risk_score: number | null;
  review_quality_score: number | null;
  merge_readiness: number | null;
  blocking_reason: string | null;
}

export interface RepositoryOut {
  id: string;
  provider: string;
  name: string;
  url: string;
  pr_count: number;
  avg_health_score: number | null;
}

export interface PRListItem {
  pr_id: string;
  provider_pr_id: string;
  title: string;
  author: string;
  state: PRStateValue;
  merged_at: string | null;
  score: ScoreSummary | null;
}

export interface SignalOut {
  signal_name: string;
  severity: SeverityValue;
  value: number | null;
  threshold: number | null;
  exceeds_threshold: boolean;
  explanation: string;
}

export interface NarrativeOut {
  ai_summary: string;
  ai_recommendation: string;
  ai_model: string;
  posted_at: string | null;
}

export interface PRDetail {
  pr_id: string;
  provider: string;
  provider_pr_id: string;
  title: string;
  author: string;
  state: PRStateValue;
  source_branch: string;
  target_branch: string;
  jira_issue_id: string | null;
  score: ScoreSummary | null;
  signals: SignalOut[];
  narrative: NarrativeOut | null;
}

export interface OverviewCounts {
  total: number;
  open: number;
  merged: number;
  closed: number;
  ready: number;
  blocked: number;
  analyzed: number;
}

export interface OverviewAverages {
  health: number | null;
  risk: number | null;
  review_quality: number | null;
  merge_readiness: number | null;
}

export interface SeverityDistribution {
  critical: number;
  high: number;
  medium: number;
  low: number;
  info: number;
}

export interface TopSignal {
  signal_name: string;
  count: number;
}

export interface OverviewOut {
  repo_id: string;
  repo_name: string;
  provider: string;
  counts: OverviewCounts;
  averages: OverviewAverages;
  severity_distribution: SeverityDistribution;
  top_signals: TopSignal[];
}

export interface ScoreHistoryPoint {
  day: string;
  runs: number;
  avg_health: number;
}

export interface ScoreHistoryOut {
  repo_id: string;
  period_days: number;
  points: ScoreHistoryPoint[];
}

export interface AuthorStatsOut {
  author: string;
  pr_count: number;
  avg_health_score: number | null;
  avg_risk_score: number | null;
}

export interface MergeReadinessOut {
  ready: boolean;
  health_score: number | null;
  merge_readiness: number | null;
  blocking_signals: string[];
  override_available: boolean;
}

export interface ScoringConfigOut {
  health_weights: Record<string, number>;
  risk_weights: Record<string, number>;
  severity_penalties: Record<string, number>;
  blocked_cap: number;
  ready_threshold: number;
  thresholds: Record<string, number>;
  customized: boolean;
}

export interface ScoringConfigUpdate {
  health_weights: Record<string, number>;
  risk_weights: Record<string, number>;
  thresholds: Record<string, number>;
}

export interface FailingCheck {
  name: string;
  status: string;
  url: string | null;
}

export interface AIFixOut {
  pr_id: string;
  has_failures: boolean;
  failing_checks: FailingCheck[];
  suggestion: string;
  model: string;
}

export interface RepoAttentionOut {
  repo_id: string;
  name: string;
  provider: string;
  merged_prs: number;
  build_violation_rate: number | null;
  attention_score: number;
  needs_attention: boolean;
  signal_counts: Record<string, number>;
  reasons: string[];
}

export interface BehaviourCorrelation {
  behaviour: string;
  with_total: number;
  with_rate: number | null;
  wo_total: number;
  wo_rate: number | null;
}

export interface RevertAnalysisOut {
  repo_id: string;
  merged: number;
  reverted: number;
  behaviours: BehaviourCorrelation[];
}
