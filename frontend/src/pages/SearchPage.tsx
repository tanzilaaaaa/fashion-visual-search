import { useCallback, useState } from "react";
import { api, imageSrc } from "../api/client";
import type { ScoredItem } from "../api/types";
import { FilterPanel } from "../components/FilterPanel";
import { ImageDropzone } from "../components/ImageDropzone";
import { ImageModal } from "../components/ImageModal";
import { RankingControls } from "../components/RankingControls";
import { ResultGrid, ResultGridSkeleton } from "../components/ResultGrid";
import { SearchBar } from "../components/SearchBar";
import { EmptyState, ErrorState } from "../components/States";
import { SlidersIcon } from "../components/Icons";
import { useSearch } from "../context/SearchContext";
import { useAsync } from "../hooks/useAsync";
import { useSearchHistory } from "../hooks/useSearchHistory";
import { humanise, percent } from "../lib/format";

export function SearchPage() {
  const s = useSearch();
  const vocab = useAsync(() => api.filters(), []);
  const { history, add, clear } = useSearchHistory();
  const [expanded, setExpanded] = useState<ScoredItem | null>(null);
  const [showFilters, setShowFilters] = useState(false);
  const closeModal = useCallback(() => setExpanded(null), []);
  const busy = s.status === "loading";

  const onText = (q: string) => {
    add(q);
    void s.searchText(q);
  };

  return (
    <div className="mx-auto max-w-7xl px-4 pb-16 sm:px-6">
      <section className="py-8 sm:py-10">
        <h1 className="font-display text-3xl font-semibold tracking-tight sm:text-4xl">
          Find it by how it <em className="text-accent">looks</em>.
        </h1>
        <p className="mt-2 max-w-2xl text-ink-soft">
          Describe a piece in your own words or upload a photo. CLIP maps both into the same visual space as the catalogue,
          so you don't need to know any tags.
        </p>
        <div className="mt-6 grid gap-4 lg:grid-cols-[1fr_22rem]">
          <SearchBar
            initial={s.lastQuery?.kind === "text" ? s.lastQuery.text : ""}
            busy={busy}
            history={history}
            onSearch={onText}
            onClearHistory={clear}
          />
          <ImageDropzone
            busy={busy}
            previewUrl={s.lastQuery?.kind === "image" ? s.lastQuery.previewUrl : null}
            onFile={(f) => void s.searchImage(f)}
          />
        </div>
      </section>

      <div className="grid gap-8 lg:grid-cols-[15rem_1fr]">
        <aside className="lg:sticky lg:top-24 lg:self-start">
          <button
            type="button"
            className="mb-4 inline-flex items-center gap-2 rounded-lg border border-stone-300 bg-white px-3 py-2 text-sm font-medium lg:hidden"
            aria-expanded={showFilters}
            aria-controls="refine"
            onClick={() => setShowFilters((v) => !v)}
          >
            <SlidersIcon width={16} height={16} /> Refine results
          </button>
          <div id="refine" className={`${showFilters ? "block" : "hidden"} space-y-8 lg:block`}>
            <RankingControls value={s.ranking} onChange={s.setRanking} disabled={busy} />
            {vocab.error ? (
              <p className="text-sm text-ink-muted">Filters are unavailable right now.</p>
            ) : (
              <FilterPanel vocab={vocab.data} value={s.filters} onChange={s.setFilters} disabled={busy} />
            )}
          </div>
        </aside>

        <section aria-live="polite" aria-busy={busy}>
          {s.status === "idle" && (
            <EmptyState title="Start with a description or a photo">
              Try “black oversized hoodie”, or drop in a picture of something you liked.
            </EmptyState>
          )}
          {busy && <ResultGridSkeleton count={8} />}
          {s.status === "error" && s.error && <ErrorState error={s.error} onRetry={s.rerun} />}
          {s.status === "success" && s.response && (
            <>
              <div className="mb-4 flex flex-wrap items-center gap-x-3 gap-y-2 text-sm">
                {s.lastQuery?.kind === "image" && (
                  <img src={s.lastQuery.previewUrl} alt="Query" className="h-10 w-8 rounded object-cover" />
                )}
                <p className="text-ink-soft">
                  <span className="font-semibold text-ink">{s.response.total}</span> results
                  {s.response.query && (
                    <>
                      {" "}for <span className="font-medium text-ink">“{s.response.query}”</span>
                    </>
                  )}
                  <span className="text-ink-muted"> · {Math.round(s.response.latency_ms)} ms</span>
                </p>
                <DetectedChips response={s.response} />
              </div>
              {s.response.total === 0 ? (
                <EmptyState title="No matching items found">
                  Nothing in the catalogue matches these filters. Remove a filter or broaden your description.
                </EmptyState>
              ) : (
                <ResultGrid items={s.response.results} onExpand={setExpanded} />
              )}
            </>
          )}
        </section>
      </div>
      <ImageModal item={expanded} onClose={closeModal} />
      {/* Preload hint so the first thumbnail paints quickly after a search. */}
      {s.response?.results[0] && <link rel="preload" as="image" href={imageSrc(s.response.results[0].image_url)} />}
    </div>
  );
}

function DetectedChips({ response }: { response: NonNullable<ReturnType<typeof useSearch>["response"]> }) {
  const chips: string[] = [];
  if (response.mode === "text") {
    if (response.detected.colours.length) chips.push(...response.detected.colours.map(humanise));
    if (response.detected.categories.length) {
      const cats = response.detected.categories;
      chips.push(cats.length > 2 ? `${cats.length} related categories` : cats.map(humanise).join(" / "));
    }
  } else if (response.inferred) {
    const { category, colour } = response.inferred;
    if (colour) chips.push(`${humanise(colour.label)} (${percent(colour.confidence)})`);
    if (category) chips.push(`${humanise(category.label)} (${percent(category.confidence)})`);
  }
  if (!chips.length) return null;
  return (
    <div className="flex flex-wrap items-center gap-1.5">
      <span className="text-xs text-ink-muted">{response.mode === "text" ? "Understood:" : "Looks like:"}</span>
      {chips.map((c) => (
        <span key={c} className="rounded-full bg-accent-soft px-2 py-0.5 text-xs font-medium text-accent">
          {c}
        </span>
      ))}
    </div>
  );
}
