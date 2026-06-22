import type {
  AuthorStatsOut,
  MergeReadinessOut,
  OverviewOut,
  PRDetail,
  PRListItem,
  RepositoryOut,
  ScoreHistoryOut,
} from "./types";

const RAW_BASE = import.meta.env.VITE_API_BASE ?? "http://136.109.192.193:8000";
export const API_BASE = RAW_BASE.replace(/\/+$/, "");
const PREFIX = `${API_BASE}/api/v1`;

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
  const url = new URL(`${PREFIX}${path}`);
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

export const api = {
  repositories: () => get<RepositoryOut[]>("/repositories"),

  overview: (repoId: string) => get<OverviewOut>(`/repositories/${repoId}/overview`),

  scoreHistory: (repoId: string, periodDays = 30) =>
    get<ScoreHistoryOut>(`/repositories/${repoId}/score_history`, { period_days: periodDays }),

  prs: (
    repoId: string,
    opts?: { state?: string; order_by?: string; limit?: number },
  ) => get<PRListItem[]>(`/repositories/${repoId}/prs`, opts),

  prDetail: (repoId: string, prId: string) =>
    get<PRDetail>(`/repositories/${repoId}/prs/${prId}`),

  mergeReadiness: (repoId: string, prId: string) =>
    get<MergeReadinessOut>(`/repositories/${repoId}/prs/${prId}/merge_readiness`),

  authorStats: (author: string) =>
    get<AuthorStatsOut>(`/authors/${encodeURIComponent(author)}/pr_stats`),
};
