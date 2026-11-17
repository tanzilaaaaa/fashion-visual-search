import { useEffect, useId, useRef, useState } from "react";
import { useTheme } from "../context/ThemeContext";
import { THEMES, type ThemeMeta } from "../theme/themes";
import { CheckIcon, PaletteIcon } from "./Icons";

function Swatch({ t, size = 28 }: { t: ThemeMeta; size?: number }) {
  const [canvas, surface, accent, accent2] = t.swatch;
  return (
    <span
      aria-hidden="true"
      className="relative inline-block shrink-0 overflow-hidden rounded-full border border-line"
      style={{ width: size, height: size, background: canvas }}
    >
      <span className="absolute inset-[18%] rounded-full" style={{ background: surface }} />
      <span className="absolute bottom-[18%] right-[18%] h-[38%] w-[38%] rounded-full" style={{ background: `linear-gradient(135deg, ${accent}, ${accent2})` }} />
    </span>
  );
}

/** Theme picker: a menu button with four previews. Esc / outside click closes; arrow keys move. */
export function ThemeSwitcher({ compact = false }: { compact?: boolean }) {
  const { theme, meta, setTheme } = useTheme();
  const [open, setOpen] = useState(false);
  const root = useRef<HTMLDivElement>(null);
  const items = useRef<(HTMLButtonElement | null)[]>([]);
  const menuId = useId();

  useEffect(() => {
    if (!open) return;
    const onDoc = (e: MouseEvent) => !root.current?.contains(e.target as Node) && setOpen(false);
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    document.addEventListener("mousedown", onDoc);
    document.addEventListener("keydown", onKey);
    items.current[THEMES.findIndex((t) => t.id === theme)]?.focus();
    return () => {
      document.removeEventListener("mousedown", onDoc);
      document.removeEventListener("keydown", onKey);
    };
  }, [open, theme]);

  const onMenuKey = (e: React.KeyboardEvent) => {
    const i = items.current.findIndex((el) => el === document.activeElement);
    if (e.key === "ArrowDown" || e.key === "ArrowUp") {
      e.preventDefault();
      const next = (i + (e.key === "ArrowDown" ? 1 : -1) + THEMES.length) % THEMES.length;
      items.current[next]?.focus();
    }
  };

  return (
    <div ref={root} className="relative">
      <button
        type="button"
        aria-haspopup="menu"
        aria-expanded={open}
        aria-controls={menuId}
        aria-label={`Theme: ${meta.name}. Change theme`}
        onClick={() => setOpen((v) => !v)}
        className="inline-flex items-center gap-2 rounded-full border border-line bg-surface/70 p-1 pr-3 text-sm font-medium text-ink-soft transition hover:text-ink focus-visible:outline focus-visible:outline-2 focus-visible:outline-accent"
      >
        <Swatch t={meta} size={26} />
        {!compact && <span className="hidden sm:inline">{meta.name}</span>}
        <PaletteIcon width={15} height={15} className="text-ink-muted" />
      </button>
      {open && (
        <div
          id={menuId}
          role="menu"
          aria-label="Choose a theme"
          onKeyDown={onMenuKey}
          className="glass absolute right-0 z-50 mt-2 w-64 rounded-2xl p-1.5 shadow-lift animate-fade-up"
          style={{ animationDuration: "0.2s" }}
        >
          {THEMES.map((t, i) => (
            <button
              key={t.id}
              ref={(el) => (items.current[i] = el)}
              role="menuitemradio"
              aria-checked={t.id === theme}
              type="button"
              onClick={() => {
                setTheme(t.id);
                setOpen(false);
              }}
              className={`flex w-full items-center gap-3 rounded-xl px-2.5 py-2 text-left transition hover:bg-surface-2 focus:bg-surface-2 focus:outline-none ${
                t.id === theme ? "bg-surface-2" : ""
              }`}
            >
              <Swatch t={t} />
              <span className="min-w-0 flex-1">
                <span className="block text-sm font-semibold text-ink">{t.name}</span>
                <span className="block text-xs text-ink-muted">{t.tagline}</span>
              </span>
              {t.id === theme && <CheckIcon width={16} height={16} className="text-accent" />}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
