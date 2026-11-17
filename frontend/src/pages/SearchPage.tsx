import { useCallback, useState } from "react";
import { api, imageSrc } from "../api/client";
import type { ScoredItem } from "../api/types";
import { FilterPanel } from "../components/FilterPanel";
import { SlidersIcon } from "../components/Icons";
import { ImageDropzone } from "../components/ImageDropzone";
import { ImageModal } from "../components/ImageModal";
import { RankingControls } from "../components/RankingControls";
import { ResultGrid, ResultGridSkeleton } from "../components/ResultGrid";
import { SearchBar } from "../components/SearchBar";
import { EmptyState, ErrorState } from "../components/States";
import { useAuth } from "../context/AuthContext";
import { useSearch } from "../context/SearchContext";
import { useAsync } from "../hooks/useAsync";
import { useSearchHistory } from "../hooks/useSearchHistory";
import { humanise, percent } from "../lib/format";

function greeting(now = new Date()) {
  const h = now.getHours();
  return h < 12 ? "Good morning" : h < 18 ? "Good afternoon" : "Good evening";
}

export function SearchPage() {
  const s = useSearch();
  const { user } = useAuth();
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
    <div className="mx-auto max-w-7xl px-4 pb-20 sm:px-6">
      <section className="py-10 sm:py-14">
        <p className="eyebrow">{user ? `${greeting()}, ${user.name.split(" ")[0]}` : "Visual search"}</p>
        <h1 className="mt-3 font-display text-4xl font-semibold tracking-tight text-ink sm:text-5xl">
          Find it by how it <span className="text-gradient italic">looks</span>.
        </h1>
        <p className="mt-3 max-w-2xl text-ink-soft">
          Describe a piece in your own words or upload a photo. CLIP maps both into the same visual space as the
          catalogue, so you never need to know a tag.
        </p>
        <div className="glass mt-8 space-y-4 rounded-[calc(var(--radius)*1.5)] p-4 shadow-lift sm:p-5">
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

      <div className="grid gap-8 lg:grid-cols-[16rem_1fr]">
        <aside className="lg:sticky lg:top-24 lg:self-start">
          <button
            type="button"
            className="btn-ghost mb-4 lg:hidden"
            aria-expanded={showFilters}
            aria-controls="refine"
            onClick={() => setShowFilters((v) => !v)}
          >
            <SlidersIcon width={16} height={16} /> Refine results
          </button>
          <div id="refine" className={`${showFilters ? "block" : "hidden"} card space-y-8 p-5 lg:block`}>
            <RankingControls value={s.ranking} onChange={s.setRanking} disabled={busy} />
            <div className="h-px bg-line" />
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
              <div className="mb-5 flex flex-wrap items-center gap-x-3 gap-y-2 text-sm">
                {s.lastQuery?.kind === "image" && (
                  <img src={s.lastQuery.previewUrl} alt="Query" className="h-10 w-8 rounded-md object-cover ring-1 ring-line" />
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
        <span key={c} className="rounded-full bg-accent-soft px-2.5 py-0.5 text-xs font-medium text-accent">
          {c}
        </span>
      ))}
    </div>
  );
}
