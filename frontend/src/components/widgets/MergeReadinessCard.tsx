import { ShieldCheck, ShieldAlert } from "lucide-react";
import { Card, CardHead } from "../primitives/Card";
import { ArcGauge } from "../primitives/ArcGauge";
import { ReadyPill } from "../primitives/Chip";
import { Skeleton, EmptyState } from "../primitives/States";
import { useMergeReadiness } from "../../lib/queries";
import { humanizeSignal } from "../../lib/format";

interface Props {
  repoId: string | undefined;
  prId: string | undefined;
}

export function MergeReadinessCard({ repoId, prId }: Props) {
  const { data, isLoading, isError } = useMergeReadiness(repoId, prId);

  return (
    <Card index={5} className="flex h-full flex-col">
      <CardHead eyebrow="Featured PR" title="Merge readiness" />

      {isLoading ? (
        <div className="mt-6 flex flex-col items-center gap-4">
          <Skeleton className="h-[168px] w-[168px] rounded-full" />
          <Skeleton className="h-6 w-40" />
        </div>
      ) : isError || !data ? (
        <EmptyState title="No analysis yet" hint="This PR hasn't been scored." />
      ) : (
        <div className="mt-3 flex flex-1 flex-col items-center">
          <ArcGauge value={data.merge_readiness} label="readiness" size={172} />
          <div className="mt-4">
            <ReadyPill ready={data.ready} />
          </div>

          <div className="mt-6 w-full">
            {data.blocking_signals.length === 0 ? (
              <div className="flex items-center justify-center gap-2 rounded-2xl bg-health-soft px-4 py-3 text-[13px] font-semibold text-health">
                <ShieldCheck size={16} />
                No blocking conditions
              </div>
            ) : (
              <div className="rounded-2xl bg-risk-soft p-4">
                <div className="mb-2 flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.12em] text-risk">
                  <ShieldAlert size={14} />
                  Blocking ({data.blocking_signals.length})
                </div>
                <ul className="flex flex-col gap-1.5">
                  {data.blocking_signals.map((s, i) => (
                    <li key={i} className="flex items-start gap-2 text-[13px] text-ink">
                      <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-risk" />
                      <span>{humanizeSignal(s)}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        </div>
      )}
    </Card>
  );
}
