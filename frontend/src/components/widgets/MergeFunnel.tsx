import { motion } from "framer-motion";
import { Card, CardHead } from "../primitives/Card";
import { Skeleton } from "../primitives/States";
import { useOverview } from "../../lib/queries";

export function MergeFunnel({ repoId }: { repoId: string | undefined }) {
  const { data, isLoading } = useOverview(repoId);
  const c = data?.counts;
  const total = Math.max(1, c?.total ?? 1);

  const steps = [
    { label: "Total PRs", value: c?.total ?? 0, color: "var(--color-ink)" },
    { label: "Analyzed", value: c?.analyzed ?? 0, color: "#4b5a7a" },
    { label: "Ready", value: c?.ready ?? 0, color: "var(--color-health)" },
    { label: "Merged", value: c?.merged ?? 0, color: "#6d4bd6" },
  ];

  return (
    <Card index={7} className="flex h-full flex-col">
      <CardHead eyebrow="Throughput" title="Merge funnel" />

      {isLoading ? (
        <div className="mt-6 flex flex-col gap-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="h-9 w-full" />
          ))}
        </div>
      ) : (
        <div className="mt-5 flex flex-col gap-3.5">
          {steps.map((s, i) => {
            const pct = Math.round((s.value / total) * 100);
            return (
              <div key={s.label}>
                <div className="mb-1 flex items-baseline justify-between">
                  <span className="text-[12px] font-medium text-ink-soft">{s.label}</span>
                  <span className="tnum text-[12px] text-ink-mute">
                    <span className="font-semibold text-ink">{s.value}</span> · {pct}%
                  </span>
                </div>
                <div className="h-9 overflow-hidden rounded-lg bg-canvas-deep">
                  <motion.div
                    className="flex h-full items-center justify-end rounded-lg pr-2.5"
                    style={{ background: s.color }}
                    initial={{ width: 0 }}
                    animate={{ width: `${Math.max(pct, s.value > 0 ? 8 : 0)}%` }}
                    transition={{ duration: 0.8, delay: i * 0.08, ease: [0.16, 1, 0.3, 1] }}
                  >
                    <span className="tnum text-[11px] font-bold text-white/90">{s.value}</span>
                  </motion.div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </Card>
  );
}
