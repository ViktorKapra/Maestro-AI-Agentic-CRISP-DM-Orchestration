/**
 * Lightweight loading placeholder — a few pulsing bars inside a card, so a
 * page that is still fetching reads as "loading" rather than "broken/empty".
 */
export function Loading({ label = "Loading…" }: { label?: string }) {
  return (
    <div
      className="space-y-4"
      role="status"
      aria-live="polite"
      aria-busy="true"
    >
      <span className="sr-only">{label}</span>
      <div className="rounded-2xl border border-surface-border bg-surface-raised p-5">
        <div className="h-5 w-40 animate-pulse rounded bg-surface-border" />
        <div className="mt-4 space-y-3">
          <div className="h-3 w-full animate-pulse rounded bg-surface-border" />
          <div className="h-3 w-5/6 animate-pulse rounded bg-surface-border" />
          <div className="h-3 w-2/3 animate-pulse rounded bg-surface-border" />
        </div>
      </div>
      <div className="grid gap-4 sm:grid-cols-2">
        <div className="h-28 animate-pulse rounded-2xl border border-surface-border bg-surface-raised" />
        <div className="h-28 animate-pulse rounded-2xl border border-surface-border bg-surface-raised" />
      </div>
    </div>
  );
}
