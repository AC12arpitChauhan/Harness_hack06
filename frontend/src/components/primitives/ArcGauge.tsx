import { motion } from "framer-motion";
import { healthTier } from "../../lib/format";

interface Props {
  value: number | null | undefined; // 0–100
  size?: number;
  stroke?: number;
  label?: string;
  /** Override the arc color; defaults to a health-tier color. */
  color?: string;
}

const START = 135; // degrees
const SWEEP = 270; // total degrees of the arc

function polar(cx: number, cy: number, r: number, deg: number) {
  const rad = (deg * Math.PI) / 180;
  return { x: cx + r * Math.cos(rad), y: cy + r * Math.sin(rad) };
}

function arcPath(cx: number, cy: number, r: number, startDeg: number, endDeg: number) {
  const s = polar(cx, cy, r, startDeg);
  const e = polar(cx, cy, r, endDeg);
  const large = endDeg - startDeg > 180 ? 1 : 0;
  return `M ${s.x} ${s.y} A ${r} ${r} 0 ${large} 1 ${e.x} ${e.y}`;
}

/** Thick 270° gauge (Material-expressive): tonal track + one bold rounded progress arc. */
export function ArcGauge({ value, size = 172, stroke = 18, label, color }: Props) {
  const cx = size / 2;
  const cy = size / 2;
  const r = (size - stroke) / 2 - 2;
  const v = value === null || value === undefined || Number.isNaN(value) ? 0 : Math.max(0, Math.min(100, value));
  const endDeg = START + (SWEEP * v) / 100;

  const tier = healthTier(value);
  const arcColor =
    color ??
    (tier === "strong"
      ? "var(--color-health)"
      : tier === "fair"
        ? "var(--color-sev-medium)"
        : tier === "weak"
          ? "var(--color-risk)"
          : "var(--color-ink-mute)");
  // Tonal track (Material "container" tone) instead of a flat hairline.
  const trackColor =
    tier === "strong"
      ? "var(--color-health-soft)"
      : tier === "fair"
        ? "var(--color-accent-soft)"
        : tier === "weak"
          ? "var(--color-risk-soft)"
          : "var(--color-canvas-deep)";

  return (
    <div className="relative inline-grid place-items-center" style={{ width: size, height: size }}>
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
        <path
          d={arcPath(cx, cy, r, START, START + SWEEP)}
          fill="none"
          stroke={trackColor}
          strokeWidth={stroke}
          strokeLinecap="round"
        />
        {v > 0 && (
          <motion.path
            d={arcPath(cx, cy, r, START, endDeg)}
            fill="none"
            stroke={arcColor}
            strokeWidth={stroke}
            strokeLinecap="round"
            initial={{ pathLength: 0 }}
            animate={{ pathLength: 1 }}
            transition={{ duration: 1.1, ease: [0.16, 1, 0.3, 1] }}
          />
        )}
      </svg>
      <div className="absolute flex flex-col items-center">
        <span className="tnum text-[46px] font-bold leading-none" style={{ color: arcColor }}>
          {value === null || value === undefined ? "—" : Math.round(v)}
        </span>
        {label && <span className="eyebrow mt-1.5">{label}</span>}
      </div>
    </div>
  );
}
