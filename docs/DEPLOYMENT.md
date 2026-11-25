# Deployment

Target: **frontend on Vercel** and **backend on Hugging Face Spaces (Docker)**, with **index
artifacts in a private Hugging Face dataset repo**. Everything below uses free tiers.

> Why not Render (PRD §13)? Measured peak memory of the backend is **~1.2 GB** (CLIP in PyTorch,
> the photo and text indexes, and the item data). Render's free and Starter plans give 512 MB, and
> free services also wipe their disk on every restart or 15-minute sleep. Render works on a paid
> 2 GB "Standard" instance with a persistent disk. A free Docker Space has 16 GB RAM and uses the
> same Dockerfile.

## 1 · GitHub

```bash
cd fashion-visual-search
git remote add origin https://github.com/<you>/fashion-visual-search.git
git push -u origin main
```

CI (`.github/workflows/ci.yml`) runs on every push and PR: backend lint + tests, ML lint +
tests, frontend tests + build, and a Docker build.

## 2 · Build the index (and fine-tune) on Kaggle

```bash
.venv/bin/pip install -e "ml[kaggle]"
# Kaggle → Settings → API → "Create New Token"; save the KGAT_… token:
mkdir -p ~/.kaggle && printf '%s' 'KGAT_…' > ~/.kaggle/access_token && chmod 600 ~/.kaggle/access_token
make kaggle-build       # private script kernel: T4 GPU, internet on, DeepFashion2 attached
make kaggle-status      # wait for "complete" (~1–1.5 h)
make kaggle-download    # → backend/artifacts/ (index.faiss, metadata.json, manifest.json,
                        #    evaluation.json, adapter.npz, images/)
```

* The Kaggle account must be **phone-verified**. Otherwise Kaggle silently disables internet
  and the GPU, and the kernel fails at `pip install`.
* `run_kaggle.py` embeds the `fvs_ml` sources in the kernel, so it doesn't need a GitHub clone.
* To deploy, upload the artifacts (~660 MB) to a **private** HF dataset repo
  `<hf-user>/fvs-artifacts`. Keep it private: DeepFashion2's terms forbid redistribution. The
  50k thumbnails go up as one `images.tar`, which uploads far faster than 50k small files:
  ```bash
  .venv/bin/hf auth login                                  # paste a WRITE token from hf.co/settings/tokens
  tar -cf /tmp/images.tar -C backend/artifacts images
  .venv/bin/hf upload <hf-user>/fvs-artifacts backend/artifacts . --repo-type dataset --private --exclude "images/*"
  .venv/bin/hf upload <hf-user>/fvs-artifacts /tmp/images.tar images.tar --repo-type dataset --private
  ```
  `backend/scripts/fetch_artifacts.py` downloads the repo during the Docker build and unpacks
  `images.tar`.

## 3 · Hugging Face Space (backend)

1. huggingface.co → **New Space** → SDK **Docker** → name `fashion-visual-search-api` → hardware *CPU basic (free)*.
2. **Account data:** a Space's own disk is wiped whenever it restarts. That happens on every
   deploy, and when a free Space wakes from its 48-hour sleep. Accounts, favorites, collections,
   interests and history (`users.db`) live there by default. For a demo that's acceptable. To
   keep them, attach a Hugging Face **Storage Bucket** at `/data` (Settings → Storage; billed per
   TB with a free allowance, see hf.co/storage) and set `USERS_DB_PATH=/data/users.db`. Buckets
   are mounted at runtime only, and SQLite on a network mount should be tested. A managed
   Postgres database (e.g. Neon's free tier) is the robust alternative but needs a code change.
3. **Settings → Variables and secrets**:
   * Variable `ARTIFACTS_REPO` = `<hf-user>/fvs-artifacts`
   * Secret `HF_TOKEN` = a **read** token that can see that repo (used only at build time)
   * Variable `AUTH_ENABLED` = `true` (and `USERS_DB_PATH` = `/data/users.db` only if a bucket is attached)
   * Secret `SESSION_SECRET` = a long random string (`python -c "import secrets;print(secrets.token_urlsafe(48))"`)
   * Variable `COOKIE_SECURE` = `true`
   * Variable `ALLOWED_ORIGINS` = `https://<your-app>.vercel.app` (only for direct API calls; the
     app itself goes through the Vercel proxy)
4. Deploy the backend code, either:
   * **automatically:** in GitHub repo settings add secret `HF_TOKEN` (a *write* token) and
     variables `HF_SPACE=<hf-user>/fashion-visual-search-api` and
     `API_URL=https://<hf-user>-fashion-visual-search-api.hf.space`. Every push to `main` then
     syncs `backend/` to the Space and waits for `/health` to report `index_loaded: true`; or
   * **manually, once:**
     ```bash
     cp deploy/huggingface/README.md backend/README.md && git add -A && git commit -m "Space README"
     git subtree push --prefix backend https://huggingface.co/spaces/<hf-user>/fashion-visual-search-api main
     ```
5. The first build downloads the artifacts and bakes in the CLIP weights (~5–10 min). Then check
   `https://<hf-user>-fashion-visual-search-api.hf.space/health`.

## 4 · Vercel (frontend)

1. In `frontend/vercel.json`, replace `<hf-user>` in the `/api/:path*` rewrite with your HF
   username, then commit. That rewrite proxies `/api/*` to the Space, so the session cookie is
   first-party. A direct cross-site cookie would be blocked by Safari and by any browser that
   blocks third-party cookies.
2. vercel.com → **Add New Project** → import the GitHub repo → **Root Directory** `frontend`
   (Vite is detected).
3. Leave `VITE_API_BASE_URL` unset. It defaults to `/api`.
4. Deploy. Every push to `main` redeploys automatically, and PRs get preview URLs.

## Cold starts

Free Spaces sleep after ~48 h without traffic. The first request after sleeping waits for the
container to start (model + index load ≈ 10–20 s); later requests take milliseconds. The app
header shows the server status. Before the final demo, open the URL once to wake it, or upgrade
the Space hardware so it never sleeps.

## Configuration reference

All variables are listed in `backend/.env.example`. The important ones are:
* `AUTH_ENABLED` (true), `USERS_DB_PATH`, `SESSION_SECRET`, `COOKIE_SECURE`;
* `ALLOWED_ORIGINS`, `MAX_UPLOAD_MB` (8), `TOP_K_DEFAULT` (24);
* `RANK_ALPHA`/`RANK_BETA` (0.85/0.15), `RATE_LIMIT` (60/minute);
* `MODEL_NAME` (`ViT-B-32-quickgelu`).

The adapter is picked up automatically when `manifest.json` lists it. If the manifest lists an
adapter but `adapter.npz` is missing, `/health` reports `degraded` instead of serving mismatched
vectors. Model, index and image paths are internal to the container and never exposed by the API.
