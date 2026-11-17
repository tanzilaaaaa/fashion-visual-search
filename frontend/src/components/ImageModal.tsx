import { useEffect, useRef } from "react";
import { Link } from "react-router-dom";
import type { ScoredItem } from "../api/types";
import { imageSrc } from "../api/client";
import { altText, capitalise, formatScore } from "../lib/format";
import { XIcon } from "./Icons";

/** Could Have: full-size image modal. Closes on Esc, backdrop click or the close button. */
export function ImageModal({ item, onClose }: { item: ScoredItem | null; onClose: () => void }) {
  const closeRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!item) return;
    const prev = document.activeElement as HTMLElement | null;
    closeRef.current?.focus();
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    document.body.style.overflow = "hidden";
    return () => {
      window.removeEventListener("keydown", onKey);
      document.body.style.overflow = "";
      prev?.focus();
    };
  }, [item, onClose]);

  if (!item) return null;
  return (
    <div className="fixed inset-0 z-50 grid place-items-center bg-ink/70 p-4" onClick={onClose} role="presentation">
      <div
        role="dialog"
        aria-modal="true"
        aria-label={altText(item)}
        onClick={(e) => e.stopPropagation()}
        className="relative w-full max-w-lg overflow-hidden rounded-2xl bg-white shadow-2xl"
      >
        <button ref={closeRef} onClick={onClose} className="absolute right-3 top-3 rounded-full bg-white/90 p-2 shadow hover:bg-stone-100" aria-label="Close">
          <XIcon />
        </button>
        <img src={imageSrc(item.image_url)} alt={altText(item)} className="max-h-[70vh] w-full bg-stone-100 object-contain" />
        <div className="flex items-center justify-between gap-4 p-4">
          <div>
            <p className="font-semibold">{capitalise(item.category)}</p>
            <p className="text-sm text-ink-muted">
              {capitalise(item.colour)} · score {formatScore(item.score)} · similarity {formatScore(item.similarity)}
            </p>
          </div>
          <Link to={`/item/${item.item_id}`} className="rounded-lg bg-ink px-3 py-2 text-sm font-semibold text-white hover:bg-black">
            View details
          </Link>
        </div>
      </div>
    </div>
  );
}
