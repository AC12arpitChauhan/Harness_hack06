import type { ReactNode } from "react";
import { AnimatedNumber } from "./AnimatedNumber";

interface Props {
  label: string;
  value: number | null | undefined;
  digits?: number;
  suffix?: ReactNode;
  accent?: string;
  hint?: ReactNode;
}

/** Big tabular number over a tracked label — the stat-tile building block. */
export function Stat({ label, value, digits = 0, suffix, accent, hint }: Props) {
  return (
    <div className="flex flex-col">
      <span className="eyebrow mb-2">{label}</span>
      <span className="flex items-baseline gap-1">
        <AnimatedNumber
          value={value}
          digits={digits}
          className="text-[38px] font-bold leading-none text-ink"
        />
        {suffix && <span className="text-[15px] font-semibold text-ink-mute">{suffix}</span>}
      </span>
      {hint && <span className="mt-2 text-[12px] text-ink-mute">{hint}</span>}
      {accent && <span className="mt-3 h-[3px] w-9 rounded-full" style={{ background: accent }} />}
    </div>
  );
}
