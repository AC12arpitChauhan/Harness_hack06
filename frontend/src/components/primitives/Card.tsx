import { motion } from "framer-motion";
import type { ReactNode } from "react";

interface CardProps {
  children: ReactNode;
  className?: string;
  /** Stagger index for entrance animation. */
  index?: number;
  /** Removes default padding (for edge-to-edge content like lists). */
  flush?: boolean;
  onClick?: () => void;
}

export function Card({ children, className = "", index = 0, flush = false, onClick }: CardProps) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 14 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, delay: Math.min(index, 8) * 0.045, ease: [0.16, 1, 0.3, 1] }}
      onClick={onClick}
      className={`card ${flush ? "" : "p-6 md:p-7"} ${onClick ? "cursor-pointer" : ""} ${className}`}
    >
      {children}
    </motion.div>
  );
}

interface CardHeadProps {
  eyebrow?: string;
  title?: ReactNode;
  right?: ReactNode;
  className?: string;
}

/** Editorial card header: tracked uppercase eyebrow + serif title, optional right slot. */
export function CardHead({ eyebrow, title, right, className = "" }: CardHeadProps) {
  return (
    <div className={`flex items-start justify-between gap-4 ${className}`}>
      <div className="min-w-0">
        {eyebrow && <div className="eyebrow mb-1.5">{eyebrow}</div>}
        {title && (
          <h3 className="display text-[26px] md:text-[30px] text-ink leading-none">{title}</h3>
        )}
      </div>
      {right && <div className="shrink-0">{right}</div>}
    </div>
  );
}
