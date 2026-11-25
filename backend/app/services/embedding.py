"""EmbeddingService — the only module that touches CLIP (PRD §9.1).

The CLIP model sits behind a small ``Encoder`` protocol so tests (and CI) can use
a deterministic fake without downloading weights, and so the checkpoint can be
swapped without touching search, ranking or the API layer.
"""

from __future__ import annotations

import logging
import threading
from collections import OrderedDict
from typing import Protocol

import numpy as np
from PIL import Image

from .adapter import Adapter

log = logging.getLogger(__name__)


class Encoder(Protocol):
    dim: int
    name: str

    def encode_texts(self, texts: list[str]) -> np.ndarray: ...

    def encode_images(self, images: list[Image.Image]) -> np.ndarray: ...


class ClipEncoder:
    """open_clip ViT-B/32 with pretrained OpenAI weights, CPU inference."""

    def __init__(self, model_name: str = "ViT-B-32-quickgelu", pretrained: str = "openai", device: str = "cpu"):
        import open_clip
        import torch

        self._torch = torch
        self.device = device
        model, _, preprocess = open_clip.create_model_and_transforms(model_name, pretrained=pretrained)
        self.model = model.to(device).eval()
        # Same transform as the offline indexing pipeline, so query vectors are comparable.
        self.preprocess = preprocess
        self.tokenizer = open_clip.get_tokenizer(model_name)
        self.dim = int(self.model.visual.output_dim)
        self.name = f"{model_name}/{pretrained}"

    def encode_texts(self, texts: list[str]) -> np.ndarray:
        torch = self._torch
        with torch.inference_mode():
            feats = self.model.encode_text(self.tokenizer(texts).to(self.device))
        return feats.float().cpu().numpy()

    def encode_images(self, images: list[Image.Image]) -> np.ndarray:
        torch = self._torch
        batch = torch.stack([self.preprocess(img.convert("RGB")) for img in images]).to(self.device)
        with torch.inference_mode():
            feats = self.model.encode_image(batch)
        return feats.float().cpu().numpy()


def l2_normalise(x: np.ndarray) -> np.ndarray:
    x = np.asarray(x, dtype=np.float32)
    norms = np.linalg.norm(x, axis=-1, keepdims=True)
    return x / np.clip(norms, 1e-12, None)


class EmbeddingService:
    """Text/image → unit-norm vectors, plus zero-shot prototypes for attribute inference."""

    CATEGORY_TEMPLATES = ("a photo of a {}.", "a person wearing a {}.", "a product photo of a {}.")
    COLOUR_TEMPLATES = ("a photo of a {} piece of clothing.", "a {} garment.", "{} colored fabric.")

    def __init__(self, encoder: Encoder, text_cache_size: int = 512, adapter: Adapter | None = None):
        self.encoder = encoder
        self.adapter = adapter
        self._cache: OrderedDict[str, np.ndarray] = OrderedDict()
        self._cache_size = text_cache_size
        self._lock = threading.Lock()
        self._prototypes: dict[str, tuple[list[str], np.ndarray]] = {}

    @property
    def dim(self) -> int:
        return self.encoder.dim

    @property
    def model_name(self) -> str:
        return self.encoder.name + (" + fine-tuned adapter" if self.adapter is not None else "")

    def encode_text(self, text: str) -> np.ndarray:
        key = " ".join(text.lower().split())
        with self._lock:
            if key in self._cache:
                self._cache.move_to_end(key)
                return self._cache[key].copy()
        vec = l2_normalise(self.encoder.encode_texts([text]))[0]
        with self._lock:
            self._cache[key] = vec
            if len(self._cache) > self._cache_size:
                self._cache.popitem(last=False)
        return vec.copy()

    def encode_image(self, image: Image.Image) -> np.ndarray:
        """Search vector for an image (adapted when a fine-tuned adapter is loaded)."""
        return self.encode_image_views(image)[1]

    def encode_image_views(self, image: Image.Image) -> tuple[np.ndarray, np.ndarray]:
        """``(raw, search)``: raw CLIP for zero-shot vs text prompts, search for the index."""
        raw = l2_normalise(self.encoder.encode_images([image]))[0]
        return raw, (self.adapter.apply(raw) if self.adapter is not None else raw)

    def prototypes(self, kind: str, labels: list[str]) -> np.ndarray:
        """Prompt-ensembled label embeddings, computed once and cached."""
        templates = self.CATEGORY_TEMPLATES if kind == "category" else self.COLOUR_TEMPLATES
        cached = self._prototypes.get(kind)
        if cached and cached[0] == labels:
            return cached[1]
        protos = []
        for label in labels:
            emb = l2_normalise(self.encoder.encode_texts([t.format(label) for t in templates]))
            protos.append(l2_normalise(emb.mean(axis=0)))
        arr = np.stack(protos).astype(np.float32)
        self._prototypes[kind] = (labels, arr)
        return arr

    def save_prototypes(self, path) -> None:
        """Persist computed label prototypes (``prototypes.npz``) so a cold start skips them."""
        data = {}
        for kind, (labels, arr) in self._prototypes.items():
            data[f"{kind}__labels"] = np.array(labels, dtype=str)
            data[f"{kind}__vectors"] = arr
        np.savez(path, **data)

    def load_prototypes(self, path) -> list[str]:
        """Load precomputed prototypes; returns the kinds loaded. Labels are re-checked on use."""
        loaded = []
        with np.load(path, allow_pickle=False) as z:
            for key in z.files:
                if key.endswith("__labels"):
                    kind = key[: -len("__labels")]
                    self._prototypes[kind] = ([str(x) for x in z[key]], z[f"{kind}__vectors"].astype(np.float32))
                    loaded.append(kind)
        return loaded

    def zero_shot(
        self, vector: np.ndarray, kind: str, labels: list[str], temperature: float = 100.0
    ) -> tuple[str, float]:
        """Most likely label for an image vector and its softmax probability."""
        logits = temperature * (self.prototypes(kind, labels) @ vector)
        logits -= logits.max()
        probs = np.exp(logits) / np.exp(logits).sum()
        best = int(probs.argmax())
        return labels[best], float(probs[best])
