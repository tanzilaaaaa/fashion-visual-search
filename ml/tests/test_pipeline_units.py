"""Unit tests for the CLIP-free parts of the offline pipeline."""

import json

import numpy as np
import pandas as pd
import pytest
from PIL import Image

from fvs_ml.annotations import discover_splits, load_items, map_csv_columns
from fvs_ml.attributes import tag_colours
from fvs_ml.build_index import build_flat_ip_index, write_artifacts
from fvs_ml.clean import clean_items
from fvs_ml.crop import crop_garment, padded_box
from fvs_ml.evaluate import consumer_to_shop, keyword_categories, recall_at_k
from fvs_ml.subset import balanced_quotas, holdout_eval_slice, sample_working_subset


@pytest.fixture()
def df2_root(tmp_path):
    """A tiny DeepFashion2-shaped tree with colliding file names across splits."""
    for split, colour in (("train", (255, 0, 0)), ("validation", (0, 0, 255))):
        (tmp_path / split / "image").mkdir(parents=True)
        (tmp_path / split / "annos").mkdir(parents=True)
        for i in range(1, 4):
            name = f"{i:06d}"
            Image.new("RGB", (200, 300), colour).save(tmp_path / split / "image" / f"{name}.jpg")
            anno = {
                "source": "shop" if i == 1 else "user",
                "pair_id": 7,
                "item1": {"category_id": 1, "category_name": "short sleeve top",
                          "bounding_box": [10, 10, 150, 200], "style": 1,
                          "scale": 2, "occlusion": 1, "viewpoint": 2, "zoom_in": 1},
                "item2": {"category_id": 8, "category_name": "trousers",
                          "bounding_box": [20, 150, 180, 290], "style": 0,
                          "scale": 2, "occlusion": 2, "viewpoint": 2, "zoom_in": 1},
            }
            (tmp_path / split / "annos" / f"{name}.json").write_text(json.dumps(anno))
    return tmp_path


def test_discover_and_load_keep_splits_apart(df2_root):
    layout = discover_splits(df2_root)
    assert set(layout) == {"train", "validation"}
    df = load_items(df2_root, workers=1)
    assert len(df) == 12
    assert df["item_id"].is_unique
    # Same basename, different split → different paths (the notebook's basename bug).
    rel = df[df["image_id"] == "000001"]["image_relpath"].unique()
    assert set(rel) == {"train/image/000001.jpg", "validation/image/000001.jpg"}


def test_clean_drops_tiny_and_duplicate_boxes():
    df = pd.DataFrame({
        "item_id": ["a", "a", "b", "c"], "image_relpath": ["x"] * 4, "category_id": [1, 1, 1, 99],
        "bbox_x1": [0, 0, 0, 0], "bbox_y1": [0, 0, 0, 0],
        "bbox_x2": [100, 100, 5, 100], "bbox_y2": [100, 100, 5, 100],
    })
    out, report = clean_items(df, min_box_side=32)
    assert list(out["item_id"]) == ["a"]
    assert report["duplicates_removed"] == 1
    assert report["invalid_or_tiny_bbox_removed"] == 1
    assert report["unknown_category_removed"] == 1


def test_balanced_quotas_redistribute_rare_classes():
    q = balanced_quotas({"rare": 10, "mid": 1000, "big": 5000}, target=900)
    assert q["rare"] == 10
    assert sum(q.values()) == 900
    assert abs(q["mid"] - q["big"]) <= 1


def test_sampling_is_reproducible():
    pool = pd.DataFrame({"item_id": range(300), "category_key": ["a"] * 200 + ["b"] * 100})
    s1 = sample_working_subset(pool, 120, seed=1)
    s2 = sample_working_subset(pool, 120, seed=1)
    assert s1["item_id"].tolist() == s2["item_id"].tolist()
    assert s1["category_key"].value_counts().to_dict() == {"a": 60, "b": 60}


