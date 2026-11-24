import { useCallback, useEffect, useState } from "react";
import { me } from "../api/client";
import { useAuth } from "../context/AuthContext";

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

const dedupe = (q: string, list: string[]) =>
  [q, ...list.filter((p) => p.toLowerCase() !== q.toLowerCase())].slice(0, MAX);

/**
 * Recent text queries. Signed in: synced to the account (the server records every
 * successful text search, so `add` only updates the screen right away). Accounts
 * switched off on the server: kept in this browser only.
 */
export function useSearchHistory() {
  const { user } = useAuth();
  const synced = !!user;
  const [history, setHistory] = useState<string[]>(() => (synced ? [] : read()));

  useEffect(() => {
    if (!synced) {
      setHistory(read());
      return;
    }
    let alive = true;
    me.history()
      .then((r) => alive && setHistory(r.entries.map((e) => e.query).slice(0, MAX)))
      .catch(() => undefined);
    return () => {
      alive = false;
    };
  }, [synced, user?.id]);

  const add = useCallback(
    (q: string) => {
      setHistory((prev) => {
        const next = dedupe(q, prev);
        if (!synced) write(next);
        return next;
      });
    },
    [synced],
  );

  const clear = useCallback(() => {
    setHistory([]);
    if (synced) void me.clearHistory().catch(() => undefined);
    else write([]);
  }, [synced]);

  return { history, add, clear };
}
