"""End-to-end offline build: DeepFashion2 → crops → CLIP → FAISS → evaluation.

Usage::

    python -m fvs_ml.pipeline --dataset-root /kaggle/input/deepfashion2-original-with-dataframes \
        --output-dir artifacts --target-items 50000

    # quick dev index (PRD §6.1)
    python -m fvs_ml.pipeline --dataset-root ~/data/df2 --output-dir ../backend/artifacts \
        --target-items 3000 --max-images-per-split 4000
"""

from __future__ import annotations

import argparse
import json
import logging
import time
from pathlib import Path

import numpy as np

from . import evaluate as ev
from .annotations import load_items
from .attributes import colour_prototypes, tag_colours
from .build_index import write_artifacts, write_text_index
from .clean import clean_items
from .config import CATEGORIES, PipelineConfig
from .embed import encode_items, encode_texts, load_clip
from .finetune import (
    FinetuneConfig,
    apply_adapter_np,
    category_prompts,
    mine_pairs,
    save_adapter,
    train_adapter,
)
from .subset import holdout_eval_slice, sample_working_subset

log = logging.getLogger("fvs_ml")
DEFAULT_COMPAT = Path(__file__).resolve().parents[2] / "backend" / "app" / "data" / "compatibility.json"


def run(
    cfg: PipelineConfig,
    max_images_per_split: int | None,
    compat_path: Path,
    skip_eval: bool,
    finetune: bool = False,
    ft_cfg: FinetuneConfig | None = None,
) -> dict:
    t0 = time.time()
    cfg.work_dir.mkdir(parents=True, exist_ok=True)
    cfg.output_dir.mkdir(parents=True, exist_ok=True)
    for stale in ("adapter.npz", "text_index.faiss"):  # never ship artifacts from an older build
        (cfg.output_dir / stale).unlink(missing_ok=True)

    # 1–2. Annotations → clean item table (cached between runs).
    items_cache = cfg.work_dir / f"items_{max_images_per_split or 'all'}.parquet"
    if items_cache.exists():
        import pandas as pd
        items = pd.read_parquet(items_cache)
        log.info("loaded %d cached item rows", len(items))
    else:
        items = load_items(cfg.dataset_root, cfg.splits, max_images_per_split, workers=cfg.io_workers)
        items.to_parquet(items_cache)
        log.info("parsed %d item rows", len(items))
    items, clean_report = clean_items(items, cfg.min_box_side)
    log.info("cleaning: %s", clean_report)

    # 3–4. Held-out evaluation slice, then a balanced working subset from the rest.
    pool, eval_slice = holdout_eval_slice(
        items, cfg.eval_fraction_of_validation, cfg.eval_max_images, cfg.seed
    )
    subset = sample_working_subset(pool, cfg.target_items, cfg.seed)
    log.info("subset=%d items, eval slice=%d items", len(subset), len(eval_slice))

    # 5–6. CLIP image embeddings (+ thumbnails) for the catalogue.
    model, preprocess, tokenizer, device = load_clip(cfg.model_name, cfg.pretrained)
    log.info("CLIP %s/%s on %s", cfg.model_name, cfg.pretrained, device)
    vectors, ok = encode_items(
        subset, cfg.dataset_root, model, preprocess, device, cfg.work_dir, cfg.images_dir,
        cfg.batch_size, cfg.num_workers, cfg.crop_padding, cfg.thumb_size, tag="catalogue",
    )
    subset, vectors = subset[ok].reset_index(drop=True), vectors[ok]

    def text_encoder(texts: list[str]) -> np.ndarray:
        return encode_texts(texts, model, tokenizer, device)

    # 6b. Optional fine-tuning: residual adapter on frozen CLIP (see finetune.py).
    adapter, ft_report = None, None
    if finetune:
        ft_cfg = ft_cfg or FinetuneConfig(seed=cfg.seed)
        adapter, ft_report = _finetune(cfg, ft_cfg, pool, model, preprocess, device, text_encoder)

    def serve(v: np.ndarray) -> np.ndarray:
        return apply_adapter_np(adapter, v) if adapter is not None else v

    # 7. Zero-shot colour attribute (always from raw CLIP vectors: text-aligned by construction).
    colours, conf = tag_colours(vectors, colour_prototypes(text_encoder))
    subset = subset.assign(colour=colours, colour_confidence=conf)

    # 8. Persist artifacts. The index stores the vectors the API will search with.
    # Dual index: photos search the adapted space, text searches the pretrained space.
    text_index_info = write_text_index(vectors, cfg.output_dir) if adapter is not None else None
    manifest = write_artifacts(subset, serve(vectors), cfg.output_dir, {
        "text_index": text_index_info,
        "adapter": (
            {"file": "adapter.npz", "ratio": float(adapter["ratio"]), "hidden": int(adapter["W1"].shape[0])}
            if adapter is not None else None
        ),
        "model_name": cfg.model_name,
        "pretrained": cfg.pretrained,
        "seed": cfg.seed,
        "target_items": cfg.target_items,
        "dataset": "DeepFashion2",
        "splits": list(cfg.splits),
        "cleaning": clean_report,
        "unreadable_items_dropped": int((~ok).sum()),
    })
    # Remove thumbnails of items dropped as unreadable so images/ matches the index.
    keep = set(subset["item_id"])
    for p in cfg.images_dir.glob("*.webp"):
        if p.stem not in keep:
            p.unlink()

    report: dict = {"manifest": manifest}
    if not skip_eval:
        # 9–10. Held-out evaluation.
        ev_vecs, ev_ok = encode_items(
            eval_slice, cfg.dataset_root, model, preprocess, device, cfg.work_dir, None,
            cfg.batch_size, cfg.num_workers, cfg.crop_padding, cfg.thumb_size, tag="eval",
        )
        eval_slice, ev_vecs = eval_slice[ev_ok].reset_index(drop=True), ev_vecs[ev_ok]
        c2s = ev.consumer_to_shop(eval_slice, serve(ev_vecs), cfg.seed)
        # Text queries are served from the pretrained-space text index (see write_text_index).
        t2i = ev.text_to_image(subset, vectors, text_encoder, seed=cfg.seed)
        report = {
            "dataset": "DeepFashion2",
            "model": f"{cfg.model_name} ({cfg.pretrained})" + (" + fine-tuned adapter" if adapter is not None else ""),
            "catalogue_items": int(len(subset)),
            "eval_items": int(len(eval_slice)),
            "consumer_to_shop": c2s,
            "text_to_image": t2i,
            "complete_the_look": ev.outfit_cooccurrence(
                eval_slice, serve(ev_vecs), ev.load_compatibility(compat_path), seed=cfg.seed
            ),
            "footprint": ev.footprint(cfg.output_dir),
            "build_seconds": round(time.time() - t0, 1),
        }
        if finetune:
            report["finetune"] = ft_report
        if adapter is not None:
            # Ablation on the same held-out slice: frozen CLIP vs CLIP + adapter.
            pre_c2s = ev.consumer_to_shop(eval_slice, ev_vecs, cfg.seed)
            ft_t2i = ev.text_to_image(subset, serve(vectors), text_encoder, seed=cfg.seed)
            report["variants"] = {
                "pretrained": {"consumer_to_shop": pre_c2s.get("clip"), "text_to_image": t2i["clip"]},
                "finetuned": {"consumer_to_shop": c2s.get("clip"), "text_to_image": ft_t2i["clip"]},
                "served": {"consumer_to_shop": c2s.get("clip"), "text_to_image": t2i["clip"],
                           "note": "dual index: photos → fine-tuned space, text → pretrained space"},
            }
        with open(cfg.output_dir / "evaluation.json", "w", encoding="utf-8") as fh:
            json.dump(report, fh, indent=2)
        log.info("evaluation: %s", json.dumps(report["consumer_to_shop"]))
    log.info("done in %.1fs → %s", time.time() - t0, cfg.output_dir)
    return report


