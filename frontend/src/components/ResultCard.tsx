import { Link } from "react-router-dom";
import type { ScoredItem } from "../api/types";
import { imageSrc } from "../api/client";
import { altText, capitalise, COLOUR_SWATCH, formatScore, SOURCE_LABEL } from "../lib/format";
import { useAccount } from "../context/AccountContext";
import { ExpandIcon, HeartIcon, LayersIcon, SparkIcon } from "./Icons";

interface Props {
  item: ScoredItem;
  rank?: number;
  onExpand?: (item: ScoredItem) => void;
  showReason?: boolean;
  compact?: boolean;
}

export function SaveButton({ itemId, label, className = "" }: { itemId: string; label: string; className?: string }) {
  const { enabled, isFavorite, toggleFavorite } = useAccount();
  if (!enabled) return null;
  const saved = isFavorite(itemId);
  return (
    <button
      type="button"
      onClick={() => void toggleFavorite(itemId)}
      aria-pressed={saved}
      aria-label={saved ? `Remove ${label} from favorites` : `Save ${label} to favorites`}
      title={saved ? "Saved" : "Save"}
      className={`glass grid h-9 w-9 place-items-center rounded-full transition hover:scale-105 focus-visible:outline focus-visible:outline-2 focus-visible:outline-accent ${
        saved ? "text-accent" : "text-ink"
      } ${className}`}
    >
      <HeartIcon width={17} height={17} filled={saved} />
    </button>
  );
}

export function ResultCard({ item, rank, onExpand, showReason, compact }: Props) {
  // CLIP cosine for good matches sits roughly in 0.2–0.4 (text) / 0.6–0.95 (image);
  // the meter shows similarity on a 0–1 scale.
  const meter = Math.max(0.04, Math.min(1, item.similarity));
  return (
    <article className="card group flex h-full flex-col overflow-hidden p-0 transition duration-300 hover:-translate-y-1 hover:border-accent/40 hover:shadow-lift">
      <div className="relative aspect-[3/4] overflow-hidden bg-surface-2">
        <Link
          to={`/app/item/${item.item_id}`}
          className="block h-full focus-visible:outline focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-accent"
        >
          <img
            src={imageSrc(item.image_url)}
            alt={altText(item)}
            loading="lazy"
            decoding="async"
            className="h-full w-full object-contain p-3 transition duration-500 group-hover:scale-[1.05]"
          />
        </Link>
        {rank !== undefined && (
          <span className="glass absolute left-2.5 top-2.5 rounded-full px-2 py-0.5 text-xs font-semibold tabular-nums text-ink">
            #{rank}
          </span>
        )}
        <span
          className="absolute right-2.5 top-2.5 rounded-full bg-ink/85 px-2 py-0.5 text-xs font-semibold tabular-nums text-canvas"
          title={`Final score ${formatScore(item.score)} · cosine similarity ${formatScore(item.similarity)}`}
        >
          {formatScore(item.score)}
        </span>
        <SaveButton itemId={item.item_id} label={altText(item)} className="absolute bottom-2.5 left-2.5" />
        {onExpand && (
          <button
            type="button"
            onClick={() => onExpand(item)}
            className="glass absolute bottom-2.5 right-2.5 rounded-full p-2 text-ink opacity-0 transition group-hover:opacity-100 focus:opacity-100 focus-visible:outline focus-visible:outline-2 focus-visible:outline-accent"
            aria-label={`View ${altText(item)} larger`}
          >
            <ExpandIcon width={16} height={16} />
          </button>
        )}
      </div>
      <div className="flex flex-1 flex-col gap-1.5 p-3.5">
        <h3 className="text-sm font-semibold leading-snug text-ink">{capitalise(item.category)}</h3>
        <div className="flex items-center gap-2 text-xs text-ink-muted">
          <span className="inline-flex items-center gap-1">
            <span className="h-2.5 w-2.5 rounded-full border border-line" style={{ background: COLOUR_SWATCH[item.colour] ?? "#ccc" }} />
            {capitalise(item.colour)}
          </span>
          <span aria-hidden="true">·</span>
          <span>{SOURCE_LABEL[item.source] ?? item.source}</span>
        </div>
        <div className="mt-1 h-1 overflow-hidden rounded-full bg-surface-2" aria-hidden="true">
          <div className="bg-gradient-accent h-full rounded-full" style={{ width: `${meter * 100}%` }} />
        </div>
        {showReason && item.reason && <p className="text-xs leading-relaxed text-ink-soft">{item.reason}</p>}
        {!compact && (
          <div className="mt-auto flex gap-1.5 pt-2.5">
            <Link
              to={`/app/item/${item.item_id}#similar`}
              className="inline-flex flex-1 items-center justify-center gap-1 rounded-full border border-line px-2 py-1.5 text-xs font-medium text-ink-soft transition hover:border-accent hover:text-accent"
            >
              <SparkIcon width={14} height={14} /> Similar
            </Link>
            <Link
              to={`/app/item/${item.item_id}#look`}
              className="inline-flex flex-1 items-center justify-center gap-1 rounded-full border border-line px-2 py-1.5 text-xs font-medium text-ink-soft transition hover:border-accent hover:text-accent"
            >
              <LayersIcon width={14} height={14} /> Look
            </Link>
          </div>
        )}
      </div>
    </article>
  );
}

export function ResultCardSkeleton() {
  return (
    <div className="card overflow-hidden p-0" aria-hidden="true">
      <div className="shimmer aspect-[3/4]" />
      <div className="space-y-2 p-3.5">
        <div className="shimmer h-4 w-2/3 rounded" />
        <div className="shimmer h-3 w-1/2 rounded" />
      </div>
    </div>
  );
}
