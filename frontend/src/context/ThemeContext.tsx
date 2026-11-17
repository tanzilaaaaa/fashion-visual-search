import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import { defaultTheme, isThemeId, THEME_STORAGE_KEY, THEMES, type ThemeId, type ThemeMeta } from "../theme/themes";

interface ThemeValue {
  theme: ThemeId;
  meta: ThemeMeta;
  setTheme: (t: ThemeId) => void;
}

const ThemeContext = createContext<ThemeValue | null>(null);

function initialTheme(): ThemeId {
  // index.html sets data-theme before React loads (no flash); prefer that.
  const fromDom = document.documentElement.dataset.theme;
  if (isThemeId(fromDom)) return fromDom;
  try {
    const saved = localStorage.getItem(THEME_STORAGE_KEY);
    if (isThemeId(saved)) return saved;
  } catch {
    /* storage unavailable (private mode) — fall back to system preference */
  }
  return defaultTheme();
}

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setThemeState] = useState<ThemeId>(initialTheme);

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    const meta = document.querySelector('meta[name="theme-color"]');
    meta?.setAttribute("content", THEMES.find((t) => t.id === theme)!.swatch[0]);
  }, [theme]);

  const setTheme = useCallback((t: ThemeId) => {
    setThemeState(t);
    try {
      localStorage.setItem(THEME_STORAGE_KEY, t);
    } catch {
      /* the choice still applies for this visit */
    }
  }, []);

  const meta = THEMES.find((t) => t.id === theme)!;
  return <ThemeContext.Provider value={{ theme, meta, setTheme }}>{children}</ThemeContext.Provider>;
}

export function useTheme() {
  const ctx = useContext(ThemeContext);
  if (!ctx) throw new Error("useTheme must be used inside <ThemeProvider>");
  return ctx;
}
