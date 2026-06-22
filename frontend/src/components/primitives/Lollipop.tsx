import { motion } from "framer-motion";
import { useState } from "react";
import type { ScoreHistoryPoint } from "../../lib/types";
import { dayLabel } from "../../lib/format";

interface Props {
  points: ScoreHistoryPoint[];
  height?: number;
}

/** Signature chart: health-over-time as lollipops (thin stem + dot), tabular axis,
 *  a soft 80/60 band to read tiers at a glance. Hand-built SVG — bespoke, tiny. */
export function Lollipop({ points, height = 220 }: Props) {
  const [hover, setHover] = useState<number | null>(null);

  if (!points.length) {
    return (
      <div
        className="flex items-center justify-center text-sm text-ink-mute"
        style={{ height }}
      >
        No history yet — runs will appear here as PRs are analyzed.
      </div>
    );
  }

  const padX = 14;
  const padTop = 18;
  const padBottom = 30;
  const W = 720; // viewBox width; scales responsively
  const innerW = W - padX * 2;
  const innerH = height - padTop - padBottom;

  const n = points.length;
  const step = n > 1 ? innerW / (n - 1) : 0;
  const x = (i: number) => padX + (n > 1 ? i * step : innerW / 2);
  const y = (v: number) => padTop + innerH * (1 - Math.max(0, Math.min(100, v)) / 100);

  const tierColor = (v: number) =>
    v >= 80 ? "var(--color-health)" : v >= 60 ? "var(--color-sev-medium)" : "var(--color-risk)";

  // show at most ~8 axis labels
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
              x2={W - padX}
              y1={y(g)}
              y2={y(g)}
              stroke="var(--color-hair)"
              strokeWidth={1}
              strokeDasharray={g === 0 ? "0" : "3 4"}
            />
            <text x={W - padX + 2} y={y(g) + 3} fontSize={10} fill="var(--color-ink-mute)" textAnchor="start">
              {g}
            </text>
          </g>
        ))}

        {points.map((p, i) => {
          const cx = x(i);
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
              {/* generous invisible hit area */}
              <rect x={cx - step / 2} y={padTop} width={Math.max(step, 24)} height={innerH} fill="transparent" />
              <motion.line
                x1={cx}
                x2={cx}
                y1={padTop + innerH}
                initial={{ y2: padTop + innerH }}
                animate={{ y2: cy }}
                transition={{ duration: 0.7, delay: i * 0.02, ease: [0.16, 1, 0.3, 1] }}
                stroke={col}
                strokeWidth={active ? 3 : 2}
                strokeLinecap="round"
                opacity={active ? 1 : 0.55}
              />
              <motion.circle
                cx={cx}
                initial={{ cy: padTop + innerH, opacity: 0 }}
                animate={{ cy, opacity: 1 }}
                transition={{ duration: 0.7, delay: i * 0.02, ease: [0.16, 1, 0.3, 1] }}
                r={active ? 6 : 4.5}
                fill={col}
                stroke="var(--color-surface)"
                strokeWidth={2}
              />
              {active && (
                <g>
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
                </g>
              )}
              {i % labelEvery === 0 && (
                <text
                  x={cx}
                  y={height - 10}
                  fontSize={10}
                  fill="var(--color-ink-mute)"
                  textAnchor="middle"
                >
                  {dayLabel(p.day)}
                </text>
              )}
            </g>
          );
        })}
      </svg>
    </div>
  );
}
