import { motion } from "framer-motion";
import { Sparkles, Lightbulb } from "lucide-react";
import { usePRDetail } from "../../lib/queries";
import { Skeleton } from "../primitives/States";

interface Props {
  repoId: string | undefined;
  prId: string | undefined;
}

/** Inverted ink card showcasing the LLM narration (Bedrock) for the featured PR. */
export function AiInsight({ repoId, prId }: Props) {
  const { data, isLoading } = usePRDetail(repoId, prId);
  const narrative = data?.narrative;
  const model = narrative?.ai_model ?? "";
  const isTemplated = model === "" || model.includes("templated") || model.includes("fallback");
  const modelLabel = isTemplated ? "Templated narration" : model;

  return (
    <motion.div
      initial={{ opacity: 0, y: 14 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.55, delay: 0.18, ease: [0.16, 1, 0.3, 1] }}
      className="relative flex h-full flex-col overflow-hidden rounded-[var(--radius-card)] p-7 text-[#e9eaee]"
      style={{ background: "#16171a", boxShadow: "var(--shadow-pop)" }}
    >
      {/* faint editorial corner glyph */}
      <Sparkles
        size={140}
        className="pointer-events-none absolute -right-6 -top-8 opacity-[0.05]"
        strokeWidth={1}
      />

      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="grid h-7 w-7 place-items-center rounded-lg bg-white/10">
            <Sparkles size={15} className="text-[var(--color-accent)]" />
          </span>
          <span className="text-[11px] font-semibold uppercase tracking-[0.14em] text-white/55">
            AI Insight
          </span>
        </div>
        <span
          className="mono rounded-full px-2.5 py-1 text-[10px] font-medium"
          style={{
            background: isTemplated ? "rgba(255,255,255,0.08)" : "var(--color-accent)",
            color: isTemplated ? "rgba(255,255,255,0.6)" : "#1b1205",
          }}
          title={isTemplated ? "Deterministic fallback narrative" : "Generated via AWS Bedrock"}
        >
          {modelLabel}
        </span>
      </div>

      {isLoading ? (
        <div className="mt-6 flex flex-col gap-3">
          <div className="skeleton h-5 w-full" style={{ background: "#23242a" }} />
          <div className="skeleton h-5 w-4/5" style={{ background: "#23242a" }} />
          <div className="skeleton h-5 w-3/5" style={{ background: "#23242a" }} />
        </div>
      ) : !narrative ? (
        <p className="mt-6 text-[15px] leading-relaxed text-white/50">
          No narrative generated for this PR yet. The summary appears once an analysis run completes.
        </p>
      ) : (
        <div className="mt-5 flex min-h-0 flex-1 flex-col">
          {data?.title && (
            <div className="mb-3 text-[12px] text-white/45">
              On <span className="font-semibold text-white/70">#{data.provider_pr_id}</span>{" "}
              {data.title}
            </div>
          )}
          <p className="display text-[23px] leading-[1.18] text-white md:text-[26px]">
            “{narrative.ai_summary}”
          </p>

          {narrative.ai_recommendation && (
            <div className="mt-5 flex items-start gap-2.5 rounded-2xl border border-white/10 bg-white/[0.04] p-4">
              <Lightbulb size={16} className="mt-0.5 shrink-0 text-[var(--color-accent)]" />
              <div>
                <div className="mb-1 text-[10px] font-semibold uppercase tracking-[0.14em] text-white/45">
                  Recommendation
                </div>
                <p className="text-[14px] leading-relaxed text-white/80">
                  {narrative.ai_recommendation}
                </p>
              </div>
            </div>
          )}
        </div>
      )}
    </motion.div>
  );
}
