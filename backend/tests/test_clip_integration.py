"""Real-model checks. Opt-in: ``pytest -m clip`` (downloads ~350 MB of weights once)."""

from __future__ import annotations

import numpy as np
import pytest
from PIL import Image

pytestmark = pytest.mark.clip


@pytest.fixture(scope="module")
def svc():
    from app.services.embedding import ClipEncoder, EmbeddingService

    return EmbeddingService(ClipEncoder())


def test_text_vectors_unit_norm_and_deterministic(svc):
    a = svc.encode_text("black oversized hoodie")
    svc._cache.clear()
    b = svc.encode_text("black oversized hoodie")
    assert a.shape == (512,)
    assert abs(np.linalg.norm(a) - 1) < 1e-4
    np.testing.assert_allclose(a, b, atol=1e-5)


def test_shared_space_matches_colour(svc):
    red = svc.encode_image(Image.new("RGB", (224, 224), (210, 20, 30)))
    assert abs(np.linalg.norm(red) - 1) < 1e-4
    assert red @ svc.encode_text("a red fabric") > red @ svc.encode_text("a blue fabric")


def test_zero_shot_category(svc):
    vec = svc.encode_text("a photo of a pleated skirt")
    label, _ = svc.zero_shot(vec, "category", ["skirt", "trousers", "long sleeve top"])
    assert label == "skirt"
