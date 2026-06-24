import { Card } from "../primitives/Card";
import { Stat } from "../primitives/Stat";
import { Skeleton } from "../primitives/States";
import { useOverview } from "../../lib/queries";

export function StatTiles({ repoId }: { repoId: string | undefined }) {
  const { data, isLoading } = useOverview(repoId);
  const c = data?.counts;
  const a = data?.averages;

  const tiles: {
    label: string;
    value: number | null | undefined;
    accent: string;
    hint?: string;
  }[] = [
    { label: "Total PRs", value: c?.total, accent: "var(--color-ink)" },
    { label: "Open", value: c?.open, accent: "var(--color-health)" },
    { label: "Merged", value: c?.merged, accent: "#6d4bd6" },
    { label: "Critical", value: c?.blocked, accent: "var(--color-risk)", hint: "high severity" },
  ];

  return (
    <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-5">
      {tiles.map((t, i) => (
        <Card key={t.label} index={i + 1} className="!p-5">
          {isLoading ? (
            <div className="flex flex-col gap-3">
              <Skeleton className="h-3 w-16" />
              <Skeleton className="h-9 w-12" />
            </div>
          ) : (
            <Stat label={t.label} value={t.value} accent={t.accent} hint={t.hint} />
          )}
        </Card>
      ))}
    </div>
  );
}
