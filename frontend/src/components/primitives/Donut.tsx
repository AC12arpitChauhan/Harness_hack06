import { motion } from "framer-motion";

interface Segment {
  value: number;
  color: string;
  label: string;
}

interface Props {
  segments: Segment[];
  size?: number;
  stroke?: number;
  centerTop?: string;
  centerSub?: string;
}

/** Ring chart (donut) for ready/blocked-style splits. */
export function Donut({ segments, size = 150, stroke = 16, centerTop, centerSub }: Props) {
  const total = segments.reduce((s, x) => s + x.value, 0) || 1;
  const r = (size - stroke) / 2;
  const c = 2 * Math.PI * r;
  const cx = size / 2;
  const cy = size / 2;

  let offset = 0;
  return (
    <div className="relative inline-grid place-items-center" style={{ width: size, height: size }}>
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} style={{ transform: "rotate(-90deg)" }}>
        <circle cx={cx} cy={cy} r={r} fill="none" stroke="var(--color-hair)" strokeWidth={stroke} />
        {segments.map((seg) => {
          const frac = seg.value / total;
          const len = frac * c;
          const node = (
            <motion.circle
              key={seg.label}
              cx={cx}
              cy={cy}
              r={r}
              fill="none"
              stroke={seg.color}
              strokeWidth={stroke}
              strokeLinecap="butt"
              strokeDasharray={`${len} ${c - len}`}
              initial={{ strokeDashoffset: -offset, opacity: 0 }}
              animate={{ strokeDashoffset: -offset, opacity: seg.value > 0 ? 1 : 0 }}
              transition={{ duration: 0.8, ease: [0.16, 1, 0.3, 1] }}
            />
          );
          offset += len;
          return node;
        })}
      </svg>
      {(centerTop || centerSub) && (
        <div className="absolute flex flex-col items-center">
          {centerTop && <span className="tnum text-[28px] font-bold leading-none text-ink">{centerTop}</span>}
          {centerSub && <span className="eyebrow mt-1">{centerSub}</span>}
        </div>
      )}
    </div>
  );
}
