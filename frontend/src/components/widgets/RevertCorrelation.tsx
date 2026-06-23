import { motion } from "framer-motion";
import { GitPullRequestClosed } from "lucide-react";
import { Card, CardHead } from "../primitives/Card";
import { EmptyState, ErrorState, Skeleton } from "../primitives/States";
import { useRevertAnalysis } from "../../lib/queries";
import { titleCase } from "../../lib/format";

const LABELS: Record<string, string> = {
  passing_build: "Passing build",
  linked_jira: "Linked Jira",
  small_change: "Small change",
  unrushed_merge: "Unrushed merge",
};

function Bar({ rate, color }: { rate: number | null; color: string }) {
  return (
    <div className="flex items-center gap-2">
      <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-canvas-deep">
        <motion.div
          className="h-full rounded-full"
          style={{ background: color }}
          initial={{ width: 0 }}
          animate={{ width: `${rate ?? 0}%` }}
          transition={{ duration: 0.7, ease: [0.16, 1, 0.3, 1] }}
        />
      </div>
      <span className="tnum w-9 text-right text-[11px] font-semibold text-ink">
        {rate === null ? "—" : `${Math.round(rate)}%`}
      </span>
    </div>
  );
}

export function RevertCorrelation({ repoId, index = 0 }: { repoId: string | undefined; index?: number }) {
  const { data, isLoading, isError, refetch } = useRevertAnalysis(repoId);

  return (
    <Card index={index} className="flex h-full flex-col">
      <CardHead
        eyebrow="What correlates with quality"
        title="Revert correlation"
        right={
          data ? (
            <span className="rounded-full bg-canvas-deep px-2.5 py-1 text-[11px] font-semibold text-ink-soft tnum">
              {data.reverted}/{data.merged} reverted
            </span>
          ) : undefined
        }
      />

      {isLoading ? (
        <div className="mt-5 flex flex-col gap-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="h-10 w-full" />
          ))}
        </div>
      ) : isError ? (
        <ErrorState onRetry={() => refetch()} />
      ) : !data || data.reverted === 0 ? (
        <div className="mt-2 flex flex-1 flex-col">
          <EmptyState
            title="No reverts in history yet"
            hint="This compares revert rates of PRs with vs without each good practice — it needs reverted PRs to be meaningful. Backfill more history to populate it."
          />
        </div>
      ) : (
        <>
          <div className="mt-4 flex items-center gap-4 text-[11px] text-ink-mute">
            <span className="flex items-center gap-1.5">
              <span className="h-2 w-2 rounded-full bg-risk" /> with practice
            </span>
            <span className="flex items-center gap-1.5">
              <span className="h-2 w-2 rounded-full" style={{ background: "var(--color-slate, #7c8597)" }} />
              without
            </span>
            <span className="ml-auto">revert rate · lower is better</span>
          </div>
          <ul className="mt-3 flex flex-col gap-3.5">
            {data.behaviours.map((b) => {
              const better =
                b.with_rate !== null && b.wo_rate !== null && b.with_rate < b.wo_rate;
              return (
                <li key={b.behaviour}>
                  <div className="mb-1 flex items-center justify-between">
                    <span className="text-[13px] font-semibold text-ink">
                      {LABELS[b.behaviour] ?? titleCase(b.behaviour.replace(/_/g, " "))}
                    </span>
                    {better && (
                      <span className="rounded-full bg-health-soft px-2 py-0.5 text-[10px] font-semibold text-health">
                        correlates with quality
                      </span>
                    )}
                  </div>
                  <Bar rate={b.with_rate} color="var(--color-risk)" />
                  <div className="mt-1.5">
                    <Bar rate={b.wo_rate} color="#7c8597" />
                  </div>
                </li>
              );
            })}
          </ul>
        </>
      )}
    </Card>
  );
}
