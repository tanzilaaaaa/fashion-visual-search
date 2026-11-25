"""Small-memory runtime: compact metadata, quantised indexes, ONNX encoder plumbing."""

import io
import json
import subprocess
import sys
from pathlib import Path

import faiss
import numpy as np
import pytest
from PIL import Image

from app.api.routes.search import _decode
from app.core.config import Settings
from app.services.compact_metadata import CompactItems, save_compact
from app.services.metadata import MetadataService
from tests.conftest import catalogue

BACKEND = Path(__file__).resolve().parents[1]


def test_compact_metadata_round_trip_matches_json(tmp_path):
    items, _ = catalogue()
    save_compact(items, tmp_path / "metadata.npz")
    compact = CompactItems(tmp_path / "metadata.npz")
    assert len(compact) == len(items)
    for orig, got in zip(items, compact):
        for key in ("item_id", "category", "category_key", "colour", "source", "viewpoint", "occlusion",
                    "scale", "zoom_in", "pair_id", "style", "split", "image_id", "worn_with", "position"):
            assert got[key] == orig[key], key
        assert got["colour_confidence"] == pytest.approx(orig["colour_confidence"])
    assert compact[-1]["item_id"] == items[-1]["item_id"]
    with pytest.raises(IndexError):
        compact[len(items)]


def test_metadata_service_behaves_the_same_on_compact_storage(tmp_path):
    items, _ = catalogue()
    (tmp_path / "metadata.json").write_text(json.dumps({"version": 1, "items": items}))
    from_json = MetadataService.load(tmp_path / "metadata.json")
    save_compact(items, tmp_path / "metadata.npz")
    from_npz = MetadataService.load(tmp_path / "metadata.json")  # .npz next to it wins
    assert isinstance(from_npz.items, CompactItems)
    assert from_npz.vocabulary() == from_json.vocabulary()
    assert from_npz.category_labels == from_json.category_labels
    assert from_npz.by_item_id == from_json.by_item_id
    f = {"category": ["trousers"], "colour": ["red"]}
    assert from_npz.matching_positions(f).tolist() == from_json.matching_positions(f).tolist()
    assert from_npz.get(9) == from_json.get(9)


def test_compact_artifacts_script_quantises_indexes_and_keeps_answers(artifacts):
    _, vecs = catalogue()
    flat_answers = faiss.read_index(str(artifacts / "index.faiss")).search(vecs[:5], 3)[1]
    out = subprocess.run(
        [sys.executable, str(BACKEND / "scripts" / "compact_artifacts.py"), "--artifacts", str(artifacts), "--check"],
        capture_output=True, text=True, cwd=BACKEND, check=True,
    )
    report = json.loads(out.stdout)
    assert report["index.faiss"]["top1_same"] == 1.0
    idx = faiss.read_index(str(artifacts / "index.faiss"))
    assert isinstance(idx, faiss.IndexScalarQuantizer)
    assert idx.search(vecs[:5], 3)[1][:, 0].tolist() == flat_answers[:, 0].tolist()
    assert (artifacts / "metadata.npz").exists() and not (artifacts / "metadata.json").exists()


def test_container_uses_onnx_when_an_exported_model_is_present(tmp_path, monkeypatch):
    from app import container

    made = {}

    class FakeOnnx:
        def __init__(self, model_dir, threads=1):
            made["dir"] = model_dir

    monkeypatch.setattr("app.services.onnx_encoder.OnnxClipEncoder", FakeOnnx)
    settings = Settings(_env_file=None, artifacts_dir=tmp_path)
    (tmp_path / "onnx").mkdir()
    (tmp_path / "onnx" / "config.json").write_text("{}")
    assert isinstance(container._make_encoder(settings), FakeOnnx)
    assert made["dir"] == tmp_path / "onnx"


def test_large_jpeg_is_decoded_at_reduced_size():
    buf = io.BytesIO()
    Image.new("RGB", (3000, 4000), (200, 30, 40)).save(buf, "JPEG")
    img = _decode(buf.getvalue())
    assert img.mode == "RGB" and min(img.size) == 448
    assert img.size[1] > img.size[0]  # aspect ratio kept


def test_tokenizer_matches_open_clip():
    open_clip = pytest.importorskip("open_clip")
    from app.services.clip_tokenizer import ClipTokenizer

    texts = ["a red casual summer dress", "Blue DENIM jacket!", "  café   crème — 50% off  ", "x" * 400, ""]
    ours = ClipTokenizer()(texts)
    ref = open_clip.get_tokenizer("ViT-B-32-quickgelu")(texts).numpy()
    np.testing.assert_array_equal(ours, ref)


def test_preprocess_matches_open_clip():
    open_clip = pytest.importorskip("open_clip")
    from app.services.onnx_encoder import preprocess

    _, _, ref = open_clip.create_model_and_transforms("ViT-B-32-quickgelu", pretrained=None)
    for size in ((300, 400), (640, 480), (224, 224), (1000, 333)):
        img = Image.fromarray(np.random.default_rng(sum(size)).integers(0, 255, (*size[::-1], 3), dtype=np.uint8))
        np.testing.assert_allclose(preprocess(img), ref(img).numpy(), atol=1e-5)


def test_prototypes_round_trip_and_skip_recompute(tmp_path):
    from app.services.embedding import EmbeddingService
    from tests.conftest import FakeEncoder

    enc = FakeEncoder()
    svc = EmbeddingService(enc)
    labels = ["red", "blue"]
    first = svc.prototypes("colour", labels)
    svc.save_prototypes(tmp_path / "prototypes.npz")

    enc2 = FakeEncoder()
    svc2 = EmbeddingService(enc2)
    assert svc2.load_prototypes(tmp_path / "prototypes.npz") == ["colour"]
    np.testing.assert_allclose(svc2.prototypes("colour", labels), first)
    assert enc2.text_calls == 0  # served from the file, no encoding
    svc2.prototypes("colour", ["red", "green"])  # different labels: recomputed, never stale
    assert enc2.text_calls > 0