def test_holdout_slice_is_disjoint_and_pair_grouped():
    df = pd.DataFrame({
        "item_id": [f"i{i}" for i in range(40)],
        "split": ["train"] * 20 + ["validation"] * 20,
        "image_id": [f"{i:06d}" for i in range(40)],
        "pair_id": [i // 2 for i in range(40)],
    })
    pool, held = holdout_eval_slice(df, fraction=0.5, max_images=100, seed=0)
    assert set(pool["item_id"]).isdisjoint(held["item_id"])
    assert (held["split"] == "validation").all()
    for pair in held["pair_id"].unique():
        assert not (pool["pair_id"] == pair).any() or (pool[pool["pair_id"] == pair]["split"] == "train").all()


def test_padded_box_clips_to_image():
    assert padded_box(0, 0, 100, 100, width=110, height=105, padding=0.1) == (0, 0, 110, 105)


def test_crop_garment_returns_rgb(df2_root):
    img = crop_garment(df2_root / "train/image/000001.jpg", (10, 10, 150, 200), 0.0)
    assert img.mode == "RGB" and img.size == (140, 190)
    r, g, b = img.getpixel((5, 5))
    assert r > 200 and b < 50


def test_flat_ip_index_is_cosine():
    rng = np.random.default_rng(0)
    v = rng.normal(size=(50, 16)).astype(np.float32) * 5  # not unit norm on purpose
    index = build_flat_ip_index(v)
    scores, ids = index.search(v[:3] / np.linalg.norm(v[:3], axis=1, keepdims=True), 1)
    assert ids[:, 0].tolist() == [0, 1, 2]
    np.testing.assert_allclose(scores[:, 0], 1.0, atol=1e-5)


def test_write_artifacts_alignment(tmp_path):
    items = pd.DataFrame({
        "item_id": ["a", "b"], "category": ["vest", "skirt"], "category_key": ["vest", "skirt"],
        "colour": ["red", "blue"], "colour_confidence": [0.9, 0.8], "source": ["shop", "user"],
        "viewpoint": [2, 3], "occlusion": [1, 1], "scale": [2, 2], "zoom_in": [1, 1],
        "pair_id": [1, 1], "style": [1, 1], "split": ["train", "train"], "image_id": ["1", "1"],
    })
    write_artifacts(items, np.eye(2, 8, dtype=np.float32), tmp_path)
    meta = json.loads((tmp_path / "metadata.json").read_text())["items"]
    assert [m["position"] for m in meta] == [0, 1]
    assert meta[0]["worn_with"] == ["b"]
    with pytest.raises(ValueError):
        write_artifacts(items, np.eye(3, 8, dtype=np.float32), tmp_path)


def test_colour_tagging_confidence_threshold():
    protos = np.eye(13, 4 + 9, dtype=np.float32)
    labels, conf = tag_colours(np.stack([protos[0], np.zeros(13, np.float32)]), protos)
    assert labels[0] == "black" and conf[0] > 0.9
    assert labels[1] == "multicolour"


def test_recall_and_consumer_to_shop():
    assert recall_at_k(np.array([[False, True], [False, False]]), ks=(1, 2)) == {
        "recall@1": 0.0, "recall@2": 0.5}
    items = pd.DataFrame({
        "source": ["shop", "shop", "user"], "style": [1, 1, 1], "pair_id": [1, 2, 1],
        "category_key": ["vest"] * 3,
    })
    v = np.array([[1, 0], [0, 1], [0.9, 0.1]], dtype=np.float32)
    out = consumer_to_shop(items, v)
    assert out["queries"] == 1 and out["clip"]["recall@1"] == 1.0


def test_keyword_baseline_misses_synonyms():
    cats = ["trousers", "short_sleeve_top"]
    assert keyword_categories("blue jeans", cats) == []
    assert keyword_categories("short sleeve top", cats) == ["short_sleeve_top"]


def test_csv_mapping_is_exact():
    m = map_csv_columns(["pair_id", "category_id", "image_name", "bounding_box"])
    assert "item_index" not in m  # 'id' substrings must not leak into other fields
    assert m["image_id"] == "image_name" and m["bbox"] == "bounding_box"
