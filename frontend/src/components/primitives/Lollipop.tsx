import { motion } from "framer-motion";
import { useState } from "react";
import type { HistoryBucket, ScoreHistoryPoint } from "../../lib/types";
import { bucketLabel, bucketTime } from "../../lib/format";

interface Props {
  points: ScoreHistoryPoint[];
  height?: number;
  bucket?: HistoryBucket;
  /** Lookback in days — positions points by REAL time across [now−window, now]
   *  so sparse points cluster by recency instead of stretching to both edges. */
  windowDays?: number;
}

/** Signature chart: health-over-time as lollipops (thin stem + dot), tabular axis,
 *  a soft 60–80 band to read tiers at a glance. Hand-built SVG — bespoke, tiny. */
export function Lollipop({ points, height = 220, bucket = "day", windowDays }: Props) {
  const [hover, setHover] = useState<number | null>(null);

  if (!points.length) {
    return (
      <div className="flex items-center justify-center text-sm text-ink-mute" style={{ height }}>
        No history yet — runs will appear here as PRs are analyzed.
      </div>
    );
  }

  const padX = 16;
  const padRight = 30; // room for the y-axis labels
  const padTop = 18;
  const padBottom = 30;
  const W = 720; // viewBox width
  const innerW = W - padX - padRight;
  const innerH = height - padTop - padBottom;
  const n = points.length;

  const y = (v: number) => padTop + innerH * (1 - Math.max(0, Math.min(100, v)) / 100);

  // X position: by REAL time across the lookback window when we know it; the window
  // is padded slightly on each side so a lone/edge point isn't glued to the border.
  let xs: number[];
  const times = points.map((p) => bucketTime(p.day));
  if (windowDays && times.every((t) => t > 0)) {
    const t1 = Date.now();
    const span = windowDays * 86_400_000;
    const t0 = t1 - span;
    const pad = span * 0.04;
    const lo = t0 - pad;
    const hi = t1 + pad;
    xs = times.map((t) => {
      const f = Math.min(1, Math.max(0, (t - lo) / (hi - lo)));
      return padX + f * innerW;
    });
  } else {
    const step = n > 1 ? innerW / (n - 1) : 0;
    xs = points.map((_, i) => (n > 1 ? padX + i * step : padX + innerW / 2));
  }

  const tierColor = (v: number) =>
    v >= 80 ? "var(--color-health)" : v >= 60 ? "var(--color-sev-medium)" : "var(--color-risk)";

  const labelEvery = Math.max(1, Math.ceil(n / 8));

  return (
    <div className="w-full">
      <svg viewBox={`0 0 ${W} ${height}`} className="w-full" style={{ height }} preserveAspectRatio="none">
        {/* tier guide band 60–80 */}
        <rect x={padX} y={y(80)} width={innerW} height={y(60) - y(80)} fill="var(--color-canvas)" />
        {[0, 60, 80, 100].map((g) => (
          <g key={g}>
            <line
              x1={padX}
              x2={padX + innerW}
              y1={y(g)}
              y2={y(g)}
              stroke="var(--color-hair)"
              strokeWidth={1}
              strokeDasharray={g === 0 ? "0" : "3 4"}
            />
            <text x={W - 4} y={y(g) + 3} fontSize={10} fill="var(--color-ink-mute)" textAnchor="end">
              {g}
            </text>
          </g>
        ))}

        {points.map((p, i) => {
          const cx = xs[i];
          const cy = y(p.avg_health);
          const col = tierColor(p.avg_health);
          const active = hover === i;
          return (
            <g
              key={p.day}
              onMouseEnter={() => setHover(i)}
              onMouseLeave={() => setHover(null)}
              style={{ cursor: "default" }}
            >
              <rect x={cx - 14} y={padTop} width={28} height={innerH} fill="transparent" />
              <motion.line
                x1={cx}
                x2={cx}
                y1={padTop + innerH}
                initial={{ y2: padTop + innerH }}
                animate={{ y2: cy }}
                transition={{ duration: 0.7, delay: i * 0.03, ease: [0.16, 1, 0.3, 1] }}
                stroke={col}
                strokeWidth={active ? 3 : 2}
                strokeLinecap="round"
                opacity={active ? 1 : 0.6}
              />
              <motion.circle
                cx={cx}
                initial={{ cy: padTop + innerH, opacity: 0 }}
                animate={{ cy, opacity: 1 }}
                transition={{ duration: 0.7, delay: i * 0.03, ease: [0.16, 1, 0.3, 1] }}
                r={active ? 6 : 4.5}
                fill={col}
                stroke="var(--color-surface)"
                strokeWidth={2}
              />
              {active && (
                <text
                  x={cx}
                  y={cy - 12}
                  fontSize={13}
                  fontWeight={700}
                  fill="var(--color-ink)"
                  textAnchor="middle"
                  className="tnum"
                >
                  {Math.round(p.avg_health)}
                </text>
              )}
              {(i % labelEvery === 0 || i === n - 1) && (
                <text
                  x={Math.min(Math.max(cx, 26), padX + innerW - 4)}
                  y={height - 10}
                  fontSize={10}
                  fill="var(--color-ink-mute)"
                  textAnchor="middle"
                >
                  {bucketLabel(p.day, bucket)}
                </text>
              )}
            </g>
          );
        })}
      </svg>
    </div>
  );
}
