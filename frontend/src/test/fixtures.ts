import type { FiltersResponse, ScoredItem, SearchResponse } from "../api/types";

export const item = (i: number, over: Partial<ScoredItem> = {}): ScoredItem => ({
  item_id: `train-00000${i}-1`,
  image_url: `/images/train-00000${i}-1`,
  category: "short sleeve dress",
  category_key: "short_sleeve_dress",
  colour: "red",
  source: "shop",
  viewpoint: "frontal",
  score: 0.4 - i * 0.01,
  similarity: 0.3 - i * 0.01,
  attribute_match: 1,
  ...over,
});

export const searchResponse = (n: number, over: Partial<SearchResponse> = {}): SearchResponse => ({
  mode: "text",
  query: "red dress",
  total: n,
  results: Array.from({ length: n }, (_, i) => item(i)),
  applied_filters: {},
  detected: { categories: ["short_sleeve_dress"], colours: ["red"] },
  inferred: null,
  ranking: { alpha: 0.85, beta: 0.15, attribute_signal_used: true },
  candidates_considered: n * 4,
  latency_ms: 42,
  ...over,
});

export const filtersResponse: FiltersResponse = {
  fields: {
    category: { label: "Category", options: [{ value: "skirt", label: "Skirt", count: 10 }, { value: "trousers", label: "Trousers", count: 8 }] },
    colour: { label: "Colour", options: [{ value: "red", label: "Red", count: 5 }] },
    source: { label: "Photo type", options: [{ value: "shop", label: "Shop / product photo", count: 12 }] },
    viewpoint: { label: "Viewpoint", options: [{ value: "frontal", label: "Frontal", count: 12 }] },
  },
};
