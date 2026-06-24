import { useMemo, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { ArrowLeft, Check, RotateCcw, Save, Sparkles } from "lucide-react";
import { AppShell } from "../components/layout/AppShell";
import { ErrorState, Skeleton } from "../components/primitives/States";
import { api } from "../lib/api";
import { keys, useScoringConfig } from "../lib/queries";
import { ApiError } from "../lib/api";
import type { ScoringConfigOut } from "../lib/types";

// Human labels for the analyzer keys + thresholds the backend returns.
const WEIGHT_LABELS: Record<string, string> = {
  merge_speed: "Merge speed",
  change_size: "Change size",
  review_quality: "Review quality",
  ci_status: "CI status",
};

const THRESHOLD_LABELS: Record<string, string> = {
  merge_fast_minutes: "Fast-merge cutoff (minutes) — faster is rubber-stamp risk",
  merge_slow_minutes: "Healthy-merge cutoff (minutes)",
  change_medium_lines: "Medium change size (lines)",
  change_high_lines: "High change size (lines)",
  change_critical_lines: "Critical change size (lines)",
  change_high_files: "High file count",
  review_trivial_lines: "Trivial-change cutoff (lines) — below this, no review needed",
  review_thin_reviewers: "Minimum reviewers before a review counts as thin",
};

const sum = (xs: number[]): number => xs.reduce((a, b) => a + b, 0);

const topbar = (
  <header className="sticky top-0 z-20 border-b border-hair bg-canvas/80 backdrop-blur-md">
    <div className="mx-auto flex max-w-[1320px] items-center gap-3 px-5 py-3.5 md:px-8">
      <Link
        to="/"
        className="grid h-9 w-9 place-items-center rounded-xl border border-hair-strong bg-surface text-ink"
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
        <Skeleton className="h-[220px] w-full rounded-[22px]" />
        <Skeleton className="mt-4 h-[320px] w-full rounded-[22px]" />
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

  // The parameter the team currently treats as most important (highest weight).
  const topHealth = useMemo(() => {
    let best = "";
    let bestV = -1;
    for (const [k, v] of Object.entries(healthW)) {
      if (v > bestV) {
        best = k;
        bestV = v;
      }
    }
    return best;
  }, [healthW]);

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
    <div className="flex flex-col gap-4 lg:gap-5">
      <div className="card p-6">
        <div className="mb-1 flex items-center justify-between gap-3">
          <div className="eyebrow">Personalize how your team scores PRs</div>
          <span
            className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[11px] font-semibold ${
              config.customized
                ? "bg-accent/10 text-accent"
                : "border border-hair-strong text-ink-mute"
            }`}
          >
            {config.customized && <Sparkles size={12} />}
            {config.customized ? "Team settings active" : "Using defaults"}
          </span>
        </div>
        <p className="text-sm text-ink-mute">
          Turn the dials so the score reflects what matters to <em>your</em> team. Higher weight = that
          area counts more toward PR health. Saved to the server and applied to{" "}
          <strong>new analyses</strong>; already-scored PRs keep their numbers until re-analyzed.
        </p>
        {topHealth && (
          <p className="mt-3 text-[13px] text-ink-soft">
            Right now your team treats{" "}
            <span className="font-semibold text-ink">{WEIGHT_LABELS[topHealth] ?? topHealth}</span> as
            the most important signal.
          </p>
        )}
      </div>

      <WeightCard
        title="Health weights — how much each area counts"
        weights={healthW}
        total={healthSum}
        onChange={(k, v) => setHealthW((w) => ({ ...w, [k]: v }))}
      />

      <div className="card p-6">
        <div className="eyebrow mb-3">Thresholds — when a signal fires</div>
        <div className="flex flex-col">
          {Object.entries(thresholds).map(([key, value]) => (
            <label
              key={key}
              className="flex items-center justify-between gap-4 border-b border-hair py-2.5 last:border-0"
            >
              <span className="text-sm text-ink">{THRESHOLD_LABELS[key] ?? key}</span>
              <input
                type="number"
                min={0}
                value={Number.isFinite(value) ? value : 0}
                onChange={(e) => setThresholds((t) => ({ ...t, [key]: clampNum(e.target.value) }))}
                className="w-24 rounded-lg border border-hair-strong bg-canvas px-2.5 py-1.5 text-right text-sm font-semibold text-ink outline-none focus:border-ink"
              />
            </label>
          ))}
        </div>
      </div>

      <div className="card p-6">
        <div className="eyebrow mb-3">Gates (defaults — not editable yet)</div>
        <div className="flex items-center justify-between border-b border-hair py-2.5">
          <span className="text-sm text-ink">Ready threshold (merge_readiness ≥ this)</span>
          <span className="mono text-sm font-semibold text-ink">{config.ready_threshold}</span>
        </div>
        <div className="flex items-center justify-between py-2.5">
          <span className="text-sm text-ink">Blocked cap (ceiling when a blocker fires)</span>
          <span className="mono text-sm font-semibold text-ink">{config.blocked_cap}</span>
        </div>
      </div>

      {error && (
        <div className="rounded-2xl border border-risk/30 bg-risk/5 px-4 py-3 text-[13px] text-risk">
          {error}
        </div>
      )}

      <div className="sticky bottom-4 flex items-center justify-end gap-2.5">
        <button
          onClick={onReset}
          disabled={pending !== null}
          className="inline-flex items-center gap-1.5 rounded-full border border-hair-strong bg-surface px-4 py-2 text-[13px] font-semibold text-ink transition hover:bg-canvas-deep disabled:opacity-50"
        >
          <RotateCcw size={14} /> Reset to defaults
        </button>
        <button
          onClick={onSave}
          disabled={pending !== null}
          className="inline-flex items-center gap-1.5 rounded-full bg-ink px-4 py-2 text-[13px] font-semibold text-surface transition hover:opacity-90 disabled:opacity-50"
        >
          {savedFlash ? <Check size={14} /> : <Save size={14} />}
          {savedFlash ? "Saved" : pending === "save" ? "Saving…" : "Save preferences"}
        </button>
      </div>
    </div>
  );
}

function WeightCard({
  title,
  weights,
  total,
  onChange,
}: {
  title: string;
  weights: Record<string, number>;
  total: number;
  onChange: (key: string, value: number) => void;
}) {
  const off = total !== 100;
  return (
    <div className="card p-6">
      <div className="mb-3 flex items-center justify-between">
        <div className="eyebrow">{title}</div>
        <span
          className={`mono text-[12px] font-semibold ${off ? "text-risk" : "text-health"}`}
          title="Weights are normalized to 100% on save"
        >
          total {total}%
        </span>
      </div>
      <div className="flex flex-col">
        {Object.entries(weights).map(([key, value]) => (
          <label
            key={key}
            className="flex items-center justify-between gap-4 border-b border-hair py-2.5 last:border-0"
          >
            <span className="text-sm text-ink">{WEIGHT_LABELS[key] ?? key}</span>
            <div className="flex items-center gap-1.5">
              <input
                type="number"
                min={0}
                max={100}
                value={Math.round(value)}
                onChange={(e) => onChange(key, clampNum(e.target.value, 0, 100))}
                className="w-20 rounded-lg border border-hair-strong bg-canvas px-2.5 py-1.5 text-right text-sm font-semibold text-ink outline-none focus:border-ink"
              />
              <span className="text-sm text-ink-mute">%</span>
            </div>
          </label>
        ))}
      </div>
      {off && (
        <p className="mt-3 text-[12px] text-ink-mute">
          Weights total {total}% — they'll be normalized to 100% when you save, keeping their
          relative proportions.
        </p>
      )}
    </div>
  );
}

// --- helpers ---------------------------------------------------------------

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

function clampNum(raw: string, min = 0, max = Number.MAX_SAFE_INTEGER): number {
  const n = Number(raw);
  if (!Number.isFinite(n)) return min;
  return Math.min(max, Math.max(min, n));
}
