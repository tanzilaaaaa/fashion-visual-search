import type { ReactNode } from "react";
import type { ApiError } from "../api/client";
import { AlertIcon, HangerIcon } from "./Icons";

/** Error state: something went wrong. Visually distinct from the empty state (PRD §4.2). */
export function ErrorState({ error, onRetry }: { error: ApiError; onRetry?: () => void }) {
  return (
    <div role="alert" data-testid="error-state" className="flex items-start gap-4 rounded-theme border border-danger/30 bg-danger-soft p-5 text-ink">
      <span className="grid h-10 w-10 shrink-0 place-items-center rounded-full bg-danger/15 text-danger">
        <AlertIcon />
      </span>
      <div className="flex-1">
        <p className="font-semibold">We couldn't complete that request</p>
        <p className="mt-1 text-sm text-ink-soft">{error.message}</p>
        {onRetry && error.status !== 400 && error.status !== 413 && (
          <button onClick={onRetry} className="btn mt-3 bg-danger px-4 py-1.5 text-canvas hover:opacity-90">
            Try again
          </button>
        )}
      </div>
    </div>
  );
}

/** Empty state: the request worked, nothing matched. */
export function EmptyState({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <div data-testid="empty-state" className="flex flex-col items-center rounded-theme border border-dashed border-line bg-surface/60 px-6 py-16 text-center">
      <span className="grid h-16 w-16 place-items-center rounded-full bg-accent-soft text-accent">
        <HangerIcon width={28} height={28} />
      </span>
      <p className="mt-5 font-display text-xl font-semibold text-ink">{title}</p>
      {children && <div className="mt-1.5 max-w-md text-sm text-ink-muted">{children}</div>}
    </div>
  );
}
