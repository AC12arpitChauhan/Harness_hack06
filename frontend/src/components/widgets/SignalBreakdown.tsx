import { Card, CardHead } from "../primitives/Card";
import { SeverityBar } from "../primitives/SeverityBar";
import { Skeleton } from "../primitives/States";
import { useOverview } from "../../lib/queries";
import { humanizeSignal, severityColor } from "../../lib/format";

export function SignalBreakdown({ repoId }: { repoId: string | undefined }) {
  const { data, isLoading } = useOverview(repoId);
  const dist = data?.severity_distribution;
  const top = data?.top_signals ?? [];

  const rows = [
    { label: "Critical", value: dist?.critical ?? 0, color: severityColor("critical") },
    { label: "High", value: dist?.high ?? 0, color: severityColor("high") },
    { label: "Medium", value: dist?.medium ?? 0, color: severityColor("medium") },
    { label: "Low", value: dist?.low ?? 0, color: severityColor("low") },
    { label: "Info", value: dist?.info ?? 0, color: severityColor("info") },
  ];

  const maxSignal = Math.max(1, ...top.map((t) => t.count));

  return (
    <Card index={6} className="flex h-full flex-col">
      <CardHead eyebrow="Signals" title="Severity breakdown" />

      {isLoading ? (
        <div className="mt-6 flex flex-col gap-3.5">
          {Array.from({ length: 5 }).map((_, i) => (
            <Skeleton key={i} className="h-2.5 w-full" />
          ))}
        </div>
      ) : (
        <>
          <div className="mt-5">
            <SeverityBar rows={rows} />
          </div>

          {top.length > 0 && (
            <>
              <div className="rule my-5" />
              <div className="eyebrow mb-3">Most frequent</div>
              <ul className="flex flex-col gap-2.5">
                {top.slice(0, 5).map((t) => (
                  <li key={t.signal_name} className="flex items-center gap-3">
                    <span className="min-w-0 flex-1 truncate text-[13px] text-ink-soft">
                      {humanizeSignal(t.signal_name)}
                    </span>
                    <div className="h-1.5 w-20 overflow-hidden rounded-full bg-canvas-deep">
                      <div
                        className="h-full rounded-full bg-ink"
                        style={{ width: `${(t.count / maxSignal) * 100}%` }}
                      />
                    </div>
                    <span className="tnum w-6 text-right text-[13px] font-semibold text-ink">
                      {t.count}
                    </span>
                  </li>
                ))}
              </ul>
            </>
          )}
        </>
      )}
    </Card>
  );
}