def _finetune(cfg, ft_cfg, pool, model, preprocess, device, text_encoder):
    """Mine pairs → embed (cached) → train → save. Never aborts the build: on failure
    the catalogue is indexed with pretrained CLIP and the reason is reported."""
    pairs = mine_pairs(pool, ft_cfg.max_items, ft_cfg.val_fraction, ft_cfg.seed)
    log.info("finetune: %d pair items (%d val)", len(pairs), int(pairs["is_val"].sum()) if len(pairs) else 0)
    if len(pairs) == 0:
        return None, {"skipped": "no consumer↔shop pairs in the train split"}
    pvecs, pok = encode_items(
        pairs, cfg.dataset_root, model, preprocess, device, cfg.work_dir, None,
        cfg.batch_size, cfg.num_workers, cfg.crop_padding, cfg.thumb_size, tag="finetune",
    )
    pairs, pvecs = pairs[pok].reset_index(drop=True), pvecs[pok]
    keys, prompts = category_prompts(CATEGORIES)
    try:
        weights, report = train_adapter(pvecs, pairs, text_encoder(prompts), keys, ft_cfg, device=device)
    except ValueError as exc:
        log.warning("finetune skipped: %s", exc)
        return None, {"skipped": str(exc)}
    if float(weights["ratio"]) == 0.0:
        log.info("finetune: r=0 chosen on the tuning split; serving pretrained CLIP")
        return None, report
    save_adapter(weights, cfg.output_dir / "adapter.npz", report)
    return weights, report


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--dataset-root", type=Path, required=True)
    p.add_argument("--output-dir", type=Path, required=True)
    p.add_argument("--work-dir", type=Path, default=Path("work"))
    p.add_argument("--target-items", type=int, default=50_000)
    p.add_argument("--max-images-per-split", type=int, default=None)
    p.add_argument("--batch-size", type=int, default=256)
    p.add_argument("--num-workers", type=int, default=2)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--compat-path", type=Path, default=DEFAULT_COMPAT)
    p.add_argument("--skip-eval", action="store_true")
    p.add_argument("--finetune", action="store_true", help="train a residual CLIP-Adapter on consumer↔shop pairs")
    p.add_argument("--ft-epochs", type=int, default=40)
    p.add_argument("--ft-max-items", type=int, default=60_000)
    p.add_argument("--ft-ratio", type=float, default=None, help="force the residual ratio r (default: tuned)")
    a = p.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    cfg = PipelineConfig(
        dataset_root=a.dataset_root, output_dir=a.output_dir, work_dir=a.work_dir,
        target_items=a.target_items, batch_size=a.batch_size, num_workers=a.num_workers, seed=a.seed,
    )
    ft_cfg = FinetuneConfig(epochs=a.ft_epochs, max_items=a.ft_max_items, fixed_ratio=a.ft_ratio, seed=a.seed)
    run(cfg, a.max_images_per_split, a.compat_path, a.skip_eval, finetune=a.finetune, ft_cfg=ft_cfg)


if __name__ == "__main__":
    main()
