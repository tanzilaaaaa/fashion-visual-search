"""Test fixtures: a tiny synthetic catalogue and a deterministic fake CLIP encoder.

CI never downloads CLIP weights. The fake encoder maps keywords and image colours
onto fixed directions so ranking behaviour is predictable and assertable.
"""

from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path

import faiss
import numpy as np
import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.container import build_container
from app.core.config import Settings
from app.main import create_app

DIM = 16
# Concept → embedding axis.
AXES = {
    "short_sleeve_top": 0, "trousers": 1, "long_sleeve_dress": 2, "long_sleeve_outwear": 3,
    "red": 4, "blue": 5,
}
KEYWORDS = {
    "t-shirt": "short_sleeve_top", "top": "short_sleeve_top", "short sleeve top": "short_sleeve_top",
    "trousers": "trousers", "jeans": "trousers",
    "dress": "long_sleeve_dress", "jacket": "long_sleeve_outwear", "outwear": "long_sleeve_outwear",
    "red": "red", "blue": "blue",
}
CATEGORY_LABELS = {
    "short_sleeve_top": "short sleeve top", "trousers": "trousers",
    "long_sleeve_dress": "long sleeve dress", "long_sleeve_outwear": "long sleeve outwear",
}


def axis(name: str) -> np.ndarray:
    v = np.zeros(DIM, np.float32)
    v[AXES[name]] = 1.0
    return v


def noise(seed_text: str, scale: float) -> np.ndarray:
    seed = int(hashlib.sha256(seed_text.encode()).hexdigest()[:8], 16)
    return np.random.default_rng(seed).normal(scale=scale, size=DIM).astype(np.float32)


class FakeEncoder:
    dim = DIM
    name = "fake-clip"

    def __init__(self):
        self.text_calls = 0

    def encode_texts(self, texts):
        self.text_calls += len(texts)
        out = []
        for t in texts:
            low = t.lower()
            v = sum((axis(c) for k, c in KEYWORDS.items() if k in low), np.zeros(DIM, np.float32))
            out.append(v + noise(low, 0.05 if v.any() else 1.0))
        return np.stack(out)

    def encode_images(self, images):
        out = []
        for img in images:
            r, g, b = np.asarray(img.convert("RGB"), dtype=np.float32).reshape(-1, 3).mean(axis=0) / 255
            out.append(axis("long_sleeve_dress") + r * axis("red") + b * axis("blue") + 0.01)
        return np.stack(out)


def catalogue() -> tuple[list[dict], np.ndarray]:
    """4 categories × 2 colours × 3 items = 24 items; photos group a top with trousers."""
    items, vecs = [], []
    for cat in CATEGORY_LABELS:
        for colour in ("red", "blue"):
            for k in range(3):
                pos = len(items)
                item_id = f"train-{pos:06d}-1"
                items.append({
                    "position": pos, "item_id": item_id, "category": CATEGORY_LABELS[cat],
                    "category_key": cat, "colour": colour, "colour_confidence": 0.9,
                    "source": "shop" if k == 0 else "user", "viewpoint": "frontal",
                    "occlusion": "slight", "scale": "moderate", "zoom_in": "none",
                    "pair_id": pos, "style": 1, "split": "train", "image_id": f"{pos:06d}",
                    "worn_with": [],
                })
                vecs.append(axis(cat) + 0.6 * axis(colour) + noise(item_id, 0.05))
    # Item 0 (red top) was photographed with item 9 (blue trousers... index 9 = trousers/blue/0).
    items[0]["worn_with"] = [items[9]["item_id"]]
    items[9]["worn_with"] = [items[0]["item_id"]]
    v = np.stack(vecs).astype(np.float32)
    v /= np.linalg.norm(v, axis=1, keepdims=True)
    return items, v


@pytest.fixture()
def artifacts(tmp_path: Path) -> Path:
    items, vecs = catalogue()
    index = faiss.IndexFlatIP(DIM)
    index.add(vecs)
    faiss.write_index(index, str(tmp_path / "index.faiss"))
    (tmp_path / "metadata.json").write_text(json.dumps({"version": 1, "items": items}))
    (tmp_path / "manifest.json").write_text(json.dumps({"item_count": len(items), "cleaning": {"x": 1}}))
    img_dir = tmp_path / "images"
    img_dir.mkdir()
    for it in items:
        Image.new("RGB", (8, 8), (200, 0, 0)).save(img_dir / f"{it['item_id']}.webp", "WEBP")
    return tmp_path


def make_settings(artifacts: Path, **overrides) -> Settings:
    base = dict(
        artifacts_dir=artifacts, load_model_on_startup=False, rate_limit_enabled=False,
        allowed_origins=["http://localhost:5173"], top_k_default=5, max_upload_mb=1.0,
        auth_enabled=False, users_db_path=artifacts / "users.db", session_secret="test-secret",
        _env_file=None,
    )
    base.update(overrides)
    return Settings(**base)


@pytest.fixture()
def make_client(artifacts):
    clients = []

    def _make(encoder=None, raise_server_exceptions=True, **overrides) -> TestClient:
        settings = make_settings(artifacts, **overrides)
        enc = encoder or FakeEncoder()
        app = create_app(settings, container_factory=lambda s: build_container(s, encoder=enc))
        client = TestClient(app, raise_server_exceptions=raise_server_exceptions)
        client.__enter__()
        clients.append(client)
        return client

    yield _make
    for c in clients:
        c.__exit__(None, None, None)


@pytest.fixture()
def client(make_client) -> TestClient:
    return make_client()


def png_bytes(colour=(220, 10, 10), size=(32, 32), fmt="PNG") -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", size, colour).save(buf, fmt)
    return buf.getvalue()
