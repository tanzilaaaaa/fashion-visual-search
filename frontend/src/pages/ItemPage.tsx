import { useEffect } from "react";
import { Link, useLocation, useNavigate, useParams } from "react-router-dom";
import { api, imageSrc } from "../api/client";
import type { ScoredItem } from "../api/types";
import { CollectionMenu } from "../components/CollectionMenu";
import { ArrowLeftIcon, HeartIcon, LayersIcon, SparkIcon } from "../components/Icons";
import { useAccount } from "../context/AccountContext";
import { ResultCard, ResultCardSkeleton } from "../components/ResultCard";
import { EmptyState, ErrorState } from "../components/States";
import { useAsync } from "../hooks/useAsync";
import { altText, capitalise, COLOUR_SWATCH, percent, SOURCE_LABEL } from "../lib/format";

export function ItemPage() {
  const { id = "" } = useParams();
  const navigate = useNavigate();
  const { hash } = useLocation();
  const item = useAsync(() => api.item(id), [id]);
  const similar = useAsync(() => api.similar(id, 8), [id]);
  const look = useAsync(() => api.recommendations(id, 4), [id]);

  useEffect(() => {
    window.scrollTo({ top: 0 });
  }, [id]);
  useEffect(() => {
    if (hash && !item.loading) document.getElementById(hash.slice(1))?.scrollIntoView({ behavior: "smooth" });
  }, [hash, item.loading]);

  if (item.error) {
    return (
      <div className="mx-auto max-w-3xl px-4 py-16">
        {item.error.status === 404 ? (
          <EmptyState title="We couldn't find that item">
            It may not be part of this catalogue. <Link to="/app" className="font-medium text-accent underline">Back to search</Link>
          </EmptyState>
        ) : (
          <ErrorState error={item.error} onRetry={item.reload} />
        )}
      </div>
    );
  }

  const d = item.data;
  return (
    <div className="mx-auto max-w-7xl px-4 pb-16 sm:px-6">
      <button onClick={() => navigate(-1)} className="mt-8 inline-flex items-center gap-1.5 text-sm font-medium text-ink-soft hover:text-ink">
        <ArrowLeftIcon width={16} height={16} /> Back to results
      </button>

      <section className="mt-6 grid gap-8 md:grid-cols-[minmax(0,22rem)_1fr]">
        <div className="card aspect-[3/4] overflow-hidden p-0 shadow-lift">
          {d ? (
            <img src={imageSrc(d.image_url)} alt={altText(d)} className="h-full w-full bg-surface-2 object-contain p-5" />
          ) : (
            <div className="shimmer h-full" />
          )}
        </div>
        <div>
          {d ? (
            <>
              <p className="eyebrow">{SOURCE_LABEL[d.source] ?? d.source} photo</p>
              <h1 className="mt-2 font-display text-4xl font-semibold tracking-tight text-ink sm:text-5xl">{capitalise(d.category)}</h1>
              <dl className="card mt-6 grid max-w-lg grid-cols-2 gap-x-6 gap-y-4 p-5 text-sm">
                <Meta label="Colour">
                  <span className="inline-flex items-center gap-1.5">
                    <span className="h-3 w-3 rounded-full border border-line" style={{ background: COLOUR_SWATCH[d.colour] ?? "#ccc" }} />
                    {capitalise(d.colour)} <span className="text-ink-muted">({percent(d.colour_confidence)} conf.)</span>
                  </span>
                </Meta>
                <Meta label="Viewpoint">{capitalise(d.viewpoint)}</Meta>
                <Meta label="Occlusion">{capitalise(d.occlusion)}</Meta>
                <Meta label="Scale">{capitalise(d.scale)}</Meta>
                <Meta label="Item ID"><code className="text-xs">{d.item_id}</code></Meta>
                <Meta label="Worn with">{d.worn_with.length ? `${d.worn_with.length} item(s) in photo` : "—"}</Meta>
              </dl>
              <p className="mt-6 max-w-md text-xs leading-relaxed text-ink-muted">
                Colour is inferred zero-shot by CLIP — DeepFashion2 doesn't label colour. Category, viewpoint, occlusion and
                scale come from the dataset's annotations.
              </p>
              <div className="mt-6 flex flex-wrap gap-2">
                <ItemSaveButton itemId={d.item_id} />
                <CollectionMenu itemId={d.item_id} />
              </div>
              <div className="mt-2 flex flex-wrap gap-2">
                <a href="#similar" className="btn-primary">
                  <SparkIcon width={16} height={16} /> Find similar
                </a>
                <a href="#look" className="btn-ghost">
                  <LayersIcon width={16} height={16} /> Complete the look
                </a>
              </div>
            </>
          ) : (
            <div className="space-y-3">
              <div className="shimmer h-4 w-24 rounded" />
              <div className="shimmer h-8 w-64 rounded" />
            </div>
          )}
        </div>
      </section>

      <Panel id="similar" title="Find Similar" subtitle="Nearest neighbours of this item's own embedding in the fine-tuned CLIP space.">
        {similar.error ? (
          <ErrorState error={similar.error} onRetry={similar.reload} />
        ) : (
          <Row items={similar.data?.results} loading={similar.loading} empty="No similar items found." />
        )}
      </Panel>

      <Panel id="look" title="Complete the Look" subtitle="Pieces from compatible categories, ranked by colour and style coherence.">
        {look.error ? (
          <ErrorState error={look.error} onRetry={look.reload} />
        ) : look.loading ? (
          <Row loading />
        ) : look.data && look.data.groups.some((g) => g.items.length) ? (
          <div className="space-y-8">
            {look.data.groups.map((g) => (
              <div key={g.group}>
                <h3 className="eyebrow mb-3">{g.label}</h3>
                <Row items={g.items} showReason empty={`No ${g.label.toLowerCase()} available.`} />
              </div>
            ))}
          </div>
        ) : (
          <EmptyState title="No complementary items for this category" />
        )}
      </Panel>
    </div>
  );
}

