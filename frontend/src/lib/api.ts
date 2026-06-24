import type {
  AIFixOut,
  AuthorStatsOut,
  MergeReadinessOut,
  OverviewOut,
  PRDetail,
  PRListItem,
  RepoAttentionOut,
  RepositoryOut,
  RevertAnalysisOut,
  ScoreHistoryOut,
  ScoringConfigOut,
  ScoringConfigUpdate,
} from "./types";

const RAW_BASE = import.meta.env.VITE_API_BASE ?? "http://136.109.192.193:8000";
export const API_BASE = RAW_BASE.replace(/\/+$/, "");
const PREFIX = `${API_BASE}/api/v1`;

// Bearer token for write routes (scoring-config). Set VITE_ADMIN_TOKEN to your
// backend's FASTAPI_AUTH_TOKEN. Empty by default → writes return a clear 401.
const ADMIN_TOKEN = (import.meta.env.VITE_ADMIN_TOKEN ?? "").trim();

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function get<T>(path: string, params?: Record<string, string | number | undefined>): Promise<T> {
  // Base arg lets a relative PREFIX (dev proxy, API_BASE="") resolve against the
  // current origin; for an absolute PREFIX the base is ignored. Without it,
  // `new URL("/api/v1/...")` throws "Invalid URL".
  const url = new URL(`${PREFIX}${path}`, window.location.origin);
  if (params) {
    for (const [k, v] of Object.entries(params)) {
      if (v !== undefined && v !== "") url.searchParams.set(k, String(v));
    }
  }
  let resp: Response;
  try {
    resp = await fetch(url.toString(), { headers: { Accept: "application/json" } });
  } catch (e) {
    throw new ApiError(
      `Could not reach the API at ${API_BASE}. Is the backend running and CORS enabled?`,
      0,
    );
  }
  if (!resp.ok) {
    let detail = resp.statusText;
    try {
      const body = await resp.json();
      if (body?.detail) detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
    } catch {
      /* ignore */
    }
    throw new ApiError(detail || `Request failed (${resp.status})`, resp.status);
  }
  return (await resp.json()) as T;
}

async function send<T>(method: "POST" | "PUT" | "DELETE", path: string, body?: unknown): Promise<T> {
  const url = new URL(`${PREFIX}${path}`, window.location.origin);
  const headers: Record<string, string> = { Accept: "application/json" };
  if (body !== undefined) headers["Content-Type"] = "application/json";
  if (ADMIN_TOKEN) headers.Authorization = `Bearer ${ADMIN_TOKEN}`;
  let resp: Response;
  try {
    resp = await fetch(url.toString(), {
      method,
      headers,
      body: body !== undefined ? JSON.stringify(body) : undefined,
    });
  } catch (e) {
    throw new ApiError(
      `Could not reach the API at ${API_BASE}. Is the backend running and CORS enabled?`,
      0,
    );
  }
  if (!resp.ok) {
    let detail = resp.statusText;
    try {
      const b = await resp.json();
      if (b?.detail) detail = typeof b.detail === "string" ? b.detail : JSON.stringify(b.detail);
    } catch {
      /* ignore */
    }
    if (resp.status === 401) {
      detail =
        "Saving needs an admin token. Set VITE_ADMIN_TOKEN (frontend env) to your backend's FASTAPI_AUTH_TOKEN.";
    }
    throw new ApiError(detail || `Request failed (${resp.status})`, resp.status);
  }
  return (await resp.json()) as T;
}

export const api = {
  repositories: () => get<RepositoryOut[]>("/repositories"),

  needsAttention: () => get<RepoAttentionOut[]>("/repositories/needs_attention"),

  overview: (repoId: string) => get<OverviewOut>(`/repositories/${repoId}/overview`),

  scoreHistory: (repoId: string, periodDays = 30, bucket: "hour" | "day" | "week" = "day") =>
    get<ScoreHistoryOut>(`/repositories/${repoId}/score_history`, { period_days: periodDays, bucket }),

  revertAnalysis: (repoId: string) =>
    get<RevertAnalysisOut>(`/repositories/${repoId}/revert_analysis`),

  prs: (
    repoId: string,
    opts?: { state?: string; order_by?: string; limit?: number },
  ) => get<PRListItem[]>(`/repositories/${repoId}/prs`, opts),

  prDetail: (repoId: string, prId: string) =>
    get<PRDetail>(`/repositories/${repoId}/prs/${prId}`),

  mergeReadiness: (repoId: string, prId: string) =>
    get<MergeReadinessOut>(`/repositories/${repoId}/prs/${prId}/merge_readiness`),

  aiFix: (repoId: string, prId: string) =>
    get<AIFixOut>(`/repositories/${repoId}/prs/${prId}/ai_fix`),

  authorStats: (author: string) =>
    get<AuthorStatsOut>(`/authors/${encodeURIComponent(author)}/pr_stats`),

  scoringConfig: () => get<ScoringConfigOut>("/scoring-config"),

  saveScoringConfig: (body: ScoringConfigUpdate) =>
    send<ScoringConfigOut>("PUT", "/scoring-config", body),

  resetScoringConfig: () => send<ScoringConfigOut>("DELETE", "/scoring-config"),

  analyzePR: (provider: string, repo: string, prNumber: number) =>
    send<Record<string, unknown>>("POST", "/analyze", { provider, repo, pr_number: prNumber }),
};
