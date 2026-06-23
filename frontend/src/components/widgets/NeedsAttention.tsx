import { motion } from "framer-motion";
import { AlertTriangle } from "lucide-react";
import { Card, CardHead } from "../primitives/Card";
import { EmptyState, ErrorState, Skeleton } from "../primitives/States";
import { useNeedsAttention } from "../../lib/queries";

function rateColor(rate: number | null): string {
  if (rate === null) return "var(--color-ink-mute)";
  if (rate >= 30) return "var(--color-risk)";
  if (rate >= 15) return "var(--color-sev-high)";
  if (rate > 0) return "var(--color-sev-medium)";
  return "var(--color-health)";
}

interface Props {
  selectedId?: string;
  onSelect?: (id: string) => void;
  index?: number;
}

export function NeedsAttention({ selectedId, onSelect, index = 0 }: Props) {
  const { data, isLoading, isError, refetch } = useNeedsAttention();

  return (
    <Card index={index} className="flex h-full flex-col">
      <CardHead eyebrow="Which repos need attention" title="Needs attention" />

      {isLoading ? (
        <div className="mt-4 flex flex-col gap-3">
          {Array.from({ length: 3 }).map((_, i) => (
            <Skeleton key={i} className="h-[68px] w-full rounded-2xl" />
          ))}
        </div>
      ) : isError ? (
        <ErrorState onRetry={() => refetch()} />
      ) : !data || data.length === 0 ? (
        <EmptyState title="No repositories yet" hint="Analyze some PRs and the ranking appears here." />
      ) : (
        <ul className="mt-4 flex flex-1 flex-col gap-2.5">
          {data.map((r) => {
            const rate = r.build_violation_rate;
            const col = rateColor(rate);
            const active = r.repo_id === selectedId;
            return (
              <li key={r.repo_id}>
                <button
                  onClick={() => onSelect?.(r.repo_id)}
                  className={`group w-full rounded-2xl border p-3.5 text-left transition ${
                    active ? "border-ink/20 bg-canvas" : "border-hair hover:bg-canvas"
                  }`}
                >
                  <div className="flex items-center justify-between gap-3">
                    <span className="truncate text-[14px] font-semibold text-ink">{r.name}</span>
                    <div className="flex shrink-0 items-center gap-2">
                      {r.needs_attention && (
                        <span className="inline-flex items-center gap-1 rounded-full bg-risk-soft px-2 py-0.5 text-[10px] font-semibold text-risk">
                          <AlertTriangle size={11} />
                          attention
                        </span>
                      )}
                      <span className="tnum text-[14px] font-bold" style={{ color: col }}>
                        {rate === null ? "—" : `${Math.round(rate)}%`}
                      </span>
                    </div>
                  </div>
                  <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-canvas-deep">
                    <motion.div
                      className="h-full rounded-full"
                      style={{ background: col }}
                      initial={{ width: 0 }}
                      animate={{ width: `${rate ?? 0}%` }}
                      transition={{ duration: 0.7, ease: [0.16, 1, 0.3, 1] }}
                    />
                  </div>
                  <div className="mt-1.5 flex items-center justify-between text-[11px] text-ink-mute">
                    <span className="tnum">
                      {r.merged_prs} merged · attention {r.attention_score.toFixed(1)}
                    </span>
                  </div>
                  {r.reasons.length > 0 && (
                    <div className="mt-1 truncate text-[11px] text-ink-soft">
                      {r.reasons.join("  ·  ")}
                    </div>
                  )}
                </button>
              </li>
            );
          })}
        </ul>
      )}

      <p className="mt-3 text-[11px] leading-snug text-ink-mute">
        Violation rate = % of merged PRs shipped without a passing build.
      </p>
    </Card>
  );
}
