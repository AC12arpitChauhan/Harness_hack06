import { motion } from "framer-motion";

interface Row {
  label: string;
  value: number;
  color: string;
}

interface Props {
  rows: Row[];
  /** Optional max for scaling; defaults to the largest row value. */
  max?: number;
}

/** Thin rounded horizontal bars with a right-aligned tabular count. */
export function SeverityBar({ rows, max }: Props) {
  const top = max ?? Math.max(1, ...rows.map((r) => r.value));
  return (
    <div className="flex flex-col gap-3.5">
      {rows.map((r, i) => (
        <div key={r.label} className="flex items-center gap-3">
          <span className="w-20 shrink-0 text-[12px] font-medium text-ink-soft">{r.label}</span>
          <div className="relative h-2.5 flex-1 overflow-hidden rounded-full bg-canvas-deep">
            <motion.div
              className="absolute inset-y-0 left-0 rounded-full"
              style={{ background: r.color }}
              initial={{ width: 0 }}
              animate={{ width: `${(r.value / top) * 100}%` }}
              transition={{ duration: 0.8, delay: i * 0.05, ease: [0.16, 1, 0.3, 1] }}
            />
          </div>
          <span className="tnum w-7 shrink-0 text-right text-[13px] font-semibold text-ink">
            {r.value}
          </span>
        </div>
      ))}
    </div>
  );
}
