export type FilterKey = "category" | "colour" | "source" | "viewpoint";
export type Filters = Partial<Record<FilterKey, string[]>>;

export interface ItemSummary {
  item_id: string;
  image_url: string;
  category: string;
  category_key: string;
  colour: string;
  source: string;
  viewpoint: string;
}

export interface ScoredItem extends ItemSummary {
  score: number;
  similarity: number;
  attribute_match: number;
  reason?: string | null;
}

export interface ItemDetail extends ItemSummary {
  occlusion: string;
  scale: string;
  zoom_in: string;
  colour_confidence: number;
  pair_id: number;
  style: number;
  worn_with: string[];
}

export interface InferredAttr {
  value: string;
  label: string;
  confidence: number;
}

export interface SearchResponse {
  mode: "text" | "image";
  query?: string | null;
  total: number;
  results: ScoredItem[];
  applied_filters: Filters;
  detected: { categories: string[]; colours: string[] };
  inferred?: { category?: InferredAttr; colour?: InferredAttr } | null;
  ranking: { alpha: number; beta: number; attribute_signal_used: boolean };
  candidates_considered: number;
  latency_ms: number;
}

export interface SimilarResponse {
  source: ItemSummary;
  total: number;
  results: ScoredItem[];
}

export interface RecommendationsResponse {
  source: ItemSummary;
  groups: { group: string; label: string; items: ScoredItem[] }[];
}

export interface FilterOption {
  value: string;
  label: string;
  count: number;
}

export interface FiltersResponse {
  fields: Record<FilterKey, { label: string; options: FilterOption[] }>;
}

export interface HealthResponse {
  status: "ok" | "degraded";
  model_loaded: boolean;
  index_loaded: boolean;
  item_count: number;
  model?: string | null;
}

export interface User {
  id: number;
  name: string;
  email: string;
}

export interface SessionResponse {
  authenticated: boolean;
  auth_enabled: boolean;
  user?: User | null;
}

export interface ShowcaseResponse {
  items: ItemSummary[];
}

export interface RankingOptions {
  topK: number;
  alpha: number;
  beta: number;
}

type RecallBlock = Record<string, number>;
export interface EvaluationReport {
  evaluation: {
    dataset: string;
    model: string;
    catalogue_items: number;
    eval_items: number;
    consumer_to_shop: { queries: number; gallery: number; clip?: RecallBlock; category_baseline?: RecallBlock };
    text_to_image: {
      clip: RecallBlock;
      keyword_baseline: RecallBlock;
      per_query: { query: string; "clip_precision@10": number; "keyword_precision@10": number }[];
    };
    complete_the_look: { queries: number; "clip_hit@10": number | null; "random_hit@10": number | null; note: string };
    footprint: { index_bytes: number; metadata_bytes: number; images_bytes: number };
    build_seconds?: number;
    variants?: {
      pretrained: { consumer_to_shop: RecallBlock | null; text_to_image: RecallBlock };
      finetuned: { consumer_to_shop: RecallBlock | null; text_to_image: RecallBlock };
      served?: { consumer_to_shop: RecallBlock | null; text_to_image: RecallBlock; note?: string };
    };
    finetune?: FinetuneReport | { skipped: string };
  } | null;
  manifest: {
    item_count?: number;
    model_name?: string;
    built_at?: string;
    category_counts?: Record<string, number>;
    colour_counts?: Record<string, number>;
    source_counts?: Record<string, number>;
    adapter?: { file: string; ratio: number; hidden: number } | null;
  };
}

export interface FinetuneReport {
  method: string;
  loss: string;
  pairs: { items: number; train_items: number; val_items: number; train_groups: number; val_groups: number };
  device: string;
  best_epoch: number;
  history: { epoch: number; loss: number | null; "val_recall@10": number }[];
  ratio_search: { ratio: number; "recall@1"?: number | null; "recall@10": number | null; "text_precision@10": number }[];
  chosen_ratio: number;
  train_seconds: number;
}

// ------------------------------------------------------------------ profile (/me)
export interface Interests {
  categories: string[];
  colours: string[];
  styles: string[];
}

export interface ProfileResponse {
  user: User;
  profile: { bio: string; location: string; avatar_color: string };
  interests: Interests;
  stats: { favorites: number; collections: number; searches: number };
  member_since: number;
  avatar_colors: string[];
  style_presets: string[];
}

export interface FavoriteItem extends ItemSummary {
  saved_at: number;
}

export interface CollectionSummary {
  id: number;
  name: string;
  created_at: number;
  count: number;
  cover: ItemSummary[];
}

export interface CollectionDetail extends CollectionSummary {
  items: ItemSummary[];
}

export interface HistoryEntry {
  id: number;
  query: string;
  created_at: number;
}

export interface ForYouResponse {
  sections: { key: string; title: string; items: ScoredItem[] }[];
  has_favorites: boolean;
  has_interests: boolean;
}
