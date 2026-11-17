# Architecture

## Two paths

The **offline path** turns DeepFashion2 into a searchable index. It runs once per catalogue
version, on Kaggle. The **online path** answers queries against that prebuilt index. Startup is
load-only: the container never rebuilds the index, and a redeploy cannot lose it.

### Offline pipeline (`ml/fvs_ml/pipeline.py`)

| Step | Module | What happens |
|---|---|---|
| 1. Load | `annotations.py` | Every `itemN` in every per-image JSON → one row keyed by `split + image_id + N`; paths stay split-relative |
| 2. Clean | `clean.py` | Dedupe on `item_id`, drop missing essentials, unknown categories and boxes < 32 px. Keep occlusion, side views and consumer photos |
| 3. Hold out | `subset.py` | 25 % of validation **pairs** (capped at 4k images) → evaluation slice, never indexed |
| 4. Sample | `subset.py` | Category-balanced 50k subset; water-filling gives rare classes' unused quota to larger ones |
| 5. Crop + encode | `crop.py`, `embed.py` | OpenCV bbox crop (+6 % padding) → CLIP image encoder in batches; 5k-item shards checkpointed as `.npy` (resumable); WebP thumbnails written in the same pass |
| 6. Fine-tune | `finetune.py` | Mine consumer↔shop pairs from **train**; embed them (cached); train a residual adapter on frozen CLIP vectors with InfoNCE + text-prototype CE; early-stop and choose `r` on a 10 % pair-id tuning split; save `adapter.npz` |
| 7. Colour | `attributes.py` | Zero-shot on the **raw** CLIP vectors: cosine to prompt-ensembled colour prototypes, softmax; < 0.35 confidence → `multicolour` |
| 8. Index | `build_index.py` | Adapted vectors → L2-normalise → `IndexFlatIP`; `metadata.json` position-aligned with the index, including `worn_with`; `manifest.json` records the adapter |
| 9. Evaluate | `evaluate.py` | Served model vs baselines, plus pretrained-vs-fine-tuned ablation. See [EVALUATION.md](EVALUATION.md) |

The pipeline runs on a Kaggle T4 through `ml/kaggle/run_kaggle.py`. It bundles `fvs_ml` into
one private script kernel, pushes it with the Kaggle API, polls its status and downloads one
`fvs_artifacts.tar`.

### Online request sequence

```mermaid
sequenceDiagram
  participant U as User
  participant R as React (Vercel)
  participant A as FastAPI route
  participant S as SearchService
  participant E as EmbeddingService (CLIP)
  participant F as IndexService (FAISS)
  participant M as MetadataService
  U->>R: types query / drops photo
  R->>A: POST /api/search/text | /api/search/image via same-origin proxy (+ session cookie)
  A->>A: session check · validate (empty, length / MIME, magic bytes, size)
  A->>S: search_text / search_image (threadpool)
  S->>E: encode → unit 512-d vector (text LRU-cached; images also pass the adapter)
  S->>M: filters → allowed positions (unknown value → 400)
  S->>F: top-k·4 inner-product search (IDSelectorBatch if filtered)
  F-->>S: positions + cosine scores
  S->>M: metadata per position
  S->>S: final = α·cos + β·attr_match, sort, cut to k
  S-->>A: ranked items + detected/inferred attributes
  A-->>R: JSON (item_id, image_url, category, score, similarity…)
  R-->>U: ranked grid · empty state · inline error
```

## Backend modules (PRD §9.1)

| Module | Responsibility | Never does |
|---|---|---|
| `EmbeddingService` | Wraps an `Encoder` (CLIP or test fake); unit-norm text/image vectors; `(raw, search)` image views; zero-shot prototypes | search or ranking |
| `Adapter` | Loads `adapter.npz`; numpy forward pass identical to training (tanh-GELU) | anything else |
| `UserStore` | SQLite accounts; scrypt hashing; constant-time verify; timing-equalised unknown-email path | sessions or HTTP |
| `IndexService` | FAISS search (optionally restricted with an ID selector) and vector reconstruction | metadata |
| `MetadataService` | position ⇄ item, filter vocabulary, filter → positions; detects index/lookup drift at load | similarity |
| `SearchService` | embed → retrieve → metadata → filter → rank; owns final ordering | HTTP concerns |
| `RecommendationService` | Find Similar; Complete the Look via `CompatibilityMap`; a reason per item | encoding |
| `api/routes/*` | validation, threadpool hand-off, JSON shaping | model or index logic |

`container.py` wires these together once at startup. If the artifacts are missing or broken, the app
still starts: `/health` reports `degraded` and search returns 503 instead of the process crash-looping.

## Key decisions

* **Exact search (`IndexFlatIP`).** At 50k × 512 floats (~100 MB) a flat scan takes milliseconds
  and recall is exact. IVF/HNSW only becomes worthwhile at a much larger corpus (stretch goal).
* **Filtered search inside FAISS.** `IDSelectorBatch` keeps filtered queries exact. Post-filtering
  a fixed top-k could return too few items for rare filter combinations.
* **Over-fetch then re-rank.** When the attribute signal is active, `k × 4` candidates are fetched
  so an exact category/colour match just outside the raw top-k can rise.
* **SQLite only for accounts.** The catalogue is a static, read-only artifact, so JSON + FAISS
  files are simpler and cheaper than PostgreSQL or MongoDB (PRD §6). The only mutable state is
  user accounts, and a single SQLite file holds them (persistent storage on Spaces).
* **Adapter, not full fine-tuning.** Training only a 0.26M-parameter residual MLP on cached
  embeddings takes minutes on a T4 and never risks the backbone. At serve time it is two numpy
  matmuls, so the API image doesn't need training code. Text queries skip the adapter; the
  text-prototype loss keeps the adapted image space aligned with them.
* **Same-origin API.** The SPA calls `/api/*`, which Vite (dev) or a Vercel rewrite (prod)
  forwards to FastAPI. The session cookie is first-party (`SameSite=Lax`) and CORS isn't needed.
* **Themes as CSS variables.** Four themes redefine one set of RGB tokens on `<html data-theme>`.
  Components only use the semantic Tailwind colours (`surface`, `ink`, `accent` …), so adding a
  theme touches no component.
* **CPU inference.** One ViT-B/32 forward pass is ~10–40 ms on CPU, far inside the 2 s / 4 s budget.

## Security (PRD §11)

* Text: non-empty and ≤ 200 characters. Uploads: MIME allow-list, `Content-Length` pre-check,
  streamed size cap (413), magic-byte check, Pillow decompression-bomb guard. All checks run
  before decoding.
* CORS is restricted to `ALLOWED_ORIGINS`; HTTPS is provided by Vercel and Spaces.
* Item IDs are validated by regex and checked against the catalogue before any file access,
  so path traversal is impossible.
* Exceptions are logged server-side and returned as a generic 500. No paths are ever serialised.
* `slowapi` rate-limits search (default 60/min/IP), login (10/min/IP) and registration (5/min/IP).
* Accounts: passwords are hashed with salted scrypt and compared in constant time. Login returns
  the same response for an unknown email and a wrong password, and an unknown email still runs
  a dummy hash, so timing doesn't reveal which emails are registered. Sessions are HMAC-signed,
  expiring, HttpOnly cookies (`itsdangerous`) carrying only the user id. A session for a deleted
  account is rejected.
* Uploads are processed in memory and dropped. Logs record path, status and latency only,
  never queries or images.
