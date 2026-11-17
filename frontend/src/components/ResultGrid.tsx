import type { ScoredItem } from "../api/types";
import { ResultCard, ResultCardSkeleton } from "./ResultCard";

export const gridClass = "grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-4";

export function ResultGrid({ items, onExpand }: { items: ScoredItem[]; onExpand?: (i: ScoredItem) => void }) {
  return (
    <ul className={gridClass} aria-label="Search results">
      {items.map((item, i) => (
        <li key={item.item_id}>
          <ResultCard item={item} rank={i + 1} onExpand={onExpand} />
        </li>
      ))}
    </ul>
  );
}

export function ResultGridSkeleton({ count = 8 }: { count?: number }) {
  return (
    <div className={gridClass} role="status" aria-label="Loading results">
      {Array.from({ length: count }).map((_, i) => (
        <ResultCardSkeleton key={i} />
      ))}
      <span className="sr-only">Searching the catalogue…</span>
    </div>
  );
}
