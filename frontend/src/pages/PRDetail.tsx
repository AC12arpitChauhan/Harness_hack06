import { useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { ArrowRight, GitMerge, Lightbulb, RefreshCw, Sparkles, Tag, X } from "lucide-react";
import { useQueryClient } from "@tanstack/react-query";
import { ArcGauge } from "../components/primitives/ArcGauge";
import { ReadyPill, StateChip } from "../components/primitives/Chip";
import { ErrorState, Skeleton } from "../components/primitives/States";
import { api, ApiError } from "../lib/api";
import { keys, usePRDetail, useMergeReadiness, useRepositories } from "../lib/queries";
import { humanizeSignal, severityColor, SEVERITY_ORDER, scoreFixed } from "../lib/format";
import type { SignalOut } from "../lib/types";
import { AiFixPanel } from "../components/widgets/AiFixPanel";

interface Props {
  repoId: string | undefined;
  prId: string | undefined;
  onClose: () => void;
}

function ScoreMeter({
  label,
  value,
  invert = false,
}: {
  label: string;
  value: number | null | undefined;
  invert?: boolean;
}) {
  const v = value ?? 0;
  // For risk, high is bad; for the rest, high is good.
  const good = invert ? v <= 30 : v >= 80;
  const mid = invert ? v <= 60 : v >= 60;
  const color = good
    ? "var(--color-health)"
    : mid
      ? "var(--color-sev-medium)"
      : "var(--color-risk)";
  return (
    <div className="rounded-2xl border border-hair bg-surface p-4">
      <div className="eyebrow mb-2">{label}</div>
      <div className="tnum text-[28px] font-bold leading-none" style={{ color }}>
        {value === null || value === undefined ? "—" : Math.round(value)}
      </div>
      <div className="mt-2.5 h-1.5 overflow-hidden rounded-full bg-canvas-deep">
        <div className="h-full rounded-full" style={{ width: `${v}%`, background: color }} />
      </div>
    </div>
  );
}

function SignalRow({ s }: { s: SignalOut }) {
  return (
    <div className="flex items-start gap-3 py-3">
      <span
        className="mt-1.5 h-2 w-2 shrink-0 rounded-full"
        style={{ background: severityColor(s.severity) }}
      />
      <div className="min-w-0 flex-1">
        <div className="flex items-center justify-between gap-3">
          <span className="text-[13px] font-semibold text-ink">{humanizeSignal(s.signal_name)}</span>
          {(s.value !== null || s.threshold !== null) && (
            <span className="mono shrink-0 text-[11px] text-ink-mute tnum">
              {s.value !== null ? scoreFixed(s.value, 1) : "—"}
              {s.threshold !== null && (
                <>
                  {" "}
                  / <span className={s.exceeds_threshold ? "text-risk" : ""}>{scoreFixed(s.threshold, 1)}</span>
                </>
              )}
            </span>
          )}
        </div>
        {s.explanation && (
          <p className="mt-0.5 text-[12.5px] leading-snug text-ink-soft">{s.explanation}</p>
        )}
      </div>
    </div>
  );
}

export function PRDetailDrawer({ repoId, prId, onClose }: Props) {
  const open = !!prId;
  const detail = usePRDetail(repoId, prId);
  const mr = useMergeReadiness(repoId, prId);
  const d = detail.data;

  const queryClient = useQueryClient();
  const repos = useRepositories();
  const repoName = repos.data?.find((r) => r.id === repoId)?.name;
  const [reanalyzing, setReanalyzing] = useState(false);
  const [reanalyzeError, setReanalyzeError] = useState<string | null>(null);

  async function onReanalyze() {
    if (!d || !repoName) return;
    setReanalyzing(true);
    setReanalyzeError(null);
    try {
      await api.analyzePR(d.provider, repoName, Number(d.provider_pr_id));
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: keys.prDetail(repoId ?? "—", prId ?? "—") }),
        queryClient.invalidateQueries({ queryKey: keys.mergeReadiness(repoId ?? "—", prId ?? "—") }),
        queryClient.invalidateQueries({ queryKey: ["prs", repoId] }),
        queryClient.invalidateQueries({ queryKey: ["overview", repoId] }),
      ]);
    } catch (e) {
      setReanalyzeError(
        e instanceof ApiError ? e.message : "Couldn't re-analyze. Please try again.",
      );
    } finally {
      setReanalyzing(false);
    }
  }

  const grouped = SEVERITY_ORDER.map((sev) => ({
    sev,
    items: (d?.signals ?? []).filter((s) => s.severity === sev),
  })).filter((g) => g.items.length > 0);

  return (
    <AnimatePresence>
      {open && (
        <>
          <motion.div
            className="fixed inset-0 z-40 bg-ink/35 backdrop-blur-[2px]"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onClose}
          />
          <motion.aside
            className="fixed right-0 top-0 z-50 flex h-full w-full max-w-[560px] flex-col bg-canvas shadow-[var(--shadow-pop)]"
            initial={{ x: "100%" }}
            animate={{ x: 0 }}
            exit={{ x: "100%" }}
            transition={{ type: "spring", stiffness: 320, damping: 34 }}
          >
            {/* header */}
            <div className="flex items-start justify-between gap-3 border-b border-hair px-6 py-5">
              <div className="min-w-0">
                {detail.isLoading ? (
                  <Skeleton className="h-6 w-40" />
                ) : (
                  <>
                    <div className="flex items-center gap-2">
                      <span className="mono text-[13px] text-ink-mute">#{d?.provider_pr_id}</span>
                      {d && <StateChip state={d.state} />}
                    </div>
                    <h2 className="display mt-1 text-[26px] leading-tight text-ink">
                      {d?.title || "Pull request"}
                    </h2>
                    {d && (
                      <div className="mt-1 text-[12.5px] text-ink-soft">by {d.author}</div>
                    )}
                  </>
                )}
              </div>
              <div className="flex shrink-0 items-center gap-2">
                {d && (
                  <button
                    onClick={onReanalyze}
                    disabled={reanalyzing || !repoName}
                    className="inline-flex items-center gap-1.5 rounded-full border border-hair-strong bg-surface px-3 py-2 text-[12px] font-semibold text-ink transition hover:bg-canvas-deep disabled:opacity-50"
                    title="Re-run analysis with the current scoring settings"
                  >
                    <RefreshCw size={14} className={reanalyzing ? "animate-spin" : ""} />
                    {reanalyzing ? "Analyzing…" : "Re-analyze"}
                  </button>
                )}
                <button
                  onClick={onClose}
                  className="grid h-9 w-9 place-items-center rounded-full border border-hair-strong bg-surface text-ink-soft transition hover:bg-canvas-deep"
                  aria-label="Close"
                >
                  <X size={17} />
                </button>
              </div>
            </div>

            {reanalyzeError && (
              <div className="border-b border-risk/30 bg-risk/5 px-6 py-2.5 text-[12.5px] text-risk">
                {reanalyzeError}
              </div>
            )}

            <div className="min-h-0 flex-1 overflow-auto px-6 py-5">
              {detail.isError ? (
                <ErrorState onRetry={() => detail.refetch()} />
              ) : detail.isLoading ? (
                <div className="flex flex-col gap-3">
                  <Skeleton className="h-24 w-full" />
                  <Skeleton className="h-32 w-full" />
                  <Skeleton className="h-40 w-full" />
                </div>
              ) : d ? (
                <div className="flex flex-col gap-6">
                  {/* branches + jira */}
                  <div className="flex flex-wrap items-center gap-2 text-[12px]">
                    <span className="mono inline-flex items-center gap-1.5 rounded-full bg-surface px-2.5 py-1 text-ink-soft ring-1 ring-hair">
                      {d.source_branch}
                    </span>
                    <ArrowRight size={13} className="text-ink-mute" />
                    <span className="mono inline-flex items-center gap-1.5 rounded-full bg-surface px-2.5 py-1 text-ink-soft ring-1 ring-hair">
                      {d.target_branch}
                    </span>
                    {d.jira_issue_id && (
                      <span className="inline-flex items-center gap-1.5 rounded-full bg-accent-soft px-2.5 py-1 font-semibold text-accent">
                        <Tag size={12} />
                        {d.jira_issue_id}
                      </span>
                    )}
                  </div>

                  {/* four scores */}
                  <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                    <ScoreMeter label="Health" value={d.score?.health_score} />
                    <ScoreMeter label="Risk" value={d.score?.risk_score} invert />
                    <ScoreMeter label="Review" value={d.score?.review_quality_score} />
                    <ScoreMeter label="Readiness" value={d.score?.merge_readiness} />
                  </div>

                  {/* merge readiness verdict */}
                  <div className="rounded-2xl border border-hair bg-surface p-5">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <GitMerge size={16} className="text-ink-soft" />
                        <span className="eyebrow">Merge verdict</span>
                      </div>
                      {mr.data && <ReadyPill ready={mr.data.ready} />}
                    </div>
                    {mr.data && mr.data.blocking_signals.length > 0 && (
                      <>
                        <div className="mb-2 mt-3 text-[11px] font-semibold uppercase tracking-[0.12em] text-risk">
                          Critical ({mr.data.blocking_signals.length})
                        </div>
                        <ul className="flex flex-col gap-1.5">
                          {mr.data.blocking_signals.map((s, i) => (
                            <li key={i} className="flex items-start gap-2 text-[13px] text-ink">
                              <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-risk" />
                              {humanizeSignal(s)}
                            </li>
                          ))}
                        </ul>
                      </>
                    )}
                  </div>

                  {/* AI fix suggestion (on demand) */}
                  <AiFixPanel repoId={repoId} prId={prId} />

                  {/* AI narrative */}
                  {d.narrative && (
                    <div className="rounded-2xl p-5 text-[#e9eaee]" style={{ background: "#16171a" }}>
                      <div className="flex items-center justify-between">
                        <span className="flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.14em] text-white/55">
                          <Sparkles size={14} className="text-accent" /> AI Narrative
                        </span>
                        <span className="mono text-[10px] text-white/45">{d.narrative.ai_model}</span>
                      </div>
                      <p className="display mt-3 text-[20px] leading-snug text-white">
                        “{d.narrative.ai_summary}”
                      </p>
                      {d.narrative.ai_recommendation && (
                        <div className="mt-4 flex items-start gap-2.5 rounded-xl border border-white/10 bg-white/[0.04] p-3.5">
                          <Lightbulb size={15} className="mt-0.5 shrink-0 text-accent" />
                          <p className="text-[13px] leading-relaxed text-white/80">
                            {d.narrative.ai_recommendation}
                          </p>
                        </div>
                      )}
                    </div>
                  )}

                  {/* signals */}
                  <div>
                    <div className="mb-1 flex items-center justify-between">
                      <span className="eyebrow">Signals</span>
                      <span className="text-[11px] text-ink-mute tnum">{d.signals.length} total</span>
                    </div>
                    {grouped.length === 0 ? (
                      <p className="py-4 text-[13px] text-ink-mute">No signals recorded.</p>
                    ) : (
                      grouped.map((g) => (
                        <div key={g.sev} className="mt-3">
                          <div
                            className="mb-1 flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.12em]"
                            style={{ color: severityColor(g.sev) }}
                          >
                            <span className="h-2 w-2 rounded-full" style={{ background: severityColor(g.sev) }} />
                            {g.sev} · {g.items.length}
                          </div>
                          <div className="divide-y divide-hair rounded-2xl border border-hair bg-surface px-4">
                            {g.items.map((s, i) => (
                              <SignalRow key={`${s.signal_name}-${i}`} s={s} />
                            ))}
                          </div>
                        </div>
                      ))
                    )}
                  </div>
                </div>
              ) : null}
            </div>
          </motion.aside>
        </>
      )}
    </AnimatePresence>
  );
}
