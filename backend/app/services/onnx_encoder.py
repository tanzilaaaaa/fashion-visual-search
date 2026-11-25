"""CLIP ViT-B/32 through ONNX Runtime: the small-memory encoder.

The OpenAI weights are exported once (``scripts/export_onnx.py``, at Docker
build time) to two int8-quantised graphs, so the running API needs neither
PyTorch nor open_clip. Pre-processing reproduces open_clip's transform for
ViT-B-32: resize the shortest side to 224 (bicubic), centre-crop 224, scale to
[0, 1], normalise with CLIP's mean/std. Output vectors are un-normalised, like
``ClipEncoder``; ``EmbeddingService`` L2-normalises them.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from PIL import Image

from .clip_tokenizer import ClipTokenizer

MEAN = np.array([0.48145466, 0.4578275, 0.40821073], dtype=np.float32)
STD = np.array([0.26862954, 0.26130258, 0.27577711], dtype=np.float32)
SIZE = 224


def preprocess(img: Image.Image, size: int = SIZE) -> np.ndarray:
    img = img.convert("RGB")
    w, h = img.size
    # Same arithmetic as torchvision's Resize(size) on a PIL image: short side -> size,
    # long side truncated (int), then PIL bicubic.
    if w <= h:
        new_w, new_h = size, int(size * h / w)
    else:
        new_w, new_h = int(size * w / h), size
    img = img.resize((new_w, new_h), Image.BICUBIC)
    w, h = img.size
    left, top = int(round((w - size) / 2.0)), int(round((h - size) / 2.0))
    img = img.crop((left, top, left + size, top + size))
    arr = np.asarray(img, dtype=np.float32) / 255.0
    return ((arr - MEAN) / STD).transpose(2, 0, 1)  # CHW


class OnnxClipEncoder:
    def __init__(self, model_dir: Path, threads: int = 1):
        import onnxruntime as ort

        model_dir = Path(model_dir)
        meta = json.loads((model_dir / "config.json").read_text())
        opts = ort.SessionOptions()
        opts.intra_op_num_threads = threads
        opts.inter_op_num_threads = 1
        opts.enable_cpu_mem_arena = False  # lower steady-state memory on tiny instances
        # Basic graph optimisation: same results, no slow first run (the full level re-plans
        # MatMulNBits kernels lazily, which costs seconds on a 0.1-CPU instance).
        opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_BASIC
        providers = ["CPUExecutionProvider"]
        self.visual = ort.InferenceSession(str(model_dir / meta["visual"]), opts, providers=providers)
        self.text = ort.InferenceSession(str(model_dir / meta["text"]), opts, providers=providers)
        self.tokenizer = ClipTokenizer()
        # Token-embedding table kept outside the graph, memory-mapped: only rows used are paged in.
        self.token_embedding = (
            np.load(model_dir / meta["token_embedding"], mmap_mode="r") if meta.get("token_embedding") else None
        )
        self.dim = int(meta["dim"])
        self.name = f"{meta['model_name']}/{meta['pretrained']} (onnx {meta.get('precision', 'int8')})"

    def encode_texts(self, texts: list[str]) -> np.ndarray:
        tokens = self.tokenizer(texts)
        if self.token_embedding is None:  # older single-graph export
            return self.text.run(None, {"tokens": tokens})[0].astype(np.float32)
        embeddings = np.asarray(self.token_embedding[tokens], dtype=np.float32)
        eot_index = tokens.argmax(axis=1).astype(np.int64)  # <end_of_text> has the highest id
        return self.text.run(None, {"embeddings": embeddings, "eot_index": eot_index})[0].astype(np.float32)

    def encode_images(self, images: list[Image.Image]) -> np.ndarray:
        batch = np.stack([preprocess(im) for im in images]).astype(np.float32)
        return self.visual.run(None, {"pixels": batch})[0].astype(np.float32)
