import { useQuery } from "@tanstack/react-query";
import { api } from "./api";

export const keys = {
  repositories: ["repositories"] as const,
  overview: (repoId: string) => ["overview", repoId] as const,
  scoreHistory: (repoId: string, days: number) => ["scoreHistory", repoId, days] as const,
  prs: (repoId: string, opts?: object) => ["prs", repoId, opts ?? {}] as const,
  prDetail: (repoId: string, prId: string) => ["prDetail", repoId, prId] as const,
  mergeReadiness: (repoId: string, prId: string) => ["mergeReadiness", repoId, prId] as const,
  authorStats: (author: string) => ["authorStats", author] as const,
};

export function useRepositories() {
  return useQuery({ queryKey: keys.repositories, queryFn: api.repositories });
}

export function useOverview(repoId: string | undefined) {
  return useQuery({
    queryKey: keys.overview(repoId ?? "—"),
    queryFn: () => api.overview(repoId!),
    enabled: !!repoId,
  });
}

export function useScoreHistory(repoId: string | undefined, days = 30) {
  return useQuery({
    queryKey: keys.scoreHistory(repoId ?? "—", days),
    queryFn: () => api.scoreHistory(repoId!, days),
    enabled: !!repoId,
  });
}

export function usePRs(
  repoId: string | undefined,
  opts?: { state?: string; order_by?: string; limit?: number },
) {
  return useQuery({
    queryKey: keys.prs(repoId ?? "—", opts),
    queryFn: () => api.prs(repoId!, opts),
    enabled: !!repoId,
  });
}

export function usePRDetail(repoId: string | undefined, prId: string | undefined) {
  return useQuery({
    queryKey: keys.prDetail(repoId ?? "—", prId ?? "—"),
    queryFn: () => api.prDetail(repoId!, prId!),
    enabled: !!repoId && !!prId,
  });
}

export function useMergeReadiness(repoId: string | undefined, prId: string | undefined) {
  return useQuery({
    queryKey: keys.mergeReadiness(repoId ?? "—", prId ?? "—"),
    queryFn: () => api.mergeReadiness(repoId!, prId!),
    enabled: !!repoId && !!prId,
  });
}

export function useAuthorStats(author: string | undefined) {
  return useQuery({
    queryKey: keys.authorStats(author ?? "—"),
    queryFn: () => api.authorStats(author!),
    enabled: !!author,
  });
}
