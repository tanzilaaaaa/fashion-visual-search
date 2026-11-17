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
        <SearchIcon className="pointer-events-none absolute left-5 top-1/2 -translate-y-1/2 text-ink-muted" />
        <input
          id="q"
          value={value}
          onChange={(e) => {
            setValue(e.target.value);
            if (error) setError(null);
          }}
          maxLength={200}
          placeholder="Describe it in your own words: “a red casual summer dress”"
          aria-invalid={!!error}
          aria-describedby={error ? "q-error" : undefined}
          className="h-16 w-full rounded-2xl border border-line bg-surface pl-14 pr-36 text-base text-ink shadow-card transition placeholder:text-ink-muted/70 focus:border-accent focus:outline-none focus:ring-4 focus:ring-accent/15 sm:text-lg"
        />
        {value && (
          <button
            type="button"
            onClick={() => setValue("")}
            className="absolute right-[7.75rem] top-1/2 -translate-y-1/2 rounded-full p-1.5 text-ink-muted hover:bg-surface-2 hover:text-ink"
            aria-label="Clear query"
          >
            <XIcon width={16} height={16} />
          </button>
        )}
        <button type="submit" disabled={busy} className="btn-primary absolute right-2.5 top-1/2 h-11 -translate-y-1/2 px-6">
          {busy ? "Searching…" : "Search"}
        </button>
      </form>
      {error && (
        <p id="q-error" role="alert" className="mt-2 text-sm text-danger">
          {error}
        </p>
      )}
      <div className="mt-4 flex flex-wrap items-center gap-2 text-sm">
        <span className="text-ink-muted">{history.length ? "Recent:" : "Try:"}</span>
        {(history.length ? history : EXAMPLES).map((ex) => (
          <button key={ex} type="button" onClick={() => submit(ex)} className="chip">
            {ex}
          </button>
        ))}
        {history.length > 0 && (
          <button type="button" onClick={onClearHistory} className="text-xs text-ink-muted underline-offset-2 hover:text-ink hover:underline">
            Clear history
          </button>
        )}
      </div>
    </div>
  );
}
