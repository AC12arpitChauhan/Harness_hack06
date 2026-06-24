import { useState } from "react";
import { ArrowDownRight, ArrowUpRight, Minus } from "lucide-react";
import { Card } from "../primitives/Card";
import { AnimatedNumber } from "../primitives/AnimatedNumber";
import { Lollipop } from "../primitives/Lollipop";
import { Skeleton, ErrorState } from "../primitives/States";
import { useOverview, useScoreHistory } from "../../lib/queries";
import { healthTier } from "../../lib/format";
import type { HistoryBucket } from "../../lib/types";

// Each range picks a bucket granularity + how far back to look.
const RANGES: Record<string, { bucket: HistoryBucket; days: number; per: string; win: string }> = {
  Hours: { bucket: "hour", days: 2, per: "hour", win: "48h" },
  Days: { bucket: "day", days: 30, per: "day", win: "30d" },
  Weeks: { bucket: "week", days: 84, per: "week", win: "12w" },
};

export function HeroIndex({ repoId }: { repoId: string | undefined }) {
  const [range, setRange] = useState<keyof typeof RANGES>("Days");
  const cfg = RANGES[range];

  const overview = useOverview(repoId);
  const history = useScoreHistory(repoId, cfg.days, cfg.bucket);

  const health = overview.data?.averages.health ?? null;
  const analyzed = overview.data?.counts.analyzed ?? 0;
  const points = history.data?.points ?? [];

  // Delta over the visible window: latest bucket vs the first.
  const delta =
    points.length >= 2 ? points[points.length - 1].avg_health - points[0].avg_health : 0;
  const dRounded = Math.round(delta);

  const tier = healthTier(health);
  const tierColor =
    tier === "strong"
      ? "var(--color-health)"
      : tier === "fair"
        ? "var(--color-sev-medium)"
        : tier === "weak"
          ? "var(--color-risk)"
          : "var(--color-ink-mute)";
  const tierLabel =
    tier === "strong" ? "Healthy" : tier === "fair" ? "Watch" : tier === "weak" ? "At risk" : "No data";

  return (
    <Card index={0} className="overflow-hidden">
      <div className="grid gap-7 lg:grid-cols-[minmax(260px,360px)_1fr] lg:gap-9">
        {/* Left: the index */}
        <div className="flex flex-col justify-between">
          <div>
            <div className="eyebrow">PR Health Index</div>
            <p className="mt-1 max-w-[280px] text-[13px] leading-snug text-ink-soft">
              Deterministic, rule-based score across every analyzed pull request in this repository.
            </p>
          </div>

          {overview.isLoading ? (
            <Skeleton className="mt-6 h-[110px] w-[200px]" />
          ) : overview.isError ? (
            <ErrorState message="Couldn't load the index." onRetry={() => overview.refetch()} />
          ) : (
            <div className="mt-6">
              <div className="flex items-end gap-3">
                <AnimatedNumber
                  value={health}
                  className="display text-[92px] leading-[0.82] md:text-[112px]"
                />
                <span className="mb-3 text-[20px] font-semibold text-ink-mute">/100</span>
              </div>

              <div className="mt-4 flex flex-wrap items-center gap-2.5">
                <span
                  className="inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-[12px] font-semibold"
                  style={{ background: `${tierColor}1a`, color: tierColor }}
                >
                  <span className="h-2 w-2 rounded-full" style={{ background: tierColor }} />
                  {tierLabel}
                </span>
                <span
                  className="inline-flex items-center gap-1 rounded-full bg-canvas-deep px-3 py-1 text-[12px] font-semibold text-ink-soft"
                  title="Change across the trend window"
                >
                  {dRounded > 0 ? (
                    <ArrowUpRight size={14} className="text-health" />
                  ) : dRounded < 0 ? (
                    <ArrowDownRight size={14} className="text-risk" />
                  ) : (
                    <Minus size={14} />
                  )}
                  <span className="tnum">
                    {dRounded > 0 ? "+" : dRounded < 0 ? "−" : "±"}
                    {Math.abs(dRounded)}
                  </span>
                  <span className="text-ink-mute">{cfg.win}</span>
                </span>
                <span className="text-[12px] text-ink-mute">
                  <span className="tnum font-semibold text-ink-soft">{analyzed}</span> PRs analyzed
                </span>
              </div>
            </div>
          )}
        </div>

        {/* Right: the trend */}
        <div className="flex flex-col">
          <div className="mb-1 flex flex-wrap items-center justify-between gap-2">
            <span className="eyebrow">Health over time</span>
            <div className="flex items-center gap-2.5">
              <span className="hidden text-[11px] text-ink-mute sm:inline">
                avg per {cfg.per} · last {cfg.win}
              </span>
              <div className="inline-flex rounded-full bg-canvas-deep p-0.5">
                {(Object.keys(RANGES) as (keyof typeof RANGES)[]).map((r) => (
                  <button
                    key={r}
                    onClick={() => setRange(r)}
                    className={`rounded-full px-2.5 py-1 text-[11px] font-semibold transition ${
                      range === r
                        ? "bg-surface text-ink shadow-[0_1px_2px_rgba(16,17,26,.12)]"
                        : "text-ink-mute hover:text-ink"
                    }`}
                  >
                    {r}
                  </button>
                ))}
              </div>
            </div>
          </div>
          {history.isLoading ? (
            <Skeleton className="mt-3 h-[200px] w-full" />
          ) : history.isError ? (
            <ErrorState message="Couldn't load history." onRetry={() => history.refetch()} />
          ) : (
            <Lollipop points={points} height={210} bucket={cfg.bucket} />
          )}
        </div>
      </div>
    </Card>
  );
}
