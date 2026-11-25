import { useRef, useState, type DragEvent } from "react";
import { CameraIcon } from "./Icons";

export const ACCEPTED_TYPES = ["image/jpeg", "image/png", "image/webp"];
export const MAX_UPLOAD_MB = 8;

/**
 * Shrink a photo in the browser before upload (longest side <= 1024 px, JPEG): CLIP only
 * needs 224 px, uploads get much faster on mobile data, and requests stay small through
 * the Vercel proxy. Falls back to the original file wherever canvas decoding isn't available.
 */
export async function downscaleImage(file: File, maxSide = 1024): Promise<File> {
  try {
    if (typeof createImageBitmap !== "function") return file;
    const bmp = await createImageBitmap(file);
    const scale = Math.min(1, maxSide / Math.max(bmp.width, bmp.height));
    if (scale === 1 && file.size < 1_500_000) return file;
    const canvas = document.createElement("canvas");
    canvas.width = Math.round(bmp.width * scale);
    canvas.height = Math.round(bmp.height * scale);
    const ctx = canvas.getContext("2d");
    if (!ctx) return file;
    ctx.drawImage(bmp, 0, 0, canvas.width, canvas.height);
    const blob = await new Promise<Blob | null>((r) => canvas.toBlob(r, "image/jpeg", 0.9));
    return blob ? new File([blob], file.name.replace(/\.[^.]+$/, "") + ".jpg", { type: "image/jpeg" }) : file;
  } catch {
    return file;
  }
}

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

  const handle = async (file?: File | null) => {
    if (!file) return;
    const problem = validateImage(file);
    setError(problem);
    if (!problem) onFile(await downscaleImage(file));
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
        className={`flex items-center gap-4 rounded-2xl border-2 border-dashed px-4 py-3 transition ${
          dragging ? "border-accent bg-accent-soft/60" : "border-line bg-surface/50 hover:border-ink-muted/50"
        }`}
      >
        {previewUrl ? (
          <img src={previewUrl} alt="Your uploaded reference" className="h-14 w-11 shrink-0 rounded-lg object-cover shadow-card" />
        ) : (
          <span className="bg-gradient-accent grid h-11 w-11 shrink-0 place-items-center rounded-xl text-on-accent shadow-glow">
            <CameraIcon width={20} height={20} />
          </span>
        )}
        <div className="min-w-0 flex-1 text-sm">
          <p className="font-medium text-ink">{previewUrl ? "Searching with your photo" : "Or search with a photo"}</p>
          <p className="text-ink-muted">
            Drop an image here, or{" "}
            <button
              type="button"
              disabled={busy}
              onClick={() => input.current?.click()}
              className="font-semibold text-accent underline-offset-4 hover:underline disabled:opacity-60 focus-visible:outline focus-visible:outline-2 focus-visible:outline-accent"
            >
              {previewUrl ? "choose another" : "browse files"}
            </button>
            <span className="hidden sm:inline"> · JPEG, PNG or WebP up to {MAX_UPLOAD_MB} MB</span>
          </p>
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
        <p role="alert" className="mt-2 text-sm text-danger">
          {error}
        </p>
      )}
    </div>
  );
}
