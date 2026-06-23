import { useQuery } from "@tanstack/react-query";
import { api } from "./api";

export const keys = {
  repositories: ["repositories"] as const,
  needsAttention: ["needsAttention"] as const,
  overview: (repoId: string) => ["overview", repoId] as const,
  scoreHistory: (repoId: string, days: number) => ["scoreHistory", repoId, days] as const,
  revertAnalysis: (repoId: string) => ["revertAnalysis", repoId] as const,
  prs: (repoId: string, opts?: object) => ["prs", repoId, opts ?? {}] as const,
  prDetail: (repoId: string, prId: string) => ["prDetail", repoId, prId] as const,
  mergeReadiness: (repoId: string, prId: string) => ["mergeReadiness", repoId, prId] as const,
  aiFix: (repoId: string, prId: string) => ["aiFix", repoId, prId] as const,
  authorStats: (author: string) => ["authorStats", author] as const,
  scoringConfig: ["scoringConfig"] as const,
};

export function useRepositories() {
  return useQuery({ queryKey: keys.repositories, queryFn: api.repositories });
}

export function useNeedsAttention() {
  return useQuery({ queryKey: keys.needsAttention, queryFn: api.needsAttention });
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

export function useRevertAnalysis(repoId: string | undefined) {
  return useQuery({
    queryKey: keys.revertAnalysis(repoId ?? "—"),
    queryFn: () => api.revertAnalysis(repoId!),
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

/** Lazy: only fetches once `enabled` flips true (the user clicks "Suggest a fix").
 *  An AI-fix call is costly (an LLM round-trip), so it never auto-refetches. */
export function useAiFix(repoId: string | undefined, prId: string | undefined, enabled: boolean) {
  return useQuery({
    queryKey: keys.aiFix(repoId ?? "—", prId ?? "—"),
    queryFn: () => api.aiFix(repoId!, prId!),
    enabled: enabled && !!repoId && !!prId,
    staleTime: Infinity,
    refetchInterval: false,
    refetchOnWindowFocus: false,
    retry: 0,
  });
}

export function useAuthorStats(author: string | undefined) {
  return useQuery({
    queryKey: keys.authorStats(author ?? "—"),
    queryFn: () => api.authorStats(author!),
    enabled: !!author,
  });
}

export function useScoringConfig() {
  return useQuery({ queryKey: keys.scoringConfig, queryFn: api.scoringConfig });
}
