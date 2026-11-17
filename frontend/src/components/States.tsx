import type { ReactNode } from "react";
import type { ApiError } from "../api/client";
import { AlertIcon, HangerIcon } from "./Icons";

/** Error state — something went wrong. Visually distinct from the empty state (PRD §4.2). */
export function ErrorState({ error, onRetry }: { error: ApiError; onRetry?: () => void }) {
  return (
    <div role="alert" data-testid="error-state" className="flex items-start gap-4 rounded-2xl border border-rose-200 bg-rose-50 p-5 text-rose-900">
      <AlertIcon className="mt-0.5 shrink-0 text-rose-600" />
      <div className="flex-1">
        <p className="font-semibold">We couldn't complete that search</p>
        <p className="mt-1 text-sm text-rose-800">{error.message}</p>
        {onRetry && error.status !== 400 && error.status !== 413 && (
          <button onClick={onRetry} className="mt-3 rounded-lg bg-rose-700 px-3 py-1.5 text-sm font-semibold text-white hover:bg-rose-800">
            Try again
          </button>
        )}
      </div>
    </div>
  );
}

/** Empty state — the request worked, nothing matched. */
export function EmptyState({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <div data-testid="empty-state" className="flex flex-col items-center rounded-2xl border border-dashed border-stone-300 bg-white px-6 py-14 text-center">
      <span className="grid h-14 w-14 place-items-center rounded-full bg-stone-100 text-ink-muted">
        <HangerIcon width={26} height={26} />
      </span>
      <p className="mt-4 font-display text-lg font-semibold">{title}</p>
      {children && <div className="mt-1 max-w-md text-sm text-ink-muted">{children}</div>}
    </div>
  );
}
