import type { FilterKey, Filters, FiltersResponse } from "../api/types";
import { COLOUR_SWATCH } from "../lib/format";

interface Props {
  vocab: FiltersResponse | null;
  value: Filters;
  onChange: (f: Filters) => void;
  disabled?: boolean;
}

const ORDER: FilterKey[] = ["category", "colour", "source", "viewpoint"];

export function FilterPanel({ vocab, value, onChange, disabled }: Props) {
  const active = Object.values(value).reduce((n, v) => n + (v?.length ?? 0), 0);

  const toggle = (field: FilterKey, v: string) => {
    const current = new Set(value[field] ?? []);
    current.has(v) ? current.delete(v) : current.add(v);
    const next: Filters = { ...value, [field]: [...current] };
    if (!next[field]!.length) delete next[field];
    onChange(next);
  };

  if (!vocab) {
    return (
      <div className="space-y-3" aria-hidden="true">
        {Array.from({ length: 6 }).map((_, i) => (
          <div key={i} className="h-5 animate-pulse rounded bg-stone-200" />
        ))}
      </div>
    );
  }

  return (
    <fieldset disabled={disabled} className="space-y-6">
      <div className="flex items-center justify-between">
        <legend className="text-sm font-semibold uppercase tracking-wide text-ink-soft">Filters</legend>
        {active > 0 && (
          <button type="button" onClick={() => onChange({})} className="text-xs font-medium text-accent hover:underline">
            Clear all ({active})
          </button>
        )}
      </div>
      {ORDER.map((field) => {
        const spec = vocab.fields[field];
        if (!spec || spec.options.length === 0) return null;
        return (
          <div key={field}>
            <h3 className="mb-2 text-sm font-medium text-ink">{spec.label}</h3>
            {field === "colour" ? (
              <div className="flex flex-wrap gap-2">
                {spec.options.map((o) => {
                  const on = value.colour?.includes(o.value) ?? false;
                  return (
                    <button
                      key={o.value}
                      type="button"
                      onClick={() => toggle("colour", o.value)}
                      aria-pressed={on}
                      title={`${o.label} (${o.count})`}
                      className={`flex items-center gap-1.5 rounded-full border px-2 py-1 text-xs transition focus-visible:outline focus-visible:outline-2 focus-visible:outline-accent ${
                        on ? "border-ink bg-ink text-white" : "border-stone-300 bg-white text-ink-soft hover:border-ink"
                      }`}
                    >
                      <span className="h-3 w-3 rounded-full border border-stone-300" style={{ background: COLOUR_SWATCH[o.value] ?? "#ccc" }} />
                      {o.label}
                    </button>
                  );
                })}
              </div>
            ) : (
              <ul className="space-y-1.5">
                {spec.options.map((o) => {
                  const id = `f-${field}-${o.value}`;
                  return (
                    <li key={o.value} className="flex items-center gap-2 text-sm">
                      <input
                        id={id}
                        type="checkbox"
                        checked={value[field]?.includes(o.value) ?? false}
                        onChange={() => toggle(field, o.value)}
                        className="h-4 w-4 rounded border-stone-400 accent-ink"
                      />
                      <label htmlFor={id} className="flex flex-1 cursor-pointer justify-between text-ink-soft">
                        <span>{o.label}</span>
                        <span className="tabular-nums text-ink-muted">{o.count.toLocaleString()}</span>
                      </label>
                    </li>
                  );
                })}
              </ul>
            )}
          </div>
        );
      })}
    </fieldset>
  );
}
