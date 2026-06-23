import { useState } from "react";
import { ChevronRight, Download } from "lucide-react";
import { Card, CardHead } from "../primitives/Card";
import { Dot, HealthNumber, StateChip } from "../primitives/Chip";
import { EmptyState, ErrorState, Skeleton } from "../primitives/States";
import { usePRs } from "../../lib/queries";
import { api } from "../../lib/api";
import { relativeTime } from "../../lib/format";
import { toCsv, downloadCsv } from "../../lib/csv";

interface Props {
  repoId: string | undefined;
  onSelect: (prId: string) => void;
  limit?: number;
}

const CSV_COLUMNS = [
  { key: "pr_number", label: "PR #" },
  { key: "title", label: "Title" },
  { key: "author", label: "Author" },
  { key: "state", label: "State" },
  { key: "health_score", label: "Health" },
  { key: "risk_score", label: "Risk" },
  { key: "review_quality_score", label: "Review Quality" },
  { key: "merge_readiness", label: "Merge Readiness" },
  { key: "blocking_reason", label: "Blocking Reason" },
  { key: "merged_at", label: "Merged At" },
];

export function PRList({ repoId, onSelect, limit = 14 }: Props) {
  const { data, isLoading, isError, refetch } = usePRs(repoId, { limit });
  const [exporting, setExporting] = useState(false);

  async function onExport() {
    if (!repoId) return;
    setExporting(true);
    try {
      // Export the full list (not just the 14 shown). Plain GET — no auth needed.
      const all = await api.prs(repoId, { limit: 1000 });
      const rows = all.map((pr) => ({
        pr_number: pr.provider_pr_id,
        title: pr.title,
        author: pr.author,
        state: pr.state,
        health_score: pr.score?.health_score ?? "",
        risk_score: pr.score?.risk_score ?? "",
        review_quality_score: pr.score?.review_quality_score ?? "",
        merge_readiness: pr.score?.merge_readiness ?? "",
        blocking_reason: pr.score?.blocking_reason ?? "",
        merged_at: pr.merged_at ?? "",
      }));
      downloadCsv(`pr-health-${repoId}.csv`, toCsv(CSV_COLUMNS, rows));
    } finally {
      setExporting(false);
    }
  }

  return (
    <Card index={4} flush className="flex h-full flex-col">
      <div className="p-6 pb-4 md:p-7 md:pb-4">
        <CardHead
          eyebrow="Pull Requests"
          title="Recent activity"
          right={
            <div className="flex items-center gap-2">
              <button
                onClick={onExport}
                disabled={exporting || !data || data.length === 0}
                className="inline-flex items-center gap-1.5 rounded-full border border-hair-strong bg-surface px-3 py-1.5 text-[11px] font-semibold text-ink transition hover:bg-canvas-deep disabled:opacity-50"
                title="Download all PRs and their scores as CSV"
              >
                <Download size={13} />
                {exporting ? "Exporting…" : "Export CSV"}
              </button>
              <span className="rounded-full bg-canvas-deep px-2.5 py-1 text-[11px] font-semibold text-ink-soft tnum">
                {data?.length ?? 0}
              </span>
            </div>
          }
        />
      </div>

      <div className="min-h-0 flex-1 overflow-auto px-3 pb-3">
        {isLoading ? (
          <div className="flex flex-col gap-2 px-3">
            {Array.from({ length: 6 }).map((_, i) => (
              <Skeleton key={i} className="h-[58px] w-full" />
            ))}
          </div>
        ) : isError ? (
          <ErrorState onRetry={() => refetch()} />
        ) : !data || data.length === 0 ? (
          <EmptyState
            title="No pull requests yet"
            hint="Run an analysis (or /admin/backfill) and PRs will appear here with live scores."
          />
        ) : (
          <ul className="flex flex-col">
            {data.map((pr) => {
              const blocked = !!pr.score?.blocking_reason;
              return (
                <li key={pr.pr_id}>
                  <button
                    onClick={() => onSelect(pr.pr_id)}
                    className="group flex w-full items-center gap-3 rounded-xl px-3 py-3 text-left transition hover:bg-canvas"
                  >
                    <span className="mono w-9 shrink-0 text-[12px] text-ink-mute">
                      #{pr.provider_pr_id}
                    </span>
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2">
                        <span className="truncate text-[14px] font-semibold text-ink">
                          {pr.title || "Untitled PR"}
                        </span>
                      </div>
                      <div className="mt-0.5 flex items-center gap-2 text-[12px] text-ink-mute">
                        <span className="truncate">{pr.author}</span>
                        <span>·</span>
                        <StateChip state={pr.state} />
                        {pr.merged_at && (
                          <>
                            <span>·</span>
                            <span>{relativeTime(pr.merged_at)}</span>
                          </>
                        )}
                      </div>
                    </div>
                    <div className="flex shrink-0 items-center gap-3">
                      <Dot
                        color={blocked ? "var(--color-risk)" : "var(--color-health)"}
                        size={9}
                      />
                      <HealthNumber value={pr.score?.health_score} size={17} />
                      <ChevronRight
                        size={16}
                        className="text-ink-mute transition group-hover:translate-x-0.5 group-hover:text-ink"
                      />
                    </div>
                  </button>
                  <div className="mx-3 h-px bg-hair last:hidden" />
                </li>
              );
            })}
          </ul>
        )}
      </div>
    </Card>
  );
}
