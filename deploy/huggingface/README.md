---
title: Fashion Visual Search API
emoji: 👗
colorFrom: pink
colorTo: gray
sdk: docker
app_port: 7860
pinned: false
---

FastAPI backend for the AI-Powered Fashion Visual Search & Recommendation System
(CLIP ViT-B/32 + FAISS over DeepFashion2). Open `/docs` for the OpenAPI reference and `/health` for status.

Space settings this needs:
* **Variable** `ARTIFACTS_REPO` = `<user>/fvs-artifacts` (the private dataset repo holding the index)
* **Secret** `HF_TOKEN` = a read token for that repo (used only at build time)
* **Variable** `ALLOWED_ORIGINS` = your Vercel URL, e.g. `https://lookbook.vercel.app`
