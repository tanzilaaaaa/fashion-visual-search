import { Link } from "react-router-dom";
import type { ScoredItem } from "../api/types";
import { imageSrc } from "../api/client";
import { altText, capitalise, COLOUR_SWATCH, formatScore, SOURCE_LABEL } from "../lib/format";
import { ExpandIcon, LayersIcon, SparkIcon } from "./Icons";

interface Props {
  item: ScoredItem;
  rank?: number;
  onExpand?: (item: ScoredItem) => void;
  showReason?: boolean;
  compact?: boolean;
}

export function ResultCard({ item, rank, onExpand, showReason, compact }: Props) {
  return (
    <article className="group flex flex-col overflow-hidden rounded-2xl border border-stone-200 bg-white shadow-card transition hover:-translate-y-0.5 hover:shadow-lg">
      <div className="relative aspect-[3/4] overflow-hidden bg-stone-100">
        <Link to={`/item/${item.item_id}`} className="block h-full focus-visible:outline focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-accent">
          <img
            src={imageSrc(item.image_url)}
            alt={altText(item)}
            loading="lazy"
            decoding="async"
            className="h-full w-full object-contain p-2 transition duration-300 group-hover:scale-[1.03]"
          />
        </Link>
        {rank !== undefined && (
          <span className="absolute left-2 top-2 rounded-full bg-white/90 px-2 py-0.5 text-xs font-semibold tabular-nums text-ink-soft shadow-sm">
            #{rank}
          </span>
        )}
        <span
          className="absolute right-2 top-2 rounded-full bg-ink/85 px-2 py-0.5 text-xs font-semibold tabular-nums text-white"
          title={`Final score ${formatScore(item.score)} · cosine similarity ${formatScore(item.similarity)}`}
        >
          {formatScore(item.score)}
        </span>
        {onExpand && (
          <button
            type="button"
            onClick={() => onExpand(item)}
            className="absolute bottom-2 right-2 rounded-full bg-white/90 p-1.5 text-ink-soft opacity-0 shadow-sm transition group-hover:opacity-100 focus:opacity-100 focus-visible:outline focus-visible:outline-2 focus-visible:outline-accent"
            aria-label={`View ${altText(item)} larger`}
          >
            <ExpandIcon width={16} height={16} />
          </button>
        )}
      </div>
      <div className="flex flex-1 flex-col gap-1.5 p-3">
        <h3 className="text-sm font-semibold leading-snug text-ink">{capitalise(item.category)}</h3>
        <div className="flex items-center gap-2 text-xs text-ink-muted">
          <span className="inline-flex items-center gap-1">
            <span className="h-2.5 w-2.5 rounded-full border border-stone-300" style={{ background: COLOUR_SWATCH[item.colour] ?? "#ccc" }} />
            {capitalise(item.colour)}
          </span>
          <span aria-hidden="true">·</span>
          <span>{SOURCE_LABEL[item.source] ?? item.source}</span>
        </div>
        {showReason && item.reason && <p className="text-xs leading-relaxed text-ink-soft">{item.reason}</p>}
        {!compact && (
          <div className="mt-auto flex gap-1.5 pt-2">
            <Link
              to={`/item/${item.item_id}#similar`}
              className="inline-flex flex-1 items-center justify-center gap-1 rounded-lg border border-stone-300 px-2 py-1.5 text-xs font-medium text-ink-soft transition hover:border-ink hover:text-ink"
            >
              <SparkIcon width={14} height={14} /> Similar
            </Link>
            <Link
              to={`/item/${item.item_id}#look`}
              className="inline-flex flex-1 items-center justify-center gap-1 rounded-lg border border-stone-300 px-2 py-1.5 text-xs font-medium text-ink-soft transition hover:border-ink hover:text-ink"
            >
              <LayersIcon width={14} height={14} /> Complete look
            </Link>
          </div>
        )}
      </div>
    </article>
  );
}

export function ResultCardSkeleton() {
  return (
    <div className="overflow-hidden rounded-2xl border border-stone-200 bg-white" aria-hidden="true">
      <div className="aspect-[3/4] animate-pulse bg-stone-200" />
      <div className="space-y-2 p-3">
        <div className="h-4 w-2/3 animate-pulse rounded bg-stone-200" />
        <div className="h-3 w-1/2 animate-pulse rounded bg-stone-200" />
      </div>
    </div>
  );
}
