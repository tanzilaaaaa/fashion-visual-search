import { useState } from "react";
import { percent } from "../lib/format";

/**
 * Two-series palette from the active theme (index.css --series-1/2). Each theme's
 * pair is validated against its own chart surface: lightness band, chroma floor,
 * colour-blind separation and >= 3:1 contrast.
 */
export const SERIES = { clip: "var(--series-1)", baseline: "var(--series-2)" } as const;

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
                    <div className="absolute inset-y-0 left-0 right-12 border-l border-line">
                      <div
                        className="h-full rounded-r"
                        style={{ width: `${Math.max(v * 100, 0.5)}%`, background: s.color, opacity: hover && hover !== id ? 0.55 : 1 }}
                      />
                    </div>
                    <span className="absolute right-0 w-11 text-right text-xs tabular-nums text-ink-soft">{percent(v)}</span>
                    {hover === id && (
                      <span role="tooltip" className="pointer-events-none absolute -top-8 left-1/3 z-10 whitespace-nowrap rounded-md bg-ink px-2 py-1 text-xs text-canvas shadow">
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
          <span className="h-3 border-l border-line">
            <span className="block h-full rounded-r" style={{ width: `${(d.value / max) * 100}%`, background: SERIES.clip }} />
          </span>
          <span className="text-right text-xs tabular-nums text-ink-muted">{d.value.toLocaleString()}</span>
        </li>
      ))}
    </ul>
  );
}

/**
 * Single-series line over epochs with a hover crosshair + tooltip. One series per
 * chart (small multiples), so two measures with different scales never share an axis.
 */
export function LineChart({
  points, format, label, highlight,
}: {
  points: { x: number; y: number }[];
  format: (v: number) => string;
  label: string;
  highlight?: number;
}) {
  const [hover, setHover] = useState<number | null>(null);
  if (points.length < 2) return <p className="text-sm text-ink-muted">Not enough points to plot.</p>;
  const W = 320, H = 150, pad = { l: 40, r: 10, t: 10, b: 24 };
  const xs = points.map((p) => p.x), ys = points.map((p) => p.y);
  const x0 = Math.min(...xs), x1 = Math.max(...xs);
  let y0 = Math.min(...ys), y1 = Math.max(...ys);
  if (y1 - y0 < 1e-9) { y0 -= 0.5; y1 += 0.5; }
  const sx = (x: number) => pad.l + ((x - x0) / (x1 - x0)) * (W - pad.l - pad.r);
  const sy = (y: number) => pad.t + (1 - (y - y0) / (y1 - y0)) * (H - pad.t - pad.b);
  const d = points.map((p, i) => `${i ? "L" : "M"}${sx(p.x).toFixed(1)},${sy(p.y).toFixed(1)}`).join(" ");
  const ticks = [y0, (y0 + y1) / 2, y1];
  const hp = hover !== null ? points[hover] : null;

  const onMove = (e: React.MouseEvent<SVGRectElement>) => {
    const r = e.currentTarget.getBoundingClientRect();
    const fx = ((e.clientX - r.left) / r.width) * (W - pad.l - pad.r) + pad.l;
    let best = 0;
    points.forEach((p, i) => { if (Math.abs(sx(p.x) - fx) < Math.abs(sx(points[best]!.x) - fx)) best = i; });
    setHover(best);
  };

  return (
    <figure className="relative">
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full overflow-visible" role="img" aria-label={`${label} by epoch`}>
        {ticks.map((t) => (
          <g key={t}>
            <line x1={pad.l} x2={W - pad.r} y1={sy(t)} y2={sy(t)} stroke="rgb(var(--line))" strokeWidth={1} />
            <text x={pad.l - 6} y={sy(t) + 3} textAnchor="end" fontSize="9" fill="rgb(var(--ink-muted))">{format(t)}</text>
          </g>
        ))}
        <text x={pad.l} y={H - 6} fontSize="9" fill="rgb(var(--ink-muted))">epoch {x0}</text>
        <text x={W - pad.r} y={H - 6} fontSize="9" textAnchor="end" fill="rgb(var(--ink-muted))">epoch {x1}</text>
        <path d={d} fill="none" stroke={SERIES.clip} strokeWidth={2} strokeLinejoin="round" strokeLinecap="round" />
        {highlight !== undefined && points.find((p) => p.x === highlight) && (
          <circle cx={sx(highlight)} cy={sy(points.find((p) => p.x === highlight)!.y)} r={4.5} fill={SERIES.clip} stroke="rgb(var(--surface))" strokeWidth={2} />
        )}
        {hp && (
          <g>
            <line x1={sx(hp.x)} x2={sx(hp.x)} y1={pad.t} y2={H - pad.b} stroke="rgb(var(--ink-muted))" strokeDasharray="3 3" />
            <circle cx={sx(hp.x)} cy={sy(hp.y)} r={4} fill={SERIES.clip} stroke="rgb(var(--surface))" strokeWidth={2} />
          </g>
        )}
        <rect x={pad.l} y={pad.t} width={W - pad.l - pad.r} height={H - pad.t - pad.b} fill="transparent" onMouseMove={onMove} onMouseLeave={() => setHover(null)} />
      </svg>
      {hp && (
        <span role="tooltip" className="pointer-events-none absolute right-0 top-0 rounded-md bg-ink px-2 py-1 text-xs text-canvas shadow">
          Epoch {hp.x}: <strong className="tabular-nums">{format(hp.y)}</strong>
        </span>
      )}
    </figure>
  );
}
