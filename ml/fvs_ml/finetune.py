"""Fine-tune a residual CLIP-Adapter on DeepFashion2 consumer↔shop pairs.

The CLIP ViT-B/32 backbone stays frozen (PRD §5.3). On top of its 512-d image
embedding we learn a small bottleneck MLP and blend it back in residually::

    z' = normalise( r · MLP(z) + (1 − r) · z )        MLP: 512 → 256 → 512 (GELU)

Training signal
---------------
* **Retrieval (InfoNCE):** a consumer ("user") photo of a garment and the shop
  photo of the same garment (same ``pair_id`` and ``style`` > 0) are pulled
  together; every other garment in the batch is a negative. Symmetric loss with
  a learnable temperature, as in CLIP itself.
* **Text alignment (cross-entropy):** adapted image vectors must still classify
  their category against the *frozen* CLIP text prototypes. Without this term the
  adapter could drift away from the text space and break text search.

Because the backbone is frozen, embeddings are computed once (and cached by
``encode_items``); training then runs on 512-d vectors and takes minutes.

Data hygiene
------------
Pairs are mined from the **train** split only. 10 % of pair ids are held out as a
tuning split used for early stopping and for choosing ``r``. The evaluation slice
(drawn from validation in ``subset.holdout_eval_slice``) is never seen here.

The exported ``adapter.npz`` is applied in plain numpy by the API, so the serving
image never needs this training code. GELU uses the tanh approximation in both
places so the two implementations agree to float precision.
"""

from __future__ import annotations

import json
import logging
import math
import time
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
import pandas as pd

log = logging.getLogger(__name__)

ADAPTER_VERSION = 1


@dataclass
class FinetuneConfig:
    hidden: int = 256
    train_ratio: float = 0.6          # residual blend used while training
    ratio_grid: tuple[float, ...] = (0.0, 0.2, 0.4, 0.6, 0.8)
    text_weight: float = 0.5          # λ for the category / text-alignment term
    max_text_drop: float = 0.02       # allowed drop in text P@10 when choosing r
    fixed_ratio: float | None = None  # skip the search and use this r (ablations / smoke tests)
    epochs: int = 40
    batch_groups: int = 1024
    lr: float = 1e-3
    weight_decay: float = 1e-4
    max_items: int = 60_000
    val_fraction: float = 0.10
    seed: int = 42


# --------------------------------------------------------------------------- #
# Pair mining
# --------------------------------------------------------------------------- #
def mine_pairs(items: pd.DataFrame, max_items: int, val_fraction: float, seed: int) -> pd.DataFrame:
    """Return train-split items that belong to a complete consumer↔shop group.

    A *group* is ``(pair_id, style)`` with ``style > 0`` that has at least one
    ``user`` and one ``shop`` item. The result has a ``group`` integer column and a
    boolean ``is_val`` column (whole pair ids are held out, never half a pair).
    """
    df = items[(items["split"] == "train") & (items["style"] > 0)].copy()
    if df.empty:
        return df.assign(group=pd.Series(dtype=int), is_val=pd.Series(dtype=bool))
    key = df["pair_id"].astype(str) + ":" + df["style"].astype(str)
    sources = df.groupby(key)["source"].agg(lambda s: {"user", "shop"} <= set(s))
    complete = sources[sources].index
    df = df[key.isin(complete)]
    key = key[df.index]

    rng = np.random.default_rng(seed)
    groups = np.array(sorted(set(key)))
    rng.shuffle(groups)
    sizes = key.value_counts()
    keep, total = [], 0
    for g in groups:
        if total >= max_items:
            break
        keep.append(g)
        total += int(sizes[g])
    df = df[key.isin(set(keep))].copy()
    key = key[df.index]

    pair_ids = np.array(sorted(df["pair_id"].unique()))
    rng.shuffle(pair_ids)
    n_val = max(1, int(round(len(pair_ids) * val_fraction))) if len(pair_ids) > 1 else 0
    val_pairs = set(pair_ids[:n_val].tolist())
    df["group"] = pd.factorize(key)[0]
    df["is_val"] = df["pair_id"].isin(val_pairs)
    return df.reset_index(drop=True)


# --------------------------------------------------------------------------- #
# Model
# --------------------------------------------------------------------------- #
def _torch():
    import torch

    return torch


def build_adapter(dim: int, hidden: int):
    torch = _torch()
    nn = torch.nn

    class Adapter(nn.Module):
        def __init__(self) -> None:
            super().__init__()
            self.fc1 = nn.Linear(dim, hidden)
            self.fc2 = nn.Linear(hidden, dim)
            self.act = nn.GELU(approximate="tanh")
            # Zero-initialised output → the adapter starts as the identity map,
            # so training can only move away from pretrained CLIP if it helps.
            nn.init.zeros_(self.fc2.weight)
            nn.init.zeros_(self.fc2.bias)

        def forward(self, z, ratio: float):
            h = self.fc2(self.act(self.fc1(z)))
            return nn.functional.normalize(ratio * h + (1.0 - ratio) * z, dim=-1)

    return Adapter()


