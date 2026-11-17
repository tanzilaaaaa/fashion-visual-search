import type { RankingOptions } from "../api/types";

interface Props {
  value: RankingOptions;
  onChange: (r: RankingOptions) => void;
  disabled?: boolean;
}

/** Could Have: adjustable top-K and ranking weights (final = α·similarity + β·attribute match). */
export function RankingControls({ value, onChange, disabled }: Props) {
  return (
    <fieldset disabled={disabled} className="space-y-4">
      <legend className="text-sm font-semibold uppercase tracking-wide text-ink-soft">Ranking</legend>
      <div>
        <label htmlFor="topk" className="mb-1 block text-sm font-medium">Results</label>
        <select
          id="topk"
          value={value.topK}
          onChange={(e) => onChange({ ...value, topK: Number(e.target.value) })}
          className="w-full rounded-lg border border-stone-300 bg-white px-3 py-2 text-sm focus:border-ink focus:outline-none"
        >
          {[12, 24, 48, 96].map((n) => (
            <option key={n} value={n}>Top {n}</option>
          ))}
        </select>
      </div>
      <div>
        <div className="mb-1 flex items-baseline justify-between">
          <label htmlFor="beta" className="text-sm font-medium">Attribute boost</label>
          <span className="text-xs tabular-nums text-ink-muted">
            α {value.alpha.toFixed(2)} · β {value.beta.toFixed(2)}
          </span>
        </div>
        <input
          id="beta"
          type="range"
          min={0}
          max={0.5}
          step={0.05}
          value={value.beta}
          onChange={(e) => {
            const beta = Number(e.target.value);
            onChange({ ...value, beta, alpha: Number((1 - beta).toFixed(2)) });
          }}
          className="w-full accent-accent"
          aria-describedby="beta-help"
        />
        <p id="beta-help" className="mt-1 text-xs leading-relaxed text-ink-muted">
          How much an exact category/colour match lifts an item above purely visual similarity.
        </p>
      </div>
    </fieldset>
  );
}
