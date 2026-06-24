import type { SeverityValue } from "./types";

/** Round a 0–100 score for display; returns "—" for null/undefined. */
export function score(n: number | null | undefined): string {
  if (n === null || n === undefined || Number.isNaN(n)) return "—";
  return String(Math.round(n));
}

export function scoreFixed(n: number | null | undefined, digits = 1): string {
  if (n === null || n === undefined || Number.isNaN(n)) return "—";
  return n.toFixed(digits);
}

/** Signed delta, e.g. +4 / −2 / ±0. */
export function delta(n: number | null | undefined): string {
  if (n === null || n === undefined || Number.isNaN(n)) return "±0";
  const r = Math.round(n);
  if (r === 0) return "±0";
  return r > 0 ? `+${r}` : `−${Math.abs(r)}`;
}

export function relativeTime(iso: string | null | undefined): string {
  if (!iso) return "—";
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return "—";
  const diff = Date.now() - then;
  const sec = Math.round(diff / 1000);
  const min = Math.round(sec / 60);
  const hr = Math.round(min / 60);
  const day = Math.round(hr / 24);
  if (sec < 60) return "just now";
  if (min < 60) return `${min}m ago`;
  if (hr < 24) return `${hr}h ago`;
  if (day < 30) return `${day}d ago`;
  const mo = Math.round(day / 30);
  if (mo < 12) return `${mo}mo ago`;
  return `${Math.round(mo / 12)}y ago`;
}

export function dayLabel(iso: string): string {
  // iso is a YYYY-MM-DD bucket key from the backend.
  const d = new Date(`${iso}T00:00:00`);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

/** Format a score-history bucket key for the x-axis, per granularity.
 *  hour key = "YYYY-MM-DDTHH:00" → "2 PM"; day/week key = "YYYY-MM-DD" → "Mon D". */
export function bucketLabel(key: string, bucket: "hour" | "day" | "week" = "day"): string {
  if (bucket === "hour") {
    const d = new Date(key); // already carries the hour
    return Number.isNaN(d.getTime()) ? key : d.toLocaleTimeString(undefined, { hour: "numeric" });
  }
  return dayLabel(key); // day → "Mon D"; week → the Monday of that week
}

/** Map a 0–100 score to a semantic health tier. */
export function healthTier(n: number | null | undefined): "strong" | "fair" | "weak" | "none" {
  if (n === null || n === undefined || Number.isNaN(n)) return "none";
  if (n >= 80) return "strong";
  if (n >= 60) return "fair";
  return "weak";
}

export const SEVERITY_ORDER: SeverityValue[] = ["critical", "high", "medium", "low", "info"];

export function severityColor(sev: SeverityValue): string {
  switch (sev) {
    case "critical":
      return "var(--color-sev-critical)";
    case "high":
      return "var(--color-sev-high)";
    case "medium":
      return "var(--color-sev-medium)";
    case "low":
      return "var(--color-sev-low)";
    default:
      return "var(--color-sev-info)";
  }
}

/** Turn "merge_speed.fast_merge" into "Merge speed · Fast merge". */
export function humanizeSignal(name: string): string {
  return name
    .split(".")
    .map((seg) =>
      seg
        .replace(/_/g, " ")
        .replace(/\b\w/g, (c) => c.toUpperCase()),
    )
    .join(" · ");
}

export function titleCase(s: string): string {
  return s.replace(/\b\w/g, (c) => c.toUpperCase());
}
