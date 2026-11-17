export type ThemeId = "atelier" | "midnight" | "blush" | "noir";

export interface ThemeMeta {
  id: ThemeId;
  name: string;
  tagline: string;
  dark: boolean;
  /** canvas, surface, accent, accent-2 — used for the switcher preview swatch. */
  swatch: [string, string, string, string];
}

export const THEMES: ThemeMeta[] = [
  { id: "atelier", name: "Atelier", tagline: "Cream, ink & burgundy", dark: false, swatch: ["#faf7f2", "#ffffff", "#9f1239", "#c2410c"] },
  { id: "midnight", name: "Midnight", tagline: "Glass & violet glow", dark: true, swatch: ["#090912", "#14141f", "#a78bfa", "#f472b6"] },
  { id: "blush", name: "Blush", tagline: "Soft rose & peach", dark: false, swatch: ["#fff6f8", "#ffffff", "#db2777", "#fb923c"] },
  { id: "noir", name: "Noir", tagline: "Black & gold", dark: true, swatch: ["#080808", "#131313", "#d4af37", "#f5e6b3"] },
];

export const THEME_STORAGE_KEY = "lookbook.theme";

export const isThemeId = (v: unknown): v is ThemeId => THEMES.some((t) => t.id === v);

export function defaultTheme(): ThemeId {
  try {
    return window.matchMedia?.("(prefers-color-scheme: dark)").matches ? "midnight" : "atelier";
  } catch {
    return "atelier";
  }
}
