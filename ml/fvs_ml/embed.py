"""Batched CLIP ViT-B/32 encoding with resumable, sharded checkpoints."""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
import pandas as pd
import torch
from torch.utils.data import DataLoader, Dataset

from .crop import crop_garment, save_thumbnail

log = logging.getLogger(__name__)


def pick_device() -> str:
    if torch.cuda.is_available():
        return "cuda"
    if torch.backends.mps.is_available():
        return "mps"
    return "cpu"


def load_clip(model_name: str = "ViT-B-32-quickgelu", pretrained: str = "openai", device: str | None = None):
    import open_clip

    device = device or pick_device()
    model, _, preprocess = open_clip.create_model_and_transforms(model_name, pretrained=pretrained)
    model = model.to(device).eval()
    tokenizer = open_clip.get_tokenizer(model_name)
    return model, preprocess, tokenizer, device


class CropDataset(Dataset):
    """Reads a source photo, crops the garment, writes its thumbnail, returns CLIP input."""

    def __init__(
        self,
        items: pd.DataFrame,
        dataset_root: Path,
        preprocess,
        padding: float,
        thumb_dir: Path | None,
        thumb_size: int,
    ):
        self.items = items.reset_index(drop=True)
        self.root = Path(dataset_root)
        self.preprocess = preprocess
        self.padding = padding
        self.thumb_dir = thumb_dir
        self.thumb_size = thumb_size

    def __len__(self) -> int:
        return len(self.items)

    def __getitem__(self, i: int):
        row = self.items.iloc[i]
        try:
            img = crop_garment(
                self.root / row.image_relpath,
                (row.bbox_x1, row.bbox_y1, row.bbox_x2, row.bbox_y2),
                self.padding,
            )
        except (FileNotFoundError, ValueError):
            return torch.zeros(3, 224, 224), i, False
        if self.thumb_dir is not None:
            out = self.thumb_dir / f"{row.item_id}.webp"
            if not out.exists():
                save_thumbnail(img, out, self.thumb_size)
        return self.preprocess(img), i, True


@torch.no_grad()
def encode_items(
    items: pd.DataFrame,
    dataset_root: Path,
    model,
    preprocess,
    device: str,
    work_dir: Path,
    thumb_dir: Path | None,
    batch_size: int = 256,
    num_workers: int = 2,
    padding: float = 0.06,
    thumb_size: int = 256,
    shard_size: int = 5_000,
    tag: str = "catalogue",
) -> tuple[np.ndarray, np.ndarray]:
    """Encode every item; returns ``(vectors[N, 512], ok_mask[N])``.

    Work is split into shards saved as ``.npy``; rerunning skips finished shards,
    so a Kaggle session that times out resumes where it stopped.
    """
    work_dir = Path(work_dir) / tag
    work_dir.mkdir(parents=True, exist_ok=True)
    n = len(items)
    vecs, oks = [], []
    for start in range(0, n, shard_size):
        end = min(n, start + shard_size)
        vec_path = work_dir / f"vec_{start:07d}_{end:07d}.npy"
        ok_path = work_dir / f"ok_{start:07d}_{end:07d}.npy"
        if vec_path.exists() and ok_path.exists():
            vecs.append(np.load(vec_path))
            oks.append(np.load(ok_path))
            log.info("shard %s-%s: cached", start, end)
            continue

        ds = CropDataset(items.iloc[start:end], dataset_root, preprocess, padding, thumb_dir, thumb_size)
        loader = DataLoader(ds, batch_size=batch_size, num_workers=num_workers, shuffle=False)
        shard_vec = np.zeros((end - start, model.visual.output_dim), dtype=np.float32)
        shard_ok = np.zeros(end - start, dtype=bool)
        for pixels, idx, ok in loader:
            feats = model.encode_image(pixels.to(device))
            feats = torch.nn.functional.normalize(feats.float(), dim=-1).cpu().numpy()
            shard_vec[idx.numpy()] = feats
            shard_ok[idx.numpy()] = ok.numpy()
        np.save(vec_path, shard_vec)
        np.save(ok_path, shard_ok)
        vecs.append(shard_vec)
        oks.append(shard_ok)
        log.info("shard %s-%s: encoded (%d ok)", start, end, int(shard_ok.sum()))

    return np.concatenate(vecs), np.concatenate(oks)


@torch.no_grad()
def encode_texts(texts: list[str], model, tokenizer, device: str) -> np.ndarray:
    tokens = tokenizer(texts).to(device)
    feats = model.encode_text(tokens)
    return torch.nn.functional.normalize(feats.float(), dim=-1).cpu().numpy()