def _gelu_tanh(x: np.ndarray) -> np.ndarray:
    return 0.5 * x * (1.0 + np.tanh(math.sqrt(2.0 / math.pi) * (x + 0.044715 * x**3)))


def apply_adapter_np(weights: dict, z: np.ndarray, ratio: float | None = None) -> np.ndarray:
    """Numpy forward pass; identical maths to ``app.services.adapter.Adapter``."""
    r = float(weights["ratio"] if ratio is None else ratio)
    z = np.asarray(z, dtype=np.float32)
    h = _gelu_tanh(z @ weights["W1"].T + weights["b1"]) @ weights["W2"].T + weights["b2"]
    out = r * h + (1.0 - r) * z
    return (out / np.maximum(np.linalg.norm(out, axis=-1, keepdims=True), 1e-12)).astype(np.float32)


# --------------------------------------------------------------------------- #
# Metrics used during tuning
# --------------------------------------------------------------------------- #
def pair_recall_at_k(vectors: np.ndarray, pairs: pd.DataFrame, k: int = 10) -> float:
    """Consumer→shop Recall@k inside a set of mined pairs (queries: user, gallery: shop)."""
    src = pairs["source"].to_numpy()
    grp = pairs["group"].to_numpy()
    q, g = np.flatnonzero(src == "user"), np.flatnonzero(src == "shop")
    if len(q) == 0 or len(g) == 0:
        return 0.0
    sims = vectors[q] @ vectors[g].T
    top = np.argsort(-sims, axis=1)[:, :k]
    return float((grp[g][top] == grp[q][:, None]).any(axis=1).mean())


def category_precision_at_k(vectors: np.ndarray, cats: np.ndarray, text_protos: np.ndarray,
                            proto_keys: list[str], k: int = 10) -> float:
    """Text-alignment proxy: for each category prompt, precision of its top-k images."""
    sims = text_protos @ vectors.T
    top = np.argsort(-sims, axis=1)[:, :k]
    present = [i for i, key in enumerate(proto_keys) if (cats == key).any()]
    if not present:
        return 0.0
    return float(np.mean([(cats[top[i]] == proto_keys[i]).mean() for i in present]))


