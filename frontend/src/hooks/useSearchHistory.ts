import { useCallback, useState } from "react";

const KEY = "fvs.searchHistory.v1";
const MAX = 8;

function read(): string[] {
  try {
    const raw = localStorage.getItem(KEY);
    const parsed = raw ? JSON.parse(raw) : [];
    return Array.isArray(parsed) ? parsed.filter((x) => typeof x === "string").slice(0, MAX) : [];
  } catch {
    return [];
  }
}

function write(list: string[]) {
  try {
    localStorage.setItem(KEY, JSON.stringify(list));
  } catch {
    /* storage may be unavailable (private mode); history is a convenience only */
  }
}

/** Recent text queries, per browser (Could Have: search history). */
export function useSearchHistory() {
  const [history, setHistory] = useState<string[]>(read);

  const add = useCallback((q: string) => {
    setHistory((prev) => {
      const next = [q, ...prev.filter((p) => p.toLowerCase() !== q.toLowerCase())].slice(0, MAX);
      write(next);
      return next;
    });
  }, []);

  const clear = useCallback(() => {
    write([]);
    setHistory([]);
  }, []);

  return { history, add, clear };
}
