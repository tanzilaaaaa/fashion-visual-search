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
confidence. A guess is used for ranking only when its confidence is ≥ 0.5. The zero-shot guess
uses the raw CLIP vector; the search itself uses the fine-tuned adapter's vector when the index
was built with one.

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

* `GET /showcase?n=12` → `{items: [ItemSummary…]}`: a deterministic, category-diverse sample
  (shop photos first). It is public and used by the landing page.

## Accounts (`AUTH_ENABLED=true`, the default)

| Endpoint | Body | Result |
|---|---|---|
| `POST /auth/register` | `{name, email, password}` | **201** + session cookie. 400 `invalid_name` / `invalid_email` / `weak_password`, **409** `email_taken`, 429 after 5/min |
| `POST /auth/login` | `{email, password}` | 200 + session cookie. **401** `invalid_credentials` (same response whether or not the email exists), 429 after 10/min |
| `POST /auth/logout` | — | clears the cookie |
| `GET /auth/me` | — | `{authenticated, auth_enabled, user: {id, name, email} \| null}` |

Passwords: 8–128 characters, at least one letter and one digit. Emails are trimmed and
lower-cased. The `fvs_session` cookie is HttpOnly, `SameSite=Lax` and HMAC-signed with
`SESSION_SECRET`, and it expires after `SESSION_MAX_AGE_S` (8 h). Without a valid session for an
existing account, `/search/*` and `/items/*` return **401** `unauthorized`. `/health`, `/filters`,
`/images/*`, `/evaluation` and `/showcase` stay public.

## Profile (`/me/*`, always needs a session for an existing account; 401 otherwise)

| Endpoint | Purpose |
|---|---|
| `GET /me/profile` · `PATCH /me/profile` | profile, interests and stats · update `{name?, bio?, location?, avatar_color?}` |
| `PUT /me/interests` | `{categories, colours, styles}`. Unknown category or colour → 400 `unsupported_filter`; style tags 1–24 characters |
| `GET /me/favorites` · `GET /me/favorites/ids` | saved items (newest first, with `saved_at`) · ids only |
| `PUT` / `DELETE /me/favorites/{item_id}` | save / unsave (idempotent; unknown item → 404; more than 500 → 400 `limit_reached`) |
| `GET` / `POST /me/collections` | list (with 4-item covers) / create `{name}` (409 `collection_exists`, case-insensitive) |
| `GET` / `PATCH` / `DELETE /me/collections/{id}` | one collection / rename / delete (another user's id → 404) |
| `PUT` / `DELETE /me/collections/{id}/items/{item_id}` | add (also favorites the item) / remove |
| `GET /me/history` · `DELETE /me/history` · `DELETE /me/history/{id}` | last 20 distinct text searches, recorded by `POST /search/text` |
| `GET /me/recommendations?top_k=12` | `{sections: [{key: "favorites" \| "interests", title, items}], has_favorites, has_interests}` |
| `PATCH /me/account` · `POST /me/password` · `DELETE /me/account` | change email / password / delete everything (each needs the current password; 10/min) |

Un-favoriting an item removes it from every collection. Deleting the account cascades through
all profile tables and clears the session cookie.

The browser reaches the API at `/api/*` on the frontend's own origin (Vite proxy locally, Vercel
rewrite in production), so the cookie is first-party.

## Errors

```json
{ "error": { "code": "empty_query", "message": "Please enter a description to search for." } }
```

| Status | Codes |
|---|---|
| 400 | `empty_query`, `query_too_long`, `unsupported_filter`, `malformed_filters`, `missing_file`, `empty_file`, `unsupported_type`, `invalid_image`, `invalid_name`, `invalid_email`, `weak_password` |
| 401 | `unauthorized`, `invalid_credentials` |
| 404 | `not_found` |
| 409 | `email_taken` |
| 413 | `payload_too_large` |
| 422 | `validation_error` (e.g. non-integer `top_k`) |
| 429 | `rate_limited` |
| 503 | `not_ready` (artifacts or model not loaded) |
| 500 | `internal_error` (generic message; details only in server logs) |

A valid query that matches nothing returns **200** with `total: 0`, never an error.