# --------------------------------------------------------------------------- #
# Training
# --------------------------------------------------------------------------- #
def train_adapter(
    vectors: np.ndarray,
    pairs: pd.DataFrame,
    text_protos: np.ndarray,
    proto_keys: list[str],
    cfg: FinetuneConfig,
    device: str | None = None,
) -> tuple[dict, dict]:
    """Train on ``vectors`` (raw CLIP, row-aligned with ``pairs``).

    Returns ``(weights, report)`` where ``weights`` holds numpy arrays
    ``W1, b1, W2, b2`` and the chosen ``ratio``.
    """
    torch = _torch()
    F = torch.nn.functional
    t0 = time.time()
    device = device or ("cuda" if torch.cuda.is_available() else "cpu")
    torch.manual_seed(cfg.seed)
    rng = np.random.default_rng(cfg.seed)

    pairs = pairs.reset_index(drop=True)
    cat_index = {k: i for i, k in enumerate(proto_keys)}
    cats = np.array(pairs["category_key"].map(cat_index).fillna(-1).astype(int), dtype=np.int64)
    tr_mask = ~pairs["is_val"].to_numpy()
    val = pairs[pairs["is_val"]].reset_index(drop=True)
    val_vecs = vectors[pairs["is_val"].to_numpy()]

    # Group → user rows / shop rows, train split only.
    tr = pairs[tr_mask]
    users = tr[tr["source"] == "user"].groupby("group").groups
    shops = tr[tr["source"] == "shop"].groupby("group").groups
    group_ids = np.array(sorted(set(users) & set(shops)))
    if len(group_ids) < 2:
        raise ValueError(f"need at least 2 consumer↔shop groups to train, found {len(group_ids)}")
    users = {g: np.asarray(users[g]) for g in group_ids}
    shops = {g: np.asarray(shops[g]) for g in group_ids}

    Z = torch.as_tensor(vectors, dtype=torch.float32, device=device)
    C = torch.as_tensor(cats, dtype=torch.long, device=device)
    T = torch.as_tensor(text_protos, dtype=torch.float32, device=device)

    model = build_adapter(vectors.shape[1], cfg.hidden).to(device)
    logit_scale = torch.nn.Parameter(torch.tensor(math.log(1 / 0.07), device=device))
    opt = torch.optim.AdamW(list(model.parameters()) + [logit_scale], lr=cfg.lr, weight_decay=cfg.weight_decay)
    batch = min(cfg.batch_groups, len(group_ids))
    steps_per_epoch = max(1, len(group_ids) // batch)
    sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, T_max=cfg.epochs * steps_per_epoch)

    history, best = [], (-1.0, None, -1)
    for epoch in range(1, cfg.epochs + 1):
        model.train()
        order = rng.permutation(group_ids)
        losses = []
        for s in range(steps_per_epoch):
            gs = order[s * batch:(s + 1) * batch]
            if len(gs) < 2:
                continue
            u_rows = np.array([rng.choice(users[g]) for g in gs])
            s_rows = np.array([rng.choice(shops[g]) for g in gs])
            zu = model(Z[u_rows], cfg.train_ratio)
            zs = model(Z[s_rows], cfg.train_ratio)
            scale = logit_scale.exp().clamp(max=100.0)
            logits = scale * zu @ zs.T
            labels = torch.arange(len(gs), device=device)
            loss_ret = 0.5 * (F.cross_entropy(logits, labels) + F.cross_entropy(logits.T, labels))

            both = torch.cat([zu, zs])
            cat_lbl = torch.cat([C[u_rows], C[s_rows]])
            ok = cat_lbl >= 0
            loss_txt = F.cross_entropy(100.0 * both[ok] @ T.T, cat_lbl[ok]) if ok.any() else both.sum() * 0
            loss = loss_ret + cfg.text_weight * loss_txt

            opt.zero_grad(set_to_none=True)
            loss.backward()
            opt.step()
            sched.step()
            losses.append(float(loss.detach()))

        weights = export_weights(model, cfg.train_ratio)
        val_r10 = pair_recall_at_k(apply_adapter_np(weights, val_vecs), val) if len(val) else float("nan")
        history.append({"epoch": epoch, "loss": round(float(np.mean(losses)), 4) if losses else None,
                        "val_recall@10": round(val_r10, 4)})
        log.info("finetune epoch %d/%d loss=%.4f val R@10=%.4f", epoch, cfg.epochs,
                 history[-1]["loss"] or float("nan"), val_r10)
        if val_r10 > best[0]:
            best = (val_r10, weights, epoch)

    weights = best[1] if best[1] is not None else export_weights(model, cfg.train_ratio)

    # Choose r on the tuning split: best retrieval while keeping text alignment.
    val_cats = val["category_key"].to_numpy()
    base_txt = category_precision_at_k(val_vecs, val_cats, text_protos, proto_keys)
    grid = []
    for r in cfg.ratio_grid:
        adapted = apply_adapter_np(weights, val_vecs, r) if len(val) else val_vecs
        grid.append({
            "ratio": r,
            "recall@1": round(pair_recall_at_k(adapted, val, k=1), 4) if len(val) else None,
            "recall@10": round(pair_recall_at_k(adapted, val), 4) if len(val) else None,
            "text_precision@10": round(category_precision_at_k(adapted, val_cats, text_protos, proto_keys), 4),
        })
    allowed = [g for g in grid if g["recall@10"] is not None and g["text_precision@10"] >= base_txt - cfg.max_text_drop]
    # Ties (common when R@10 saturates) go to the better R@1, then to the smaller r.
    chosen = max(allowed, key=lambda g: (g["recall@10"], g["recall@1"], -g["ratio"]))["ratio"] if allowed else 0.0
    if cfg.fixed_ratio is not None:
        chosen = float(cfg.fixed_ratio)
    weights["ratio"] = np.float32(chosen)

    report = {
        "method": "Residual CLIP-Adapter on frozen ViT-B/32 image embeddings",
        "loss": "symmetric InfoNCE (consumer↔shop) + λ·CE vs frozen CLIP text prototypes",
        "config": {k: (list(v) if isinstance(v, tuple) else v) for k, v in asdict(cfg).items()},
        "pairs": {
            "items": int(len(pairs)),
            "train_items": int(tr_mask.sum()),
            "val_items": int(len(val)),
            "train_groups": int(len(group_ids)),
            "val_groups": int(val["group"].nunique()) if len(val) else 0,
        },
        "device": device,
        "best_epoch": int(best[2]),
        "history": history,
        "ratio_search": grid,
        "val_text_precision@10_pretrained": round(base_txt, 4),
        "chosen_ratio": float(chosen),
        "train_seconds": round(time.time() - t0, 1),
    }
    return weights, report


def export_weights(model, ratio: float) -> dict:
    sd = {k: v.detach().cpu().numpy().astype(np.float32) for k, v in model.state_dict().items()}
    return {"W1": sd["fc1.weight"], "b1": sd["fc1.bias"], "W2": sd["fc2.weight"], "b2": sd["fc2.bias"],
            "ratio": np.float32(ratio)}


def save_adapter(weights: dict, path: Path, meta: dict | None = None) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez(path, W1=weights["W1"], b1=weights["b1"], W2=weights["W2"], b2=weights["b2"],
             ratio=np.float32(weights["ratio"]), version=np.int32(ADAPTER_VERSION),
             meta=np.array(json.dumps(meta or {})))


def load_adapter(path: Path) -> dict:
    with np.load(path, allow_pickle=False) as d:
        return {k: d[k] for k in ("W1", "b1", "W2", "b2", "ratio")}


def category_prompts(categories: dict[int, str]) -> tuple[list[str], list[str]]:
    """``(keys, prompts)`` for the frozen text prototypes."""
    from .config import slug

    names = [categories[i] for i in sorted(categories)]
    return [slug(n) for n in names], [f"a photo of a {n}, a type of clothing" for n in names]
