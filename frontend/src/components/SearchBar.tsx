import { useState, type FormEvent } from "react";
import { SearchIcon, XIcon } from "./Icons";

const EXAMPLES = ["black oversized hoodie", "white summer dress", "red casual summer dress", "blue denim jacket", "pleated mini skirt"];

interface Props {
  initial?: string;
  busy?: boolean;
  history: string[];
  onSearch: (q: string) => void;
  onClearHistory: () => void;
}

export function SearchBar({ initial = "", busy, history, onSearch, onClearHistory }: Props) {
  const [value, setValue] = useState(initial);
  const [error, setError] = useState<string | null>(null);

  const submit = (q: string) => {
    const trimmed = q.trim();
    if (!trimmed) {
      setError("Describe what you're looking for, e.g. “black oversized hoodie”.");
      return;
    }
    setError(null);
    setValue(trimmed);
    onSearch(trimmed);
  };

  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    submit(value);
  };

  return (
    <div>
      <form onSubmit={onSubmit} role="search" className="relative">
        <label htmlFor="q" className="sr-only">Describe a fashion item</label>
        <SearchIcon className="pointer-events-none absolute left-4 top-1/2 -translate-y-1/2 text-ink-muted" />
        <input
          id="q"
          value={value}
          onChange={(e) => {
            setValue(e.target.value);
            if (error) setError(null);
          }}
          maxLength={200}
          placeholder="Describe it in your own words — “a red casual summer dress”"
          aria-invalid={!!error}
          aria-describedby={error ? "q-error" : undefined}
          className="h-14 w-full rounded-2xl border border-stone-300 bg-white pl-12 pr-36 text-base shadow-card placeholder:text-stone-400 focus:border-ink focus:outline-none focus:ring-2 focus:ring-ink/10"
        />
        {value && (
          <button
            type="button"
            onClick={() => setValue("")}
            className="absolute right-[7.5rem] top-1/2 -translate-y-1/2 rounded-full p-1.5 text-ink-muted hover:bg-stone-100"
            aria-label="Clear query"
          >
            <XIcon width={16} height={16} />
          </button>
        )}
        <button
          type="submit"
          disabled={busy}
          className="absolute right-2 top-1/2 h-10 -translate-y-1/2 rounded-xl bg-ink px-5 text-sm font-semibold text-white transition hover:bg-black disabled:cursor-wait disabled:opacity-70 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
        >
          {busy ? "Searching…" : "Search"}
        </button>
      </form>
      {error && (
        <p id="q-error" role="alert" className="mt-2 text-sm text-accent">
          {error}
        </p>
      )}
      <div className="mt-3 flex flex-wrap items-center gap-2 text-sm">
        <span className="text-ink-muted">{history.length ? "Recent:" : "Try:"}</span>
        {(history.length ? history : EXAMPLES).map((ex) => (
          <button
            key={ex}
            type="button"
            onClick={() => submit(ex)}
            className="rounded-full border border-stone-300 bg-white px-3 py-1 text-ink-soft transition hover:border-ink hover:text-ink focus-visible:outline focus-visible:outline-2 focus-visible:outline-accent"
          >
            {ex}
          </button>
        ))}
        {history.length > 0 && (
          <button type="button" onClick={onClearHistory} className="text-xs text-ink-muted underline-offset-2 hover:underline">
            Clear history
          </button>
        )}
      </div>
    </div>
  );
}
