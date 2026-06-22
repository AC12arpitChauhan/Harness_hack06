import { useEffect, useRef, useState } from "react";
import { Check, ChevronsUpDown, GitBranch } from "lucide-react";
import type { RepositoryOut } from "../../lib/types";
import { HealthNumber } from "../primitives/Chip";

interface Props {
  repos: RepositoryOut[];
  selectedId: string | undefined;
  onSelect: (id: string) => void;
}

export function RepoSwitcher({ repos, selectedId, onSelect }: Props) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const selected = repos.find((r) => r.id === selectedId) ?? repos[0];

  useEffect(() => {
    function onDoc(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, []);

  if (!selected) return null;

  return (
    <div ref={ref} className="relative">
      <button
        onClick={() => setOpen((o) => !o)}
        className="flex items-center gap-2.5 rounded-full border border-hair-strong bg-surface px-3.5 py-2 text-sm font-semibold text-ink transition hover:border-ink/30"
      >
        <GitBranch size={15} className="text-ink-mute" />
        <span className="max-w-[220px] truncate">{selected.name}</span>
        <span className="rounded-full bg-canvas-deep px-1.5 py-0.5 text-[11px] font-semibold text-ink-soft tnum">
          {selected.pr_count}
        </span>
        <ChevronsUpDown size={14} className="text-ink-mute" />
      </button>

      {open && (
        <div className="absolute left-0 z-30 mt-2 w-[320px] overflow-hidden rounded-2xl border border-hair bg-surface p-1.5 shadow-[var(--shadow-pop)]">
          <div className="eyebrow px-3 py-2">Repositories</div>
          <div className="max-h-[340px] overflow-auto">
            {repos.map((r) => {
              const active = r.id === selected.id;
              return (
                <button
                  key={r.id}
                  onClick={() => {
                    onSelect(r.id);
                    setOpen(false);
                  }}
                  className={`flex w-full items-center justify-between gap-3 rounded-xl px-3 py-2.5 text-left transition ${
                    active ? "bg-canvas-deep" : "hover:bg-canvas"
                  }`}
                >
                  <div className="min-w-0">
                    <div className="flex items-center gap-2">
                      {active && <Check size={14} className="text-health" />}
                      <span className="truncate text-sm font-semibold text-ink">{r.name}</span>
                    </div>
                    <span className="text-[11px] uppercase tracking-wide text-ink-mute">
                      {r.provider} · {r.pr_count} PRs
                    </span>
                  </div>
                  <HealthNumber value={r.avg_health_score} size={16} />
                </button>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
