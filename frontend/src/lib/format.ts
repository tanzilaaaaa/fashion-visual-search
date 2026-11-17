import type { ItemSummary } from "../api/types";

export const capitalise = (s: string) => (s ? s.charAt(0).toUpperCase() + s.slice(1) : s);

export const humanise = (key: string) => capitalise(key.replace(/_/g, " "));

export const percent = (x: number, digits = 0) => `${(x * 100).toFixed(digits)}%`;

/** Similarity is cosine in [-1, 1]; CLIP scores for good matches sit around 0.25–0.35 for text. */
export const formatScore = (x: number) => x.toFixed(3);

export function altText(item: Pick<ItemSummary, "colour" | "category" | "source">) {
  const colour = item.colour && item.colour !== "multicolour" ? `${item.colour} ` : "";
  const kind = item.source === "shop" ? "product photo" : "street photo";
  return `${capitalise(colour + item.category)} — ${kind}`;
}

export const SOURCE_LABEL: Record<string, string> = { shop: "Shop", user: "Street" };

export const COLOUR_SWATCH: Record<string, string> = {
  black: "#1c1917", white: "#f5f5f4", grey: "#a8a29e", red: "#dc2626", pink: "#f472b6",
  orange: "#f97316", yellow: "#facc15", green: "#16a34a", blue: "#2563eb", navy: "#1e3a8a",
  purple: "#9333ea", brown: "#92400e", beige: "#d6c7a1",
  multicolour: "conic-gradient(#dc2626, #facc15, #16a34a, #2563eb, #9333ea, #dc2626)",
};

export function formatBytes(n: number) {
  if (n < 1024) return `${n} B`;
  if (n < 1024 ** 2) return `${(n / 1024).toFixed(1)} KB`;
  if (n < 1024 ** 3) return `${(n / 1024 ** 2).toFixed(1)} MB`;
  return `${(n / 1024 ** 3).toFixed(2)} GB`;
}
