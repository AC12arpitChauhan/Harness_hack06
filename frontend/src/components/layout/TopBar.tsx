import { Activity } from "lucide-react";
import type { RepositoryOut } from "../../lib/types";
import { RepoSwitcher } from "./RepoSwitcher";
import { HealthNumber } from "../primitives/Chip";

interface Props {
  repos: RepositoryOut[];
  selectedId: string | undefined;
  onSelect: (id: string) => void;
  globalHealth: number | null | undefined;
  isFetching?: boolean;
}

export function TopBar({ repos, selectedId, onSelect, globalHealth, isFetching }: Props) {
  return (
    <header className="sticky top-0 z-20 border-b border-hair bg-canvas/80 backdrop-blur-md">
      <div className="mx-auto flex max-w-[1320px] items-center justify-between gap-4 px-5 py-3.5 md:px-8">
        <div className="flex items-center gap-3">
          <div className="grid h-9 w-9 place-items-center rounded-xl bg-ink text-surface">
            <Activity size={18} strokeWidth={2.5} />
          </div>
          <div className="leading-tight">
            <div className="text-[15px] font-bold tracking-tight text-ink">PR Health</div>
            <div className="text-[11px] font-medium uppercase tracking-[0.14em] text-ink-mute">
              Analytics
            </div>
          </div>
        </div>

        <div className="flex items-center gap-3">
          {repos.length > 0 && (
            <RepoSwitcher repos={repos} selectedId={selectedId} onSelect={onSelect} />
          )}
          <div className="hidden items-center gap-2 rounded-full border border-hair-strong bg-surface px-3.5 py-2 sm:flex">
            <span
              className={`inline-block h-2 w-2 rounded-full ${
                isFetching ? "bg-accent" : "bg-health"
              }`}
              style={{ animation: isFetching ? "pulse 1.2s infinite" : undefined }}
            />
            <span className="eyebrow">Repo Health</span>
            <HealthNumber value={globalHealth} size={16} />
          </div>
        </div>
      </div>
    </header>
  );
}
