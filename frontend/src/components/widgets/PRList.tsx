import { useEffect, useMemo, useState } from "react";
import { ChevronLeft, ChevronRight, Download, Search } from "lucide-react";
import { Card, CardHead } from "../primitives/Card";
import { Dot, HealthNumber, StateChip } from "../primitives/Chip";
import { EmptyState, ErrorState, Skeleton } from "../primitives/States";
import { usePRs } from "../../lib/queries";
import { relativeTime } from "../../lib/format";
import { toCsv, downloadCsv } from "../../lib/csv";

interface Props {
  repoId: string | undefined;
  onSelect: (prId: string) => void;
}

const PAGE_SIZE = 10;

const CSV_COLUMNS = [
  { key: "pr_number", label: "PR #" },
  { key: "title", label: "Title" },
  { key: "author", label: "Author" },
  { key: "state", label: "State" },
  { key: "health_score", label: "Health" },
  { key: "review_quality_score", label: "Review Quality" },
  { key: "merge_readiness", label: "Merge Readiness" },
  { key: "critical_reason", label: "Critical Reason" },
  { key: "merged_at", label: "Merged At" },
];

export function PRList({ repoId, onSelect }: Props) {
  // Fetch the whole list (backend max page = 500); search + paginate on the client.
  const { data, isLoading, isError, refetch } = usePRs(repoId, { limit: 500 });
  const [query, setQuery] = useState("");
  const [page, setPage] = useState(0);

  // Reset to the first page when the repo or the search changes.
  useEffect(() => setPage(0), [repoId, query]);

  const all = data ?? [];
  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return all;
    return all.filter(
      (pr) =>
        (pr.title || "").toLowerCase().includes(q) ||
        (pr.author || "").toLowerCase().includes(q) ||
        String(pr.provider_pr_id).includes(q),
    );
  }, [all, query]);

  const pageCount = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
  const current = Math.min(page, pageCount - 1);
  const start = current * PAGE_SIZE;
  const shown = filtered.slice(start, start + PAGE_SIZE);

  function onExport() {
    const rows = filtered.map((pr) => ({
      pr_number: pr.provider_pr_id,
      title: pr.title,
      author: pr.author,
      state: pr.state,
      health_score: pr.score?.health_score ?? "",
      review_quality_score: pr.score?.review_quality_score ?? "",
      merge_readiness: pr.score?.merge_readiness ?? "",
      critical_reason: pr.score?.blocking_reason ?? "",
      merged_at: pr.merged_at ?? "",
    }));
    downloadCsv(`pr-health-${repoId}.csv`, toCsv(CSV_COLUMNS, rows));
  }

  return (
    <Card index={4} flush className="flex h-full flex-col">
      <div className="p-6 pb-3 md:p-7 md:pb-3">
        <CardHead
          eyebrow="Pull Requests"
          title="All pull requests"
          right={
            <div className="flex items-center gap-2">
              <button
                onClick={onExport}
                disabled={all.length === 0}
                className="inline-flex items-center gap-1.5 rounded-full border-2 border-hair-strong bg-surface px-3 py-1.5 text-[11px] font-semibold text-ink transition hover:bg-canvas-deep disabled:opacity-50"
                title="Download the listed PRs + scores as CSV"
              >
                <Download size={13} />
                CSV
              </button>
              <span className="rounded-full bg-canvas-deep px-2.5 py-1 text-[11px] font-semibold text-ink-soft tnum">
                {all.length}
              </span>
            </div>
          }
        />
        {/* search */}
        <div className="relative mt-4">
          <Search size={15} className="pointer-events-none absolute left-3.5 top-1/2 -translate-y-1/2 text-ink-mute" />
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search by title, author, or #number…"
            className="w-full rounded-xl border-2 border-hair bg-canvas py-2.5 pl-10 pr-3 text-[13px] text-ink outline-none transition placeholder:text-ink-mute focus:border-ink/30"
          />
        </div>
      </div>

      <div className="min-h-0 flex-1 overflow-auto px-3">
        {isLoading ? (
          <div className="flex flex-col gap-2 px-3">
            {Array.from({ length: 6 }).map((_, i) => (
              <Skeleton key={i} className="h-[58px] w-full" />
            ))}
          </div>
        ) : isError ? (
          <ErrorState onRetry={() => refetch()} />
        ) : all.length === 0 ? (
          <EmptyState
            title="No pull requests yet"
            hint="Run an analysis (or /admin/backfill) and PRs will appear here with live scores."
          />
        ) : filtered.length === 0 ? (
          <EmptyState title="No matches" hint={`Nothing matches “${query}”.`} />
        ) : (
          <ul className="flex flex-col">
            {shown.map((pr) => {
              const critical = !!pr.score?.blocking_reason;
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
                      <span className="block truncate text-[14px] font-semibold text-ink">
                        {pr.title || "Untitled PR"}
                      </span>
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
                      <Dot color={critical ? "var(--color-risk)" : "var(--color-health)"} size={9} />
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

      {/* pagination */}
      {filtered.length > 0 && (
        <div className="flex items-center justify-between gap-2 border-t-2 border-hair px-5 py-3 text-[12px]">
          <span className="tnum text-ink-mute">
            {start + 1}–{Math.min(start + PAGE_SIZE, filtered.length)} of {filtered.length}
          </span>
          <div className="flex items-center gap-2">
            <button
              onClick={() => setPage(current - 1)}
              disabled={current === 0}
              className="grid h-7 w-7 place-items-center rounded-full border-2 border-hair-strong text-ink-soft transition hover:bg-canvas-deep disabled:opacity-40"
              aria-label="Previous page"
            >
              <ChevronLeft size={15} />
            </button>
            <span className="tnum font-semibold text-ink-soft">
              {current + 1}/{pageCount}
            </span>
            <button
              onClick={() => setPage(current + 1)}
              disabled={current >= pageCount - 1}
              className="grid h-7 w-7 place-items-center rounded-full border-2 border-hair-strong text-ink-soft transition hover:bg-canvas-deep disabled:opacity-40"
              aria-label="Next page"
            >
              <ChevronRight size={15} />
            </button>
          </div>
        </div>
      )}
    </Card>
  );
}
