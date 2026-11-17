import axios, { AxiosError } from "axios";
import type {
  EvaluationReport,
  Filters,
  FiltersResponse,
  HealthResponse,
  ItemDetail,
  RankingOptions,
  RecommendationsResponse,
  SearchResponse,
  SessionResponse,
  SimilarResponse,
} from "./types";

export const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000").replace(/\/$/, "");

export const http = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30_000,
  withCredentials: true, // needed for the optional session cookie
});

/** A user-presentable error, normalised from the API's `{error: {code, message}}` body. */
export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
    public code: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

export function toApiError(err: unknown): ApiError {
  if (err instanceof ApiError) return err;
  const ax = err as AxiosError<{ error?: { code?: string; message?: string } }>;
  if (ax?.isAxiosError) {
    if (!ax.response) {
      const msg =
        ax.code === "ECONNABORTED"
          ? "The server took too long to respond. It may be waking up — please try again."
          : "Can't reach the search server. Check your connection or try again in a moment.";
      return new ApiError(msg, 0, "network_error");
    }
    const body = ax.response.data?.error;
    return new ApiError(
      body?.message ?? `Request failed (${ax.response.status}).`,
      ax.response.status,
      body?.code ?? "http_error",
    );
  }
  return new ApiError("Something unexpected happened.", 0, "unknown");
}

async function call<T>(p: Promise<{ data: T }>): Promise<T> {
  try {
    return (await p).data;
  } catch (e) {
    throw toApiError(e);
  }
}

export const imageSrc = (path: string) => (path.startsWith("http") ? path : `${API_BASE_URL}${path}`);

export const api = {
  searchText: (query: string, filters: Filters, opts: RankingOptions, signal?: AbortSignal) =>
    call<SearchResponse>(
      http.post(
        "/search/text",
        { query, top_k: opts.topK, filters, alpha: opts.alpha, beta: opts.beta },
        { signal },
      ),
    ),

  searchImage: (file: File, filters: Filters, opts: RankingOptions, signal?: AbortSignal) => {
    const form = new FormData();
    form.append("file", file);
    form.append("top_k", String(opts.topK));
    form.append("filters", JSON.stringify(filters));
    form.append("alpha", String(opts.alpha));
    form.append("beta", String(opts.beta));
    return call<SearchResponse>(http.post("/search/image", form, { signal }));
  },

  item: (id: string) => call<ItemDetail>(http.get(`/items/${encodeURIComponent(id)}`)),
  similar: (id: string, topK = 12) =>
    call<SimilarResponse>(http.get(`/items/${encodeURIComponent(id)}/similar`, { params: { top_k: topK } })),
  recommendations: (id: string, perGroup = 6) =>
    call<RecommendationsResponse>(
      http.get(`/items/${encodeURIComponent(id)}/recommendations`, { params: { per_group: perGroup } }),
    ),
  filters: () => call<FiltersResponse>(http.get("/filters")),
  health: () => call<HealthResponse>(http.get("/health")),
  evaluation: () => call<EvaluationReport>(http.get("/evaluation")),
  me: () => call<SessionResponse>(http.get("/auth/me")),
  login: (username: string, password: string) =>
    call<SessionResponse>(http.post("/auth/login", { username, password })),
  logout: () => call<SessionResponse>(http.post("/auth/logout")),
};
