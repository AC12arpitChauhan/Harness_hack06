import { useEffect, useRef, useState } from "react";

interface Props {
  value: number | null | undefined;
  /** Decimal places. */
  digits?: number;
  duration?: number;
  className?: string;
  placeholder?: string;
}

/** Count-up number with tabular figures. Respects reduced-motion via short duration. */
export function AnimatedNumber({
  value,
  digits = 0,
  duration = 900,
  className = "",
  placeholder = "—",
}: Props) {
  const [display, setDisplay] = useState(0);
  const fromRef = useRef(0);
  const rafRef = useRef<number | null>(null);

  useEffect(() => {
    if (value === null || value === undefined || Number.isNaN(value)) return;
    const from = fromRef.current;
    const to = value;
    const start = performance.now();
    const tick = (now: number) => {
      const t = Math.min(1, (now - start) / duration);
      // easeOutCubic
      const eased = 1 - Math.pow(1 - t, 3);
      setDisplay(from + (to - from) * eased);
      if (t < 1) rafRef.current = requestAnimationFrame(tick);
      else fromRef.current = to;
    };
    rafRef.current = requestAnimationFrame(tick);
    return () => {
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
    };
  }, [value, duration]);

  if (value === null || value === undefined || Number.isNaN(value)) {
    return <span className={`tnum ${className}`}>{placeholder}</span>;
  }
  return <span className={`tnum ${className}`}>{display.toFixed(digits)}</span>;
}
