import { useEffect, useMemo } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { AppShell } from "../components/layout/AppShell";
import { TopBar } from "../components/layout/TopBar";
import { HeroIndex } from "../components/widgets/HeroIndex";
import { StatTiles } from "../components/widgets/StatTiles";
import { PRList } from "../components/widgets/PRList";
import { AiInsight } from "../components/widgets/AiInsight";
import { MergeReadinessCard } from "../components/widgets/MergeReadinessCard";
import { SignalBreakdown } from "../components/widgets/SignalBreakdown";
import { MergeFunnel } from "../components/widgets/MergeFunnel";
import { AuthorSpotlight } from "../components/widgets/AuthorSpotlight";
import { PRDetailDrawer } from "./PRDetail";
import { EmptyState, ErrorState, Skeleton } from "../components/primitives/States";
import { useOverview, usePRs, useRepositories } from "../lib/queries";

export function Dashboard() {
  const { repoId, prId } = useParams();
  const navigate = useNavigate();

  const repos = useRepositories();
  const selectedId = repoId ?? repos.data?.[0]?.id;

  // Land on the first repo when none is in the URL.
  useEffect(() => {
    if (!repoId && repos.data && repos.data.length > 0) {
      navigate(`/repos/${repos.data[0].id}`, { replace: true });
    }
  }, [repoId, repos.data, navigate]);

  const overview = useOverview(selectedId);
  const prs = usePRs(selectedId, { limit: 14 });
  const featuredPrId = prs.data?.[0]?.pr_id;

  // Most frequent author across the recent PRs.
  const topAuthor = useMemo(() => {
    const counts = new Map<string, number>();
    for (const pr of prs.data ?? []) counts.set(pr.author, (counts.get(pr.author) ?? 0) + 1);
    let best: string | undefined;
    let bestN = 0;
    for (const [a, n] of counts) {
      if (n > bestN) {
        best = a;
        bestN = n;
      }
    }
    return best;
  }, [prs.data]);

  const globalHealth =
    overview.data?.averages.health ??
    repos.data?.find((r) => r.id === selectedId)?.avg_health_score ??
    null;
  const isFetching = repos.isFetching || overview.isFetching || prs.isFetching;

  const topbar = (
    <TopBar
      repos={repos.data ?? []}
      selectedId={selectedId}
      onSelect={(id) => navigate(`/repos/${id}`)}
      globalHealth={globalHealth}
      isFetching={isFetching}
    />
  );

  // ── repository-level states ───────────────────────────────────────────
  if (repos.isLoading) {
    return (
      <AppShell topbar={topbar}>
        <Skeleton className="h-[280px] w-full rounded-[22px]" />
        <div className="mt-4 grid grid-cols-2 gap-4 sm:grid-cols-5">
          {Array.from({ length: 5 }).map((_, i) => (
            <Skeleton key={i} className="h-[110px] rounded-[22px]" />
          ))}
        </div>
      </AppShell>
    );
  }

  if (repos.isError) {
    return (
      <AppShell topbar={topbar}>
        <div className="card p-10">
          <ErrorState
            message="Couldn't reach the API. Confirm the backend is deployed and CORS is enabled."
            onRetry={() => repos.refetch()}
          />
        </div>
      </AppShell>
    );
  }

  if (!repos.data || repos.data.length === 0) {
    return (
      <AppShell topbar={topbar}>
        <div className="card p-10">
          <EmptyState
            title="No repositories analyzed yet"
            hint="Trigger an analysis from your CI pipeline or POST /api/v1/admin/backfill, then refresh."
          />
        </div>
      </AppShell>
    );
  }

  // ── the bento ─────────────────────────────────────────────────────────
  return (
    <AppShell topbar={topbar}>
      <div className="flex flex-col gap-4 lg:gap-5">
        <HeroIndex repoId={selectedId} />

        <StatTiles repoId={selectedId} />

        <div className="grid grid-cols-1 gap-4 lg:grid-cols-12 lg:gap-5">
          <div className="lg:col-span-7">
            <PRList repoId={selectedId} onSelect={(pid) => navigate(`/repos/${selectedId}/prs/${pid}`)} />
          </div>
          <div className="flex flex-col gap-4 lg:col-span-5 lg:gap-5">
            <AiInsight repoId={selectedId} prId={featuredPrId} />
            <MergeReadinessCard repoId={selectedId} prId={featuredPrId} />
          </div>
        </div>

        <div className="grid grid-cols-1 gap-4 md:grid-cols-3 lg:gap-5">
          <SignalBreakdown repoId={selectedId} />
          <MergeFunnel repoId={selectedId} />
          <AuthorSpotlight author={topAuthor} />
        </div>
      </div>

      <PRDetailDrawer
        repoId={selectedId}
        prId={prId}
        onClose={() => navigate(`/repos/${selectedId}`)}
      />
    </AppShell>
  );
}
