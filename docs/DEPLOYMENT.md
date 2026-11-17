# Deployment

Target: **frontend on Vercel**, **backend on Hugging Face Spaces (Docker)**, with **index artifacts
in a private Hugging Face dataset repo**. Everything below uses free tiers.

> Why not Render (PRD §13)? Render's free and Starter plans give 512 MB RAM. CLIP ViT-B/32
> (PyTorch) plus a 50k index needs ~1–1.5 GB at runtime and would be OOM-killed. A Docker Space
> on the free tier has 16 GB RAM and uses the same Dockerfile.

## 1 · GitHub

```bash
cd fashion-visual-search
git remote add origin https://github.com/<you>/fashion-visual-search.git
git push -u origin main
```

CI (`.github/workflows/ci.yml`) runs on every push and PR: backend lint + tests, ML lint +
tests, frontend tests + build, and a Docker build.

## 2 · Build the index on Kaggle

Follow the README's "Building the index" section and run the last notebook cell with
`PUSH_TO_HF = True`. This creates a **private** dataset repo `<hf-user>/fvs-artifacts`
containing `index.faiss`, `metadata.json`, `manifest.json`, `evaluation.json` and `images.tar`.
Keep it private: DeepFashion2's terms forbid redistribution.

## 3 · Hugging Face Space (backend)

1. huggingface.co → **New Space** → SDK **Docker** → name `fashion-visual-search-api` → hardware *CPU basic (free)*.
2. Space **Settings → Variables and secrets**:
   * Variable `ARTIFACTS_REPO` = `<hf-user>/fvs-artifacts`
   * Secret `HF_TOKEN` = a **read** token that can see that repo (used only at build time)
   * Variable `ALLOWED_ORIGINS` = `https://<your-app>.vercel.app`
   * Optional demo login: `AUTH_ENABLED=true`, secret `DEMO_PASSWORD`, secret `SESSION_SECRET`
     (a long random string) and `COOKIE_SECURE=true`
3. Deploy the backend code, either:
   * **automatically:** in GitHub repo settings add secret `HF_TOKEN` (a *write* token) and
     variables `HF_SPACE=<hf-user>/fashion-visual-search-api` and
     `API_URL=https://<hf-user>-fashion-visual-search-api.hf.space`. Every push to `main` then
     syncs `backend/` to the Space and waits for `/health` to report `index_loaded: true`; or
   * **manually, once:**
     ```bash
     cp deploy/huggingface/README.md backend/README.md && git add -A && git commit -m "Space README"
     git subtree push --prefix backend https://huggingface.co/spaces/<hf-user>/fashion-visual-search-api main
     ```
4. The first build downloads the artifacts and bakes in the CLIP weights (~5–10 min). Then check
   `https://<hf-user>-fashion-visual-search-api.hf.space/health`.

## 4 · Vercel (frontend)

1. vercel.com → **Add New Project** → import the GitHub repo → **Root Directory** `frontend`
   (Vite is detected; `vercel.json` adds SPA rewrites and security headers).
2. Environment variable `VITE_API_BASE_URL` = `https://<hf-user>-fashion-visual-search-api.hf.space`.
3. Deploy. Every push to `main` redeploys automatically, and PRs get preview URLs.
4. Copy the production URL into the Space's `ALLOWED_ORIGINS`. The Space restarts, and CORS then
   only allows your frontend.

## Cold starts

Free Spaces sleep after ~48 h without traffic. The first request after sleeping waits for the
container to start (model + index load ≈ 10–20 s); later requests take milliseconds. The UI shows
the server status in the header and a clear timeout message. Before the final demo, open the URL
once to wake it, or upgrade the Space hardware so it never sleeps.

## Configuration reference

All variables are listed in `backend/.env.example`. The important ones are `ALLOWED_ORIGINS`,
`MAX_UPLOAD_MB` (8), `TOP_K_DEFAULT` (24), `RANK_ALPHA`/`RANK_BETA` (0.85/0.15), `RATE_LIMIT`
(60/minute), `AUTH_ENABLED`, `SESSION_SECRET` and `MODEL_NAME` (`ViT-B-32-quickgelu`).
Model, index and image paths are internal to the container and never exposed by the API.
