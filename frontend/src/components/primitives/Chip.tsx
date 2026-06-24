import type { ReactNode } from "react";
import { healthTier } from "../../lib/format";

/** A small status dot. */
export function Dot({ color, size = 8 }: { color: string; size?: number }) {
  return (
    <span
      style={{ background: color, width: size, height: size }}
      className="inline-block rounded-full"
    />
  );
}

/** PR state chip — open / merged / closed. */
export function StateChip({ state }: { state: string }) {
  const s = state.toLowerCase();
  const map: Record<string, { bg: string; fg: string; label: string }> = {
    open: { bg: "var(--color-health-soft)", fg: "var(--color-health)", label: "Open" },
    merged: { bg: "#efeafd", fg: "#6d4bd6", label: "Merged" },
    closed: { bg: "var(--color-canvas-deep)", fg: "var(--color-ink-soft)", label: "Closed" },
  };
  const cfg = map[s] ?? { bg: "var(--color-canvas-deep)", fg: "var(--color-ink-soft)", label: state };
  return (
    <span
      style={{ background: cfg.bg, color: cfg.fg }}
      className="inline-flex items-center rounded-full px-2.5 py-0.5 text-[11px] font-semibold tracking-wide"
    >
      {cfg.label}
    </span>
  );
}

/** Ready / critical verdict pill (no "blocked" framing — we surface severity). */
export function ReadyPill({ ready }: { ready: boolean }) {
  return (
    <span
      style={{
        background: ready ? "var(--color-health-soft)" : "var(--color-risk-soft)",
        color: ready ? "var(--color-health)" : "var(--color-risk)",
      }}
      className="inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-[12px] font-semibold"
    >
      <Dot color={ready ? "var(--color-health)" : "var(--color-risk)"} />
      {ready ? "Ready to merge" : "Critical"}
    </span>
  );
}

/** Generic neutral pill. */
export function Pill({
  children,
  tone = "neutral",
}: {
  children: ReactNode;
  tone?: "neutral" | "accent" | "health" | "risk";
}) {
  const tones: Record<string, { bg: string; fg: string }> = {
    neutral: { bg: "var(--color-canvas-deep)", fg: "var(--color-ink-soft)" },
    accent: { bg: "var(--color-accent-soft)", fg: "var(--color-accent)" },
    health: { bg: "var(--color-health-soft)", fg: "var(--color-health)" },
    risk: { bg: "var(--color-risk-soft)", fg: "var(--color-risk)" },
  };
  const c = tones[tone];
  return (
    <span
      style={{ background: c.bg, color: c.fg }}
      className="inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[11px] font-semibold"
    >
      {children}
    </span>
  );
}

/** Inline color-coded health number. */
export function HealthNumber({
  value,
  size = 18,
}: {
  value: number | null | undefined;
  size?: number;
}) {
  const tier = healthTier(value);
  const color =
    tier === "strong"
      ? "var(--color-health)"
      : tier === "fair"
        ? "var(--color-sev-medium)"
        : tier === "weak"
          ? "var(--color-risk)"
          : "var(--color-ink-mute)";
  return (
    <span className="tnum font-semibold" style={{ color, fontSize: size }}>
      {value === null || value === undefined ? "—" : Math.round(value)}
    </span>
  );
}
