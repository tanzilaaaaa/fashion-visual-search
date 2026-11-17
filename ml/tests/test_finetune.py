"""Fine-tuning: pair mining hygiene, training signal, and numpy/torch parity."""

import numpy as np
import pandas as pd
import pytest

from fvs_ml.finetune import (
    FinetuneConfig,
    apply_adapter_np,
    build_adapter,
    export_weights,
    load_adapter,
    mine_pairs,
    pair_recall_at_k,
    save_adapter,
    train_adapter,
)


def _items(n_pairs=40, split="train"):
    rows = []
    for p in range(n_pairs):
        for src in ("shop", "user", "user"):
            rows.append({"split": split, "pair_id": p, "style": 1, "source": src,
                         "category_key": ["skirt", "trousers"][p % 2]})
        rows.append({"split": split, "pair_id": p, "style": 0, "source": "user", "category_key": "skirt"})
    return pd.DataFrame(rows)


def test_mine_pairs_keeps_only_complete_train_groups_and_holds_out_whole_pairs():
    items = pd.concat([
        _items(30),
        _items(5, split="validation"),
        pd.DataFrame([{"split": "train", "pair_id": 999, "style": 1, "source": "user", "category_key": "skirt"}]),
    ], ignore_index=True)
    pairs = mine_pairs(items, max_items=10_000, val_fraction=0.2, seed=0)
    assert set(pairs["split"]) == {"train"}
    assert (pairs["style"] > 0).all()
    assert 999 not in set(pairs["pair_id"])                     # user-only group dropped
    for _, g in pairs.groupby("group"):
        assert {"user", "shop"} <= set(g["source"])
    val_pairs, tr_pairs = set(pairs[pairs.is_val].pair_id), set(pairs[~pairs.is_val].pair_id)
    assert val_pairs and not (val_pairs & tr_pairs)


def test_mine_pairs_respects_item_cap():
    pairs = mine_pairs(_items(50), max_items=30, val_fraction=0.1, seed=0)
    assert 30 <= len(pairs) <= 33


def _clustered(pairs, dim=32, noise=0.9, seed=0):
    """Consumer and shop views of a group share a direction plus heavy domain noise."""
    rng = np.random.default_rng(seed)
    centres = rng.normal(size=(pairs["group"].max() + 1, dim))
    domain = {"user": rng.normal(size=dim) * 2.0, "shop": rng.normal(size=dim) * 2.0}
    v = np.stack([centres[g] + domain[s] + noise * rng.normal(size=dim)
                  for g, s in zip(pairs["group"], pairs["source"])])
    return (v / np.linalg.norm(v, axis=1, keepdims=True)).astype(np.float32)


def test_training_improves_recall_and_reports_history():
    pairs = mine_pairs(_items(120), max_items=10_000, val_fraction=0.25, seed=1)
    vecs = _clustered(pairs)
    protos = np.eye(32, dtype=np.float32)[:2]
    cfg = FinetuneConfig(hidden=64, epochs=25, batch_groups=64, lr=5e-3, ratio_grid=(0.0, 0.5, 0.8),
                         max_text_drop=1.0, seed=0)
    weights, report = train_adapter(vecs, pairs, protos, ["skirt", "trousers"], cfg, device="cpu")
    val = pairs[pairs.is_val].reset_index(drop=True)
    before = pair_recall_at_k(vecs[pairs.is_val.to_numpy()], val)
    after = pair_recall_at_k(apply_adapter_np(weights, vecs[pairs.is_val.to_numpy()]), val)
    assert after > before
    assert len(report["history"]) == 25 and report["chosen_ratio"] > 0
    assert report["pairs"]["val_items"] == len(val)


def test_numpy_forward_matches_torch(tmp_path):
    torch = pytest.importorskip("torch")
    model = build_adapter(16, 8)
    torch.nn.init.normal_(model.fc2.weight)                       # break the identity init
    z = torch.nn.functional.normalize(torch.randn(5, 16), dim=-1)
    ref = model(z, 0.4).detach().numpy()
    w = export_weights(model, 0.4)
    save_adapter(w, tmp_path / "a.npz", {"note": "test"})
    out = apply_adapter_np(load_adapter(tmp_path / "a.npz"), z.numpy())
    np.testing.assert_allclose(out, ref, atol=1e-5)
    np.testing.assert_allclose(np.linalg.norm(out, axis=1), 1.0, atol=1e-5)


def test_zero_initialised_adapter_is_identity():
    model = build_adapter(16, 8)
    z = np.random.default_rng(0).normal(size=(4, 16)).astype(np.float32)
    z /= np.linalg.norm(z, axis=1, keepdims=True)
    np.testing.assert_allclose(apply_adapter_np(export_weights(model, 0.6), z), z, atol=1e-6)
