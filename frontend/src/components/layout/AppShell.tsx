import type { ReactNode } from "react";
import { API_BASE } from "../../lib/api";

export function AppShell({ topbar, children }: { topbar: ReactNode; children: ReactNode }) {
  return (
    <div className="min-h-full">
      {topbar}
      <main className="mx-auto max-w-[1320px] px-5 pb-20 pt-7 md:px-8">{children}</main>
      <footer className="mx-auto max-w-[1320px] px-5 pb-10 md:px-8">
        <div className="rule mb-4" />
        <div className="flex flex-wrap items-center justify-between gap-2 text-[11px] text-ink-mute">
          <span className="uppercase tracking-[0.14em]">
            Deterministic scoring · LLM narration via Bedrock
          </span>
          <span className="mono">{API_BASE || "dev proxy → /api"}</span>
        </div>
      </footer>
    </div>
  );
}
