import { Card, CardHead } from "../primitives/Card";
import { ArcGauge } from "../primitives/ArcGauge";
import { Skeleton, EmptyState } from "../primitives/States";
import { useAuthorStats } from "../../lib/queries";

export function AuthorSpotlight({ author }: { author: string | undefined }) {
  const { data, isLoading } = useAuthorStats(author);
  const initial = (author ?? "?").slice(0, 1).toUpperCase();

  return (
    <Card index={8} className="flex h-full flex-col">
      <CardHead eyebrow="People" title="Author spotlight" />

      {!author ? (
        <EmptyState title="No authors yet" />
      ) : isLoading ? (
        <div className="mt-6 flex items-center gap-4">
          <Skeleton className="h-14 w-14 rounded-full" />
          <div className="flex flex-col gap-2">
            <Skeleton className="h-4 w-28" />
            <Skeleton className="h-3 w-20" />
          </div>
        </div>
      ) : (
        <div className="mt-5 flex flex-1 flex-col">
          <div className="flex items-center gap-3.5">
            <div className="grid h-14 w-14 place-items-center rounded-full bg-ink text-[20px] font-bold text-surface">
              {initial}
            </div>
            <div className="min-w-0">
              <div className="truncate text-[17px] font-bold text-ink">{author}</div>
              <div className="text-[12px] text-ink-mute">
                <span className="tnum font-semibold text-ink-soft">{data?.pr_count ?? 0}</span> pull
                requests
              </div>
            </div>
          </div>

          <div className="mt-6 flex flex-1 flex-col">
            <div className="flex flex-1 flex-col items-center justify-center rounded-2xl bg-canvas p-5">
              <ArcGauge value={data?.avg_health_score} label="Avg Health" size={172} />
            </div>
          </div>
        </div>
      )}
    </Card>
  );
}
