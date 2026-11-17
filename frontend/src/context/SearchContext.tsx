import { createContext, useCallback, useContext, useMemo, useRef, useState, type ReactNode } from "react";
import { api, ApiError, toApiError } from "../api/client";
import type { Filters, RankingOptions, SearchResponse } from "../api/types";

export type SearchStatus = "idle" | "loading" | "success" | "error";

export type LastQuery = { kind: "text"; text: string } | { kind: "image"; file: File; previewUrl: string };

interface SearchState {
  status: SearchStatus;
  response: SearchResponse | null;
  error: ApiError | null;
  lastQuery: LastQuery | null;
  filters: Filters;
  ranking: RankingOptions;
}

interface SearchContextValue extends SearchState {
  searchText: (text: string) => Promise<void>;
  searchImage: (file: File) => Promise<void>;
  setFilters: (f: Filters) => void;
  setRanking: (r: RankingOptions) => void;
  rerun: () => void;
  reset: () => void;
}

export const DEFAULT_RANKING: RankingOptions = { topK: 24, alpha: 0.85, beta: 0.15 };

const SearchContext = createContext<SearchContextValue | null>(null);

export function SearchProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<SearchState>({
    status: "idle",
    response: null,
    error: null,
    lastQuery: null,
    filters: {},
    ranking: DEFAULT_RANKING,
  });
  const abortRef = useRef<AbortController | null>(null);
  const stateRef = useRef(state);
  stateRef.current = state;

  const run = useCallback(async (query: LastQuery, filters: Filters, ranking: RankingOptions) => {
    abortRef.current?.abort();
    const ctrl = new AbortController();
    abortRef.current = ctrl;
    setState((s) => {
      if (s.lastQuery?.kind === "image" && s.lastQuery !== query) URL.revokeObjectURL(s.lastQuery.previewUrl);
      return { ...s, status: "loading", error: null, lastQuery: query, filters, ranking };
    });
    try {
      const response =
        query.kind === "text"
          ? await api.searchText(query.text, filters, ranking, ctrl.signal)
          : await api.searchImage(query.file, filters, ranking, ctrl.signal);
      if (!ctrl.signal.aborted) setState((s) => ({ ...s, status: "success", response }));
    } catch (e) {
      const err = toApiError(e);
      if (ctrl.signal.aborted || err.message === "canceled") return;
      setState((s) => ({ ...s, status: "error", error: err }));
    }
  }, []);

  const searchText = useCallback(
    (text: string) => run({ kind: "text", text }, stateRef.current.filters, stateRef.current.ranking),
    [run],
  );

  const searchImage = useCallback(
    (file: File) =>
      run(
        { kind: "image", file, previewUrl: URL.createObjectURL(file) },
        stateRef.current.filters,
        stateRef.current.ranking,
      ),
    [run],
  );

  const setFilters = useCallback(
    (filters: Filters) => {
      const { lastQuery, ranking } = stateRef.current;
      if (lastQuery) void run(lastQuery, filters, ranking);
      else setState((s) => ({ ...s, filters }));
    },
    [run],
  );

  const setRanking = useCallback(
    (ranking: RankingOptions) => {
      const { lastQuery, filters } = stateRef.current;
      if (lastQuery) void run(lastQuery, filters, ranking);
      else setState((s) => ({ ...s, ranking }));
    },
    [run],
  );

  const rerun = useCallback(() => {
    const { lastQuery, filters, ranking } = stateRef.current;
    if (lastQuery) void run(lastQuery, filters, ranking);
  }, [run]);

  const reset = useCallback(() => {
    abortRef.current?.abort();
    setState((s) => {
      if (s.lastQuery?.kind === "image") URL.revokeObjectURL(s.lastQuery.previewUrl);
      return { ...s, status: "idle", response: null, error: null, lastQuery: null };
    });
  }, []);

  const value = useMemo(
    () => ({ ...state, searchText, searchImage, setFilters, setRanking, rerun, reset }),
    [state, searchText, searchImage, setFilters, setRanking, rerun, reset],
  );
  return <SearchContext.Provider value={value}>{children}</SearchContext.Provider>;
}

export function useSearch() {
  const ctx = useContext(SearchContext);
  if (!ctx) throw new Error("useSearch must be used inside <SearchProvider>");
  return ctx;
}
