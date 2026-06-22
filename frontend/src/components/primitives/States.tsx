import { AlertCircle, Inbox, RefreshCw } from "lucide-react";

export function Skeleton({ className = "" }: { className?: string }) {
  return <div className={`skeleton ${className}`} />;
}

export function ErrorState({
  message,
  onRetry,
}: {
  message?: string;
  onRetry?: () => void;
}) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 py-10 text-center">
      <AlertCircle size={22} className="text-risk" />
      <p className="max-w-sm text-sm text-ink-soft">
        {message ?? "Something went wrong loading this data."}
      </p>
      {onRetry && (
        <button
          onClick={onRetry}
          className="inline-flex items-center gap-1.5 rounded-full border border-hair-strong px-3.5 py-1.5 text-[12px] font-semibold text-ink transition hover:bg-canvas-deep"
        >
          <RefreshCw size={13} /> Retry
        </button>
      )}
    </div>
  );
}

export function EmptyState({ title, hint }: { title: string; hint?: string }) {
  return (
    <div className="flex flex-col items-center justify-center gap-2 py-10 text-center">
      <Inbox size={22} className="text-ink-mute" />
      <p className="text-sm font-semibold text-ink">{title}</p>
      {hint && <p className="max-w-sm text-[13px] text-ink-mute">{hint}</p>}
    </div>
  );
}
