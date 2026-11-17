# API reference

Interactive OpenAPI docs are served at `/docs` (Swagger) and `/redoc`. Base URL locally: `http://localhost:8000`.

## POST /search/text

```json
{ "query": "red casual summer dress", "top_k": 24,
  "filters": { "category": ["short_sleeve_dress"], "colour": ["red"], "source": [], "viewpoint": [] },
  "alpha": 0.85, "beta": 0.15 }
```

Only `query` is required. Unknown body fields → 422.

```json
{
  "mode": "text",
  "query": "red casual summer dress",
  "total": 24,
  "results": [
    { "item_id": "train-012345-1", "image_url": "/images/train-012345-1",
      "category": "short sleeve dress", "category_key": "short_sleeve_dress", "colour": "red",
      "source": "shop", "viewpoint": "frontal",
      "score": 0.4268, "similarity": 0.3256, "attribute_match": 1.0, "reason": null }
  ],
  "applied_filters": {},
  "detected": { "categories": ["long_sleeve_dress", "short_sleeve_dress", "sling_dress", "vest_dress"], "colours": ["red"] },
  "inferred": null,
  "ranking": { "alpha": 0.85, "beta": 0.15, "attribute_signal_used": true },
  "candidates_considered": 96,
  "latency_ms": 39.5
}
```

`score` is the final ranking value and `similarity` is the raw FAISS cosine. When no attribute
is detected, or `beta = 0`, `score == similarity`.

## POST /search/image

`multipart/form-data`: `file` (JPEG/PNG/WebP, ≤ `MAX_UPLOAD_MB`), plus optional `top_k`,
`filters` (JSON string), `alpha` and `beta`. The response has the same shape, with
`mode: "image"` and `inferred` holding CLIP's zero-shot `{category, colour}` guesses and their
confidence. A guess is used for ranking only when its confidence is ≥ 0.5.

## Items

* `GET /items/{id}` → metadata, including occlusion, scale, colour confidence, `pair_id`, `style` and `worn_with`.
* `GET /items/{id}/similar?top_k=12` → `{source, total, results[]}`; the source item is never included.
* `GET /items/{id}/recommendations?per_group=6` →
  `{source, groups: [{group: "bottoms", label: "Bottoms", items: [... reason ...]}]}`.

## Meta

* `GET /filters` → `{fields: {category|colour|source|viewpoint: {label, options: [{value, label, count}]}}}`
* `GET /images/{id}` → `image/webp`, cached for 7 days
* `GET /health` → `{status: "ok"|"degraded", model_loaded, index_loaded, item_count, model, startup_error, stats}`
* `GET /evaluation` → `{evaluation, manifest}`, or 404 if none was generated

## Auth (optional, `AUTH_ENABLED=true`)

`POST /auth/login {username, password}` sets the HttpOnly `fvs_session` cookie.
`POST /auth/logout` clears it. `GET /auth/me` returns the session. When auth is enabled,
`/search/*` and `/items/*` return 401 without a valid cookie.

## Errors

```json
{ "error": { "code": "empty_query", "message": "Please enter a description to search for." } }
```

| Status | Codes |
|---|---|
| 400 | `empty_query`, `query_too_long`, `unsupported_filter`, `malformed_filters`, `missing_file`, `empty_file`, `unsupported_type`, `invalid_image` |
| 401 | `unauthorized`, `invalid_credentials` |
| 404 | `not_found` |
| 413 | `payload_too_large` |
| 422 | `validation_error` (e.g. non-integer `top_k`) |
| 429 | `rate_limited` |
| 503 | `not_ready` (artifacts or model not loaded) |
| 500 | `internal_error` (generic message; details only in server logs) |

A valid query that matches nothing returns **200** with `total: 0`, never an error.
