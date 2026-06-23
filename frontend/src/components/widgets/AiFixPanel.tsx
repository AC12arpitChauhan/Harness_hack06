import { useEffect, useState } from "react";
import { CheckCircle2, ExternalLink, RefreshCw, Wrench } from "lucide-react";
import { useAiFix } from "../../lib/queries";
import { Markdown } from "../primitives/Markdown";
import { Skeleton } from "../primitives/States";

/** On-demand "how do I fix this failing build?" panel for the PR drawer.
 *  Every click of the button hits the AI fresh (Suggest a fix → Regenerate). */
export function AiFixPanel({ repoId, prId }: { repoId: string | undefined; prId: string | undefined }) {
  const [requested, setRequested] = useState(false);
  // Reset when the drawer switches to a different PR.
  useEffect(() => setRequested(false), [prId]);

  const q = useAiFix(repoId, prId, requested);
  const data = q.data;

  // First click enables the query; every later click forces a fresh AI call.
  const ask = () => {
    if (!requested) setRequested(true);
    else q.refetch();
  };

  const buttonLabel = q.isFetching ? "Thinking…" : data || q.isError ? "Regenerate" : "Suggest a fix";

  return (
    <div className="rounded-2xl border border-hair bg-surface p-5">
      <div className="flex items-center justify-between gap-3">
        <span className="eyebrow flex items-center gap-2">
          <Wrench size={14} className="text-accent" /> AI fix suggestion
        </span>
        <button
          onClick={ask}
          disabled={q.isFetching}
          className="inline-flex items-center gap-1.5 rounded-full border border-hair-strong bg-canvas-deep px-3 py-1.5 text-[12px] font-semibold text-ink transition hover:border-ink/30 disabled:opacity-50"
        >
          {q.isFetching ? (
            <RefreshCw size={12} className="animate-spin" />
          ) : (
            data && <RefreshCw size={12} />
          )}
          {buttonLabel}
        </button>
      </div>

      {!requested && (
        <p className="mt-2 text-[12.5px] leading-snug text-ink-soft">
          Ask the model how to get this PR's failing checks to pass. Each click queries the AI fresh.
        </p>
      )}

      {requested && q.isFetching && (
        <div className="mt-3 flex flex-col gap-2">
          <Skeleton className="h-4 w-full" />
          <Skeleton className="h-4 w-5/6" />
          <Skeleton className="h-4 w-2/3" />
        </div>
      )}

      {requested && q.isError && !q.isFetching && (
        <p className="mt-2 text-[12.5px] text-risk">
          Couldn't generate a suggestion. {(q.error as Error)?.message ?? "Try again."}
        </p>
      )}

      {requested && data && !q.isFetching &&
        (data.has_failures ? (
          <div className="mt-3">
            <div className="mb-3 flex flex-wrap items-center gap-1.5">
              {data.failing_checks.map((c) =>
                c.url ? (
                  <a
                    key={c.name}
                    href={c.url}
                    target="_blank"
                    rel="noreferrer"
                    className="inline-flex items-center gap-1 rounded-full bg-risk-soft px-2.5 py-0.5 text-[11px] font-semibold text-risk"
                  >
                    {c.name}
                    <ExternalLink size={10} />
                  </a>
                ) : (
                  <span
                    key={c.name}
                    className="inline-flex items-center rounded-full bg-risk-soft px-2.5 py-0.5 text-[11px] font-semibold text-risk"
                  >
                    {c.name}
                  </span>
                ),
              )}
              {data.model && (
                <span className="mono ml-auto rounded-full bg-canvas-deep px-2 py-0.5 text-[10px] text-ink-soft">
                  {data.model}
                </span>
              )}
            </div>
            <Markdown text={data.suggestion} />
          </div>
        ) : (
          <div className="mt-3 flex items-center gap-2 rounded-xl bg-health-soft px-3 py-2 text-[13px] font-medium text-health">
            <CheckCircle2 size={15} />
            No failing checks — nothing to fix here.
          </div>
        ))}
    </div>
  );
}
