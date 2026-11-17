# syntax=docker/dockerfile:1.7
# Fashion Visual Search API — CPU inference image.
# Works on Hugging Face Spaces (Docker SDK, port 7860) and any container host.
FROM python:3.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    HF_HOME=/opt/hf-cache \
    PORT=7860 \
    ARTIFACTS_DIR=/app/artifacts

RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 curl \
    && rm -rf /var/lib/apt/lists/*

# Spaces run containers as uid 1000.
RUN useradd --create-home --uid 1000 app
WORKDIR /app

COPY requirements.txt requirements-ml.txt ./
RUN pip install --index-url https://download.pytorch.org/whl/cpu torch==2.15.0 torchvision==0.29.2 \
    && pip install -r requirements.txt -r requirements-ml.txt

# Bake the CLIP weights into the image so startup never downloads anything.
ARG MODEL_NAME=ViT-B-32-quickgelu
RUN python -c "import open_clip; open_clip.create_model_and_transforms('${MODEL_NAME}', pretrained='openai')"

COPY app ./app
COPY scripts ./scripts
# Local artifacts (if any) are copied; otherwise they're pulled from a private HF dataset repo.
COPY artifacts ./artifacts
ARG ARTIFACTS_REPO=""
RUN --mount=type=secret,id=HF_TOKEN,required=false \
    ARTIFACTS_REPO="${ARTIFACTS_REPO}" python scripts/fetch_artifacts.py --dest /app/artifacts

RUN chown -R app:app /app /opt/hf-cache
USER app

EXPOSE 7860
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
    CMD curl -fsS "http://127.0.0.1:${PORT}/health" | grep -q '"index_loaded":true' || exit 1

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT} --proxy-headers --forwarded-allow-ips='*' --workers 1"]