function Meta({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <dt className="text-ink-muted">{label}</dt>
      <dd className="mt-0.5 font-medium text-ink">{children}</dd>
    </div>
  );
}

function Panel({ id, title, subtitle, children }: { id: string; title: string; subtitle: string; children: React.ReactNode }) {
  return (
    <section id={id} className="mt-16 scroll-mt-24" aria-labelledby={`${id}-title`}>
      <h2 id={`${id}-title`} className="font-display text-3xl font-semibold tracking-tight text-ink">{title}</h2>
      <p className="mb-5 mt-1 text-sm text-ink-muted">{subtitle}</p>
      {children}
    </section>
  );
}

function Row({ items, loading, showReason, empty }: { items?: ScoredItem[]; loading?: boolean; showReason?: boolean; empty?: string }) {
  if (loading) {
    return (
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-4" role="status" aria-label="Loading recommendations">
        {Array.from({ length: 4 }).map((_, i) => <ResultCardSkeleton key={i} />)}
      </div>
    );
  }
  if (!items?.length) return <p className="text-sm text-ink-muted">{empty}</p>;
  return (
    <ul className="grid grid-cols-2 gap-4 sm:grid-cols-4">
      {items.map((it) => (
        <li key={it.item_id}><ResultCard item={it} showReason={showReason} compact /></li>
      ))}
    </ul>
  );
}

function ItemSaveButton({ itemId }: { itemId: string }) {
  const { enabled, isFavorite, toggleFavorite } = useAccount();
  if (!enabled) return null;
  const saved = isFavorite(itemId);
  return (
    <button type="button" aria-pressed={saved} onClick={() => void toggleFavorite(itemId)} className={saved ? "btn-primary" : "btn-ghost"}>
      <HeartIcon width={16} height={16} filled={saved} /> {saved ? "Saved" : "Save"}
    </button>
  );
}
