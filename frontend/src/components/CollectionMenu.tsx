import { useEffect, useRef, useState, type FormEvent } from "react";
import { me, toApiError } from "../api/client";
import type { CollectionSummary } from "../api/types";
import { useAccount } from "../context/AccountContext";
import { CheckIcon, FolderIcon, PlusIcon } from "./Icons";

/** "Add to collection": pick a board or create one. Adding also saves the item. */
export function CollectionMenu({ itemId }: { itemId: string }) {
  const { enabled, notify, setFavoriteIds } = useAccount();
  const [open, setOpen] = useState(false);
  const [cols, setCols] = useState<CollectionSummary[] | null>(null);
  const [inCols, setInCols] = useState<Set<number>>(new Set());
  const [name, setName] = useState("");
  const root = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    me.collections()
      .then(async (r) => {
        setCols(r.collections);
        const details = await Promise.all(r.collections.map((c) => me.collection(c.id)));
        setInCols(new Set(details.filter((d) => d.items.some((i) => i.item_id === itemId)).map((d) => d.id)));
      })
      .catch((e) => notify(toApiError(e).message));
    const onDoc = (e: MouseEvent) => !root.current?.contains(e.target as Node) && setOpen(false);
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    document.addEventListener("mousedown", onDoc);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDoc);
      document.removeEventListener("keydown", onKey);
    };
  }, [open, itemId, notify]);

  if (!enabled) return null;

  const refreshFavorites = () => me.favoriteIds().then((r) => setFavoriteIds(r.ids)).catch(() => undefined);

  const toggle = async (c: CollectionSummary) => {
    try {
      if (inCols.has(c.id)) {
        await me.removeFromCollection(c.id, itemId);
        setInCols((s) => new Set([...s].filter((x) => x !== c.id)));
        notify(`Removed from “${c.name}”`);
      } else {
        await me.addToCollection(c.id, itemId);
        setInCols((s) => new Set(s).add(c.id));
        notify(`Added to “${c.name}”`);
        void refreshFavorites();
      }
    } catch (e) {
      notify(toApiError(e).message);
    }
  };

  const create = async (e: FormEvent) => {
    e.preventDefault();
    if (!name.trim()) return;
    try {
      const c = await me.createCollection(name.trim());
      await me.addToCollection(c.id, itemId);
      setCols((prev) => [{ ...c, count: 1 }, ...(prev ?? [])]);
      setInCols((s) => new Set(s).add(c.id));
      setName("");
      notify(`Added to “${c.name}”`);
      void refreshFavorites();
    } catch (err) {
      notify(toApiError(err).message);
    }
  };

  return (
    <div ref={root} className="relative">
      <button type="button" className="btn-ghost" aria-haspopup="menu" aria-expanded={open} onClick={() => setOpen((v) => !v)}>
        <FolderIcon width={16} height={16} /> Add to collection
      </button>
      {open && (
        <div role="menu" aria-label="Collections" className="glass absolute left-0 z-40 mt-2 w-72 rounded-2xl p-2 shadow-lift animate-fade-up" style={{ animationDuration: "0.2s" }}>
          {cols === null ? (
            <p className="px-3 py-2 text-sm text-ink-muted">Loading…</p>
          ) : cols.length === 0 ? (
            <p className="px-3 py-2 text-sm text-ink-muted">No collections yet. Create your first one below.</p>
          ) : (
            <ul className="max-h-56 overflow-y-auto">
              {cols.map((c) => (
                <li key={c.id}>
                  <button
                    role="menuitemcheckbox"
                    aria-checked={inCols.has(c.id)}
                    type="button"
                    onClick={() => void toggle(c)}
                    className="flex w-full items-center justify-between gap-2 rounded-xl px-3 py-2 text-left text-sm text-ink hover:bg-surface-2 focus:bg-surface-2 focus:outline-none"
                  >
                    <span className="truncate">{c.name}</span>
                    {inCols.has(c.id) && <CheckIcon width={16} height={16} className="text-accent" />}
                  </button>
                </li>
              ))}
            </ul>
          )}
          <form onSubmit={create} className="mt-1 flex gap-2 border-t border-line px-1 pt-2">
            <label htmlFor={`newcol-${itemId}`} className="sr-only">New collection name</label>
            <input
              id={`newcol-${itemId}`}
              value={name}
              onChange={(e) => setName(e.target.value)}
              maxLength={40}
              placeholder="New collection"
              className="input py-2 text-sm"
            />
            <button type="submit" className="btn-primary px-3" aria-label="Create collection and add">
              <PlusIcon width={16} height={16} />
            </button>
          </form>
        </div>
      )}
    </div>
  );
}
