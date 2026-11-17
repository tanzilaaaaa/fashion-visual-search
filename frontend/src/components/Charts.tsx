import { useState } from "react";
import { percent } from "../lib/format";

/** Two-series palette, validated (lightness, chroma, CVD ΔE 24, contrast ≥ 3:1 on white). */
export const SERIES = { clip: "#9f1239", baseline: "#2a78d6" } as const;

export interface GroupedRow {
  label: string;
  clip: number;
  baseline: number;
}

export function Legend({ items }: { items: { label: string; color: string }[] }) {
  return (
    <ul className="flex flex-wrap gap-4 text-xs text-ink-soft" aria-label="Legend">
      {items.map((i) => (
        <li key={i.label} className="inline-flex items-center gap-1.5">
          <span className="h-2.5 w-2.5 rounded-sm" style={{ background: i.color }} aria-hidden="true" />
          {i.label}
        </li>
      ))}
    </ul>
  );
}

/**
 * Horizontal grouped bars on a shared 0–100% axis. Each bar is direct-labelled,
 * so identity never relies on colour alone, and hovering shows an exact tooltip.
 */
export function GroupedBars({ rows, clipLabel, baselineLabel }: { rows: GroupedRow[]; clipLabel: string; baselineLabel: string }) {
  const [hover, setHover] = useState<string | null>(null);
  const series = [
    { key: "clip" as const, label: clipLabel, color: SERIES.clip },
    { key: "baseline" as const, label: baselineLabel, color: SERIES.baseline },
  ];
  return (
    <figure>
      <Legend items={series.map((s) => ({ label: s.label, color: s.color }))} />
      <div className="mt-4 space-y-4">
        {rows.map((row) => (
          <div key={row.label} className="grid grid-cols-[5.5rem_1fr] items-center gap-3">
            <span className="text-sm font-medium text-ink-soft">{row.label}</span>
            <div className="space-y-[2px]">
              {series.map((s) => {
                const v = row[s.key];
                const id = `${row.label}-${s.key}`;
                return (
                  <div
                    key={s.key}
                    className="relative flex h-5 items-center"
                    onMouseEnter={() => setHover(id)}
                    onMouseLeave={() => setHover(null)}
                    onFocus={() => setHover(id)}
                    onBlur={() => setHover(null)}
                    tabIndex={0}
                    aria-label={`${row.label}, ${s.label}: ${percent(v, 1)}`}
                  >
                    <div className="absolute inset-y-0 left-0 right-12 border-l border-stone-300">
                      <div
                        className="h-full rounded-r"
                        style={{ width: `${Math.max(v * 100, 0.5)}%`, background: s.color, opacity: hover && hover !== id ? 0.55 : 1 }}
                      />
                    </div>
                    <span className="absolute right-0 w-11 text-right text-xs tabular-nums text-ink-soft">{percent(v)}</span>
                    {hover === id && (
                      <span role="tooltip" className="pointer-events-none absolute -top-8 left-1/3 z-10 whitespace-nowrap rounded-md bg-ink px-2 py-1 text-xs text-white shadow">
                        {s.label} · {row.label}: <strong className="tabular-nums">{percent(v, 1)}</strong>
                      </span>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        ))}
      </div>
    </figure>
  );
}

/** Single-series magnitude bars (one hue; the title names the series, so no legend). */
export function DistributionBars({ data }: { data: { label: string; value: number }[] }) {
  const max = Math.max(1, ...data.map((d) => d.value));
  return (
    <ul className="space-y-1.5">
      {data.map((d) => (
        <li key={d.label} className="grid grid-cols-[9rem_1fr_3.5rem] items-center gap-3 text-sm" title={`${d.label}: ${d.value.toLocaleString()}`}>
          <span className="truncate text-ink-soft">{d.label}</span>
          <span className="h-3 border-l border-stone-300">
            <span className="block h-full rounded-r" style={{ width: `${(d.value / max) * 100}%`, background: SERIES.clip }} />
          </span>
          <span className="text-right text-xs tabular-nums text-ink-muted">{d.value.toLocaleString()}</span>
        </li>
      ))}
    </ul>
  );
}
