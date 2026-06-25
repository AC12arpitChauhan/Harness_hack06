import { useMemo, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import {
  ArrowLeft,
  Check,
  Lock,
  RotateCcw,
  Ruler,
  Save,
  Scale,
  Sparkles,
} from "lucide-react";
import { AppShell } from "../components/layout/AppShell";
import { ErrorState, Skeleton } from "../components/primitives/States";
import { api, ApiError } from "../lib/api";
import { keys, useScoringConfig } from "../lib/queries";
import { severityColor, SEVERITY_ORDER } from "../lib/format";
import type { ScoringConfigOut } from "../lib/types";
import type { SeverityValue } from "../lib/types";

/* ───────────────────────── metric metadata ─────────────────────────
   Every configurable knob the backend exposes, with a plain-language
   description rendered alongside it. Order here = order on the page. */

const SIGNAL_META: { key: string; label: string; desc: string }[] = [
  {
    key: "review_quality",
    label: "Review quality",
    desc: "Did the PR get real human review — enough approving reviewers for the size of the change? No approval on a non-trivial change is a hard blocker.",
  },
  {
    key: "ci_status",
    label: "CI status",
    desc: "Are the required checks and builds green? A failing required check, or merging despite one, is a hard blocker.",
  },
  {
    key: "change_size",
    label: "Change size",
    desc: "How large the diff is, in lines and files. Big changes are harder to review well and riskier to merge.",
  },
  {
    key: "merge_speed",
    label: "Merge speed",
    desc: "How fast the PR went from opened to merged. Lightning-fast merges often mean nobody really looked.",
  },
];

const THRESHOLD_META: { key: string; label: string; desc: string; unit: string }[] = [
  {
    key: "merge_fast_minutes",
    label: "Rubber-stamp cutoff",
    desc: "Open → merge faster than this is flagged CRITICAL as a likely rubber-stamp.",
    unit: "min",
  },
  {
    key: "merge_slow_minutes",
    label: "Quick-merge cutoff",
    desc: "Merged faster than this — but slower than the rubber-stamp cutoff — is flagged HIGH.",
    unit: "min",
  },
  {
    key: "change_medium_lines",
    label: "Medium change",
    desc: "Total lines changed (additions + deletions) at or above this is a MEDIUM-size signal.",
    unit: "lines",
  },
  {
    key: "change_high_lines",
    label: "Large change",
    desc: "Lines changed at or above this is a HIGH-size signal.",
    unit: "lines",
  },
  {
    key: "change_critical_lines",
    label: "Huge change",
    desc: "Lines changed at or above this is a CRITICAL-size signal.",
    unit: "lines",
  },
  {
    key: "change_high_files",
    label: "File sprawl",
    desc: "Touching at or above this many files flags the change as sprawling.",
    unit: "files",
  },
  {
    key: "review_trivial_lines",
    label: "Trivial-change cutoff",
    desc: "PRs changing this many lines or fewer don't need a review to pass.",
    unit: "lines",
  },
  {
    key: "review_thin_reviewers",
    label: "Thin-review cutoff",
    desc: "Fewer than this many distinct reviewers counts as thin review.",
    unit: "people",
  },
];

const SEVERITY_DESC: Record<string, string> = {
  critical: "A hard problem — e.g. a failing required check or an unreviewed large change.",
  high: "A serious issue that strongly drags the score down.",
  medium: "A notable issue worth flagging on the PR.",
  low: "A minor nit, surfaced but only lightly penalized.",
  info: "Context only — never costs any points.",
};

const sum = (xs: number[]): number => xs.reduce((a, b) => a + b, 0);

const topbar = (
  <header className="sticky top-0 z-20 border-b border-hair bg-canvas/80 backdrop-blur-md">
    <div className="mx-auto flex max-w-[1320px] items-center gap-3 px-5 py-3.5 md:px-8">
      <Link
        to="/"
        className="grid h-9 w-9 place-items-center rounded-xl border border-hair-strong bg-surface text-ink transition hover:bg-canvas-deep"
        aria-label="Back to dashboard"
      >
        <ArrowLeft size={18} />
      </Link>
      <div className="leading-tight">
        <div className="text-[15px] font-bold tracking-tight text-ink">Scoring Settings</div>
        <div className="text-[11px] font-medium uppercase tracking-[0.14em] text-ink-mute">
          Personalize how PRs are scored
        </div>
      </div>
    </div>
  </header>
);

export function Settings() {
  const cfg = useScoringConfig();

  if (cfg.isLoading) {
    return (
      <AppShell topbar={topbar}>
        <Skeleton className="h-[180px] w-full rounded-[22px]" />
        <Skeleton className="mt-5 h-[360px] w-full rounded-[22px]" />
        <Skeleton className="mt-5 h-[440px] w-full rounded-[22px]" />
      </AppShell>
    );
  }

  if (cfg.isError || !cfg.data) {
    return (
      <AppShell topbar={topbar}>
        <div className="card p-10">
          <ErrorState
            message="Couldn't load scoring settings. Confirm the backend is running."
            onRetry={() => cfg.refetch()}
          />
        </div>
      </AppShell>
    );
  }

  // Keyed on the loaded config so the form re-initializes whenever the server
  // values change (after a save/reset, or if the backend defaults change).
  return (
    <AppShell topbar={topbar}>
      <SettingsForm key={JSON.stringify(cfg.data)} config={cfg.data} />
    </AppShell>
  );
}

function SettingsForm({ config }: { config: ScoringConfigOut }) {
  const queryClient = useQueryClient();

  // Weights are edited as PERCENTS (0–100) for a friendlier UI; converted back to
  // fractions on save. Thresholds are edited as their raw numbers.
  const [healthW, setHealthW] = useState<Record<string, number>>(() => toPercent(config.health_weights));
  const [thresholds, setThresholds] = useState<Record<string, number>>(() => ({ ...config.thresholds }));
  const [pending, setPending] = useState<"save" | "reset" | null>(null);
  const [savedFlash, setSavedFlash] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const healthSum = Math.round(sum(Object.values(healthW)));

  // Ordered union of signal keys — known ones first (in our order), any extras appended,
  // so the table is exhaustive even if the backend adds a weighted analyzer later.
  const signalKeys = useMemo(() => orderedKeys(SIGNAL_META.map((m) => m.key), healthW), [healthW]);
  const thresholdKeys = useMemo(
    () => orderedKeys(THRESHOLD_META.map((m) => m.key), thresholds),
    [thresholds],
  );

  const dirty = useMemo(() => {
    return (
      !weightsEqual(healthW, toPercent(config.health_weights)) ||
      !thresholdsEqual(thresholds, config.thresholds)
    );
  }, [healthW, thresholds, config]);

  async function onSave() {
    setPending("save");
    setError(null);
    try {
      await api.saveScoringConfig({
        health_weights: normalize(healthW),
        thresholds,
      });
      await queryClient.invalidateQueries({ queryKey: keys.scoringConfig });
      setSavedFlash(true);
      setTimeout(() => setSavedFlash(false), 1800);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Couldn't save. Please try again.");
    } finally {
      setPending(null);
    }
  }

  async function onReset() {
    setPending("reset");
    setError(null);
    try {
      await api.resetScoringConfig();
      await queryClient.invalidateQueries({ queryKey: keys.scoringConfig });
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Couldn't reset. Please try again.");
    } finally {
      setPending(null);
    }
  }

  return (
    <div className="flex flex-col gap-5 pb-24">
      {/* ───── intro ───── */}
      <div className="card overflow-hidden">
        <div className="flex flex-col gap-4 p-6 md:flex-row md:items-start md:justify-between md:p-7">
          <div className="max-w-2xl">
            <div className="eyebrow mb-2">Your scoring model</div>
            <h1 className="display text-[34px] leading-[1.02] text-ink md:text-[40px]">
              Tune the dials so a healthy&nbsp;PR means what <em>your</em> team says it means.
            </h1>
            <p className="mt-3 text-[13.5px] leading-relaxed text-ink-soft">
              Every metric below feeds the deterministic score. Weights decide how much each area
              counts; thresholds decide when a signal fires. Saved settings apply to{" "}
              <strong className="text-ink">new analyses</strong> — already-scored PRs keep their
              numbers until re-analyzed.
            </p>
          </div>
          <span
            className={`inline-flex shrink-0 items-center gap-1.5 self-start rounded-full px-3 py-1.5 text-[11px] font-semibold ${
              config.customized
                ? "bg-accent-soft text-accent"
                : "border border-hair-strong text-ink-mute"
            }`}
          >
            {config.customized && <Sparkles size={13} />}
            {config.customized ? "Team settings active" : "Using defaults"}
          </span>
        </div>
      </div>

      {/* ───── weights ───── */}
      <SectionCard
        index="01"
        icon={<Scale size={16} />}
        title="Weights — how much each area counts"
        desc="Each signal contributes to the Health score in proportion to its weight. Weights are normalized to 100% on save, so only the relative sizes matter."
        right={<TotalBadge label="Health" total={healthSum} />}
      >
        <div className="overflow-x-auto">
          <table className="w-full border-collapse text-left">
            <thead>
              <Th3 a="Signal" b="What it measures" c="Health" />
            </thead>
            <tbody>
              {signalKeys.map((key) => {
                const meta = SIGNAL_META.find((m) => m.key === key);
                return (
                  <tr key={key} className="border-b border-hair transition last:border-0 hover:bg-surface-2">
                    <td className="px-6 py-4 align-top">
                      <div className="text-[14px] font-semibold text-ink">{meta?.label ?? prettify(key)}</div>
                      <div className="mono mt-0.5 text-[11px] text-ink-mute">{key}</div>
                    </td>
                    <td className="max-w-[420px] px-4 py-4 align-top text-[13px] leading-snug text-ink-soft">
                      {meta?.desc ?? "—"}
                    </td>
                    <td className="px-6 py-4 align-top text-right">
                      <NumberField
                        ariaLabel={`Health weight for ${meta?.label ?? key}`}
                        value={healthW[key]}
                        max={100}
                        suffix="%"
                        onChange={(v) => setHealthW((w) => ({ ...w, [key]: v }))}
                      />
                    </td>
                  </tr>
                );
              })}
            </tbody>
            <tfoot>
              <tr className="border-t border-hair-strong bg-surface-2 text-[12px]">
                <td className="px-6 py-3 font-semibold text-ink" colSpan={2}>
                  Total
                </td>
                <td className="px-6 py-3 text-right">
                  <TotalBadge total={healthSum} compact />
                </td>
              </tr>
            </tfoot>
          </table>
        </div>
        {healthSum !== 100 && (
          <p className="border-t border-hair px-6 py-3 text-[12px] text-ink-mute">
            Weights don't add up to 100% — that's fine. We'll normalize on save and keep your
            relative proportions.
          </p>
        )}
      </SectionCard>

      {/* ───── thresholds ───── */}
      <SectionCard
        index="02"
        icon={<Ruler size={16} />}
        title="Thresholds — when a signal fires"
        desc="The exact lines a PR has to cross before each issue is raised. Lower a cutoff to be stricter; raise it to be more forgiving."
      >
        <div className="overflow-x-auto">
          <table className="w-full border-collapse text-left">
            <thead>
              <Th3 a="Threshold" b="What it controls" c="Value" />
            </thead>
            <tbody>
              {thresholdKeys.map((key) => {
                const meta = THRESHOLD_META.find((m) => m.key === key);
                return (
                  <tr key={key} className="border-b border-hair transition last:border-0 hover:bg-surface-2">
                    <td className="px-6 py-4 align-top">
                      <div className="text-[14px] font-semibold text-ink">{meta?.label ?? prettify(key)}</div>
                      <div className="mono mt-0.5 text-[11px] text-ink-mute">{key}</div>
                    </td>
                    <td className="max-w-[420px] px-4 py-4 align-top text-[13px] leading-snug text-ink-soft">
                      {meta?.desc ?? "—"}
                    </td>
                    <td className="px-6 py-4 align-top text-right">
                      <NumberField
                        ariaLabel={meta?.label ?? key}
                        value={thresholds[key]}
                        suffix={meta?.unit}
                        onChange={(v) => setThresholds((t) => ({ ...t, [key]: v }))}
                      />
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </SectionCard>

      {/* ───── engine constants (reference) ───── */}
      <SectionCard
        index="03"
        icon={<Lock size={16} />}
        title="Engine constants — reference"
        desc="The scoring model itself: how much each severity costs, and the merge gates. These are the same for every team, so the scores stay comparable across the org."
        muted
      >
        <div className="overflow-x-auto">
          <table className="w-full border-collapse text-left">
            <thead>
              <Th3 a="Metric" b="What it means" c="Value" />
            </thead>
            <tbody>
              {SEVERITY_ORDER.map((sev) => (
                <tr key={sev} className="border-b border-hair last:border-0">
                  <td className="px-6 py-3.5 align-top">
                    <span className="inline-flex items-center gap-2">
                      <span
                        className="h-2.5 w-2.5 rounded-full"
                        style={{ background: severityColor(sev as SeverityValue) }}
                      />
                      <span className="text-[14px] font-semibold capitalize text-ink">{sev} penalty</span>
                    </span>
                  </td>
                  <td className="max-w-[420px] px-4 py-3.5 align-top text-[13px] leading-snug text-ink-soft">
                    {SEVERITY_DESC[sev] ?? "Points removed per issue at this severity."}
                  </td>
                  <td className="px-6 py-3.5 align-top text-right">
                    <ReadonlyValue value={config.severity_penalties[sev]} suffix="pts" />
                  </td>
                </tr>
              ))}
              <tr className="border-b border-hair">
                <td className="px-6 py-3.5 align-top text-[14px] font-semibold text-ink">
                  Merge-ready bar
                </td>
                <td className="max-w-[420px] px-4 py-3.5 align-top text-[13px] leading-snug text-ink-soft">
                  A PR is marked ready when merge readiness is at or above this and no hard blocker
                  fired.
                </td>
                <td className="px-6 py-3.5 align-top text-right">
                  <ReadonlyValue value={config.ready_threshold} />
                </td>
              </tr>
              <tr>
                <td className="px-6 py-3.5 align-top text-[14px] font-semibold text-ink">
                  Blocked ceiling
                </td>
                <td className="max-w-[420px] px-4 py-3.5 align-top text-[13px] leading-snug text-ink-soft">
                  When a hard blocker fires, merge readiness is capped at this no matter how good
                  everything else looks.
                </td>
                <td className="px-6 py-3.5 align-top text-right">
                  <ReadonlyValue value={config.blocked_cap} />
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </SectionCard>

      {error && (
        <div className="rounded-2xl border border-risk/30 bg-risk/5 px-4 py-3 text-[13px] text-risk">
          {error}
        </div>
      )}

      {/* ───── sticky actions ───── */}
      <div className="sticky bottom-4 z-10 mt-1">
        <div className="card flex items-center justify-between gap-3 px-4 py-3 shadow-[var(--shadow-pop)]">
          <span className="flex items-center gap-2 pl-1 text-[12.5px] text-ink-soft">
            {savedFlash ? (
              <>
                <Check size={15} className="text-health" />
                <span className="font-semibold text-health">Saved</span>
              </>
            ) : dirty ? (
              <>
                <span className="h-2 w-2 rounded-full bg-accent" />
                <span>Unsaved changes</span>
              </>
            ) : (
              <span className="text-ink-mute">All changes saved</span>
            )}
          </span>
          <div className="flex items-center gap-2.5">
            <button
              onClick={onReset}
              disabled={pending !== null || !config.customized}
              className="inline-flex items-center gap-1.5 rounded-full border border-hair-strong bg-surface px-4 py-2 text-[13px] font-semibold text-ink transition hover:bg-canvas-deep disabled:opacity-40"
              title={config.customized ? "Forget the team override and use engine defaults" : "Already on defaults"}
            >
              <RotateCcw size={14} className={pending === "reset" ? "animate-spin" : ""} />
              Reset to defaults
            </button>
            <button
              onClick={onSave}
              disabled={pending !== null || !dirty}
              className="inline-flex items-center gap-1.5 rounded-full bg-ink px-5 py-2 text-[13px] font-semibold text-surface transition hover:opacity-90 disabled:opacity-40"
            >
              {pending === "save" ? (
                <Save size={14} className="animate-pulse" />
              ) : (
                <Save size={14} />
              )}
              {pending === "save" ? "Saving…" : "Save preferences"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

/* ───────────────────────── presentational pieces ───────────────────────── */

function SectionCard({
  index,
  icon,
  title,
  desc,
  right,
  muted = false,
  children,
}: {
  index: string;
  icon: React.ReactNode;
  title: string;
  desc: string;
  right?: React.ReactNode;
  muted?: boolean;
  children: React.ReactNode;
}) {
  return (
    <section className="card overflow-hidden">
      <div className="flex flex-col gap-3 border-b border-hair px-6 py-5 sm:flex-row sm:items-start sm:justify-between">
        <div className="flex items-start gap-3">
          <span
            className={`grid h-10 w-10 shrink-0 place-items-center rounded-xl ${
              muted ? "bg-canvas-deep text-ink-mute" : "bg-accent-soft text-accent"
            }`}
          >
            {icon}
          </span>
          <div>
            <div className="flex items-center gap-2">
              <span className="display text-[18px] text-ink-mute tnum">{index}</span>
              <h2 className="text-[15px] font-bold tracking-tight text-ink">{title}</h2>
            </div>
            <p className="mt-1 max-w-2xl text-[12.5px] leading-snug text-ink-soft">{desc}</p>
          </div>
        </div>
        {right && <div className="shrink-0 sm:pt-1">{right}</div>}
      </div>
      {children}
    </section>
  );
}

function Th3({ a, b, c }: { a: string; b: string; c: string }) {
  return (
    <tr className="border-b border-hair text-[10.5px] font-semibold uppercase tracking-[0.13em] text-ink-mute">
      <th className="px-6 py-3 text-left">{a}</th>
      <th className="px-4 py-3 text-left">{b}</th>
      <th className="px-6 py-3 text-right">{c}</th>
    </tr>
  );
}

function NumberField({
  value,
  onChange,
  suffix,
  min = 0,
  max,
  ariaLabel,
}: {
  value: number | undefined;
  onChange: (v: number) => void;
  suffix?: string;
  min?: number;
  max?: number;
  ariaLabel?: string;
}) {
  return (
    <span className="inline-flex items-center justify-end gap-1.5">
      <input
        type="number"
        inputMode="numeric"
        aria-label={ariaLabel}
        min={min}
        max={max}
        value={Number.isFinite(value) ? Math.round(value as number) : 0}
        onChange={(e) => onChange(clampNum(e.target.value, min, max ?? Number.MAX_SAFE_INTEGER))}
        className="tnum w-[74px] rounded-lg border border-hair-strong bg-canvas px-2.5 py-1.5 text-right text-[13px] font-semibold text-ink outline-none transition focus:border-ink focus:ring-2 focus:ring-ink/10"
      />
      {suffix && <span className="w-[42px] text-left text-[12px] text-ink-mute">{suffix}</span>}
    </span>
  );
}

function ReadonlyValue({ value, suffix }: { value: number; suffix?: string }) {
  return (
    <span className="mono inline-flex items-center justify-end gap-1.5">
      <span className="rounded-lg bg-canvas-deep px-2.5 py-1.5 text-[13px] font-semibold text-ink tnum">
        {Number.isFinite(value) ? value : "—"}
      </span>
      {suffix && <span className="w-[42px] text-left text-[12px] text-ink-mute">{suffix}</span>}
    </span>
  );
}

function TotalBadge({ total, label, compact = false }: { total: number; label?: string; compact?: boolean }) {
  const off = total !== 100;
  return (
    <span
      className={`mono inline-flex items-center gap-1.5 rounded-full ${compact ? "px-2 py-0.5" : "px-2.5 py-1"} text-[11px] font-semibold ${
        off ? "bg-risk-soft text-risk" : "bg-health-soft text-health"
      }`}
      title="Weights are normalized to 100% on save"
    >
      {label && <span className="font-sans uppercase tracking-wide opacity-70">{label}</span>}
      {total}%
    </span>
  );
}

/* ───────────────────────── helpers ───────────────────────── */

/** Known keys first (in the given order), then any extras present in the data. */
function orderedKeys(known: string[], ...maps: Record<string, number>[]): string[] {
  const all = new Set<string>();
  for (const m of maps) for (const k of Object.keys(m)) all.add(k);
  const ordered = known.filter((k) => all.has(k));
  for (const k of all) if (!ordered.includes(k)) ordered.push(k);
  return ordered;
}

function prettify(key: string): string {
  return key.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

/** fractions (0..1) -> percents (0..100) for editing */
function toPercent(fracs: Record<string, number>): Record<string, number> {
  const out: Record<string, number> = {};
  for (const [k, v] of Object.entries(fracs)) out[k] = Math.round(v * 1000) / 10;
  return out;
}

/** percents -> normalized fractions summing to 1.0 (even split if all zero) */
function normalize(percents: Record<string, number>): Record<string, number> {
  const ks = Object.keys(percents);
  const total = sum(Object.values(percents));
  const out: Record<string, number> = {};
  if (total <= 0) {
    const even = ks.length ? 1 / ks.length : 0;
    for (const k of ks) out[k] = even;
    return out;
  }
  for (const k of ks) out[k] = percents[k] / total;
  return out;
}

function weightsEqual(a: Record<string, number>, b: Record<string, number>): boolean {
  const ks = new Set([...Object.keys(a), ...Object.keys(b)]);
  for (const k of ks) if (Math.round(a[k] ?? 0) !== Math.round(b[k] ?? 0)) return false;
  return true;
}

function thresholdsEqual(a: Record<string, number>, b: Record<string, number>): boolean {
  const ks = new Set([...Object.keys(a), ...Object.keys(b)]);
  for (const k of ks) if ((a[k] ?? NaN) !== (b[k] ?? NaN)) return false;
  return true;
}

function clampNum(raw: string, min = 0, max = Number.MAX_SAFE_INTEGER): number {
  const n = Number(raw);
  if (!Number.isFinite(n)) return min;
  return Math.min(max, Math.max(min, n));
}
