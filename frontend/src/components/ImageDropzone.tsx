import { useRef, useState, type DragEvent } from "react";
import { UploadIcon } from "./Icons";

export const ACCEPTED_TYPES = ["image/jpeg", "image/png", "image/webp"];
export const MAX_UPLOAD_MB = 8;

/** Client-side check mirroring the API's rules, so most mistakes are caught instantly. */
export function validateImage(file: File): string | null {
  if (!ACCEPTED_TYPES.includes(file.type)) return "Unsupported file type. Please choose a JPEG, PNG or WebP image.";
  if (file.size > MAX_UPLOAD_MB * 1024 * 1024) return `That image is larger than ${MAX_UPLOAD_MB} MB.`;
  return null;
}

interface Props {
  busy?: boolean;
  previewUrl?: string | null;
  onFile: (f: File) => void;
}

export function ImageDropzone({ busy, previewUrl, onFile }: Props) {
  const input = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handle = (file?: File | null) => {
    if (!file) return;
    const problem = validateImage(file);
    setError(problem);
    if (!problem) onFile(file);
  };

  const onDrop = (e: DragEvent) => {
    e.preventDefault();
    setDragging(false);
    handle(e.dataTransfer.files?.[0]);
  };

  return (
    <div>
      <div
        onDragOver={(e) => {
          e.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
        className={`flex h-full min-h-[8.5rem] items-center gap-4 rounded-2xl border-2 border-dashed p-4 transition ${
          dragging ? "border-accent bg-accent-soft/60" : "border-stone-300 bg-white"
        }`}
      >
        {previewUrl ? (
          <img src={previewUrl} alt="Your uploaded reference" className="h-24 w-20 shrink-0 rounded-lg object-cover shadow-card" />
        ) : (
          <span className="grid h-12 w-12 shrink-0 place-items-center rounded-full bg-stone-100 text-ink-soft">
            <UploadIcon />
          </span>
        )}
        <div className="min-w-0 text-sm">
          <p className="font-medium text-ink">Search with a photo</p>
          <p className="text-ink-muted">Drop an image here, or</p>
          <button
            type="button"
            disabled={busy}
            onClick={() => input.current?.click()}
            className="mt-1 font-semibold text-accent underline-offset-4 hover:underline disabled:opacity-60 focus-visible:outline focus-visible:outline-2 focus-visible:outline-accent"
          >
            {previewUrl ? "choose another" : "browse files"}
          </button>
          <p className="mt-1 text-xs text-ink-muted">JPEG, PNG or WebP · up to {MAX_UPLOAD_MB} MB</p>
        </div>
        <input
          ref={input}
          type="file"
          accept={ACCEPTED_TYPES.join(",")}
          className="sr-only"
          aria-label="Upload a fashion image"
          data-testid="file-input"
          onChange={(e) => {
            handle(e.target.files?.[0]);
            e.target.value = "";
          }}
        />
      </div>
      {error && (
        <p role="alert" className="mt-2 text-sm text-accent">
          {error}
        </p>
      )}
    </div>
  );
}
