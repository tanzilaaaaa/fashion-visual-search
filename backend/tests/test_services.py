"""Unit tests for the services in isolation."""

from __future__ import annotations

import faiss
import numpy as np
import pytest

from app.core.config import BACKEND_DIR, Settings
from app.services.embedding import EmbeddingService, l2_normalise
from app.services.index import IndexService
from app.services.metadata import MetadataService, UnknownFilterValue
from app.services.query_parser import parse_query
from app.services.recommendation import CompatibilityMap
from app.services.search import attribute_match
from tests.conftest import FakeEncoder, catalogue


@pytest.mark.parametrize("query,cats,colours", [
    ("black oversized hoodie", {"long_sleeve_top"}, {"black"}),
    ("red casual summer dress", {"short_sleeve_dress", "long_sleeve_dress", "vest_dress", "sling_dress"},
     {"red"}),
    ("white summer dress", {"short_sleeve_dress", "long_sleeve_dress", "vest_dress", "sling_dress"},
     {"white"}),
    ("blue jeans", {"trousers"}, {"blue"}),
    ("denim jacket", {"short_sleeve_outwear", "long_sleeve_outwear"}, {"blue"}),
    ("black denim shorts", {"shorts"}, {"black"}),
    ("vest dress", {"vest_dress", "sling_dress"}, set()),
    ("grey tank top", {"vest"}, {"grey"}),
    ("long sleeve dress in navy blue", {"long_sleeve_dress"}, {"navy"}),
    ("something comfy", set(), set()),
])
def test_query_parser(query, cats, colours):
    p = parse_query(query)
    assert p.categories == cats
    assert p.colours == colours


def test_attribute_match_fraction():
    from app.services.query_parser import ParsedQuery

    meta = {"category_key": "skirt", "colour": "red"}
    assert attribute_match(meta, ParsedQuery({"skirt"}, {"red"})) == 1.0
    assert attribute_match(meta, ParsedQuery({"skirt"}, {"blue"})) == 0.5
    assert attribute_match(meta, ParsedQuery()) == 0.0


def test_embeddings_are_unit_norm_and_deterministic():
    svc = EmbeddingService(FakeEncoder())
    a, b = svc.encode_text("red dress"), svc.encode_text("red dress")
    np.testing.assert_allclose(a, b)
    assert abs(np.linalg.norm(a) - 1) < 1e-5
    assert abs(np.linalg.norm(l2_normalise(np.array([3.0, 4.0]))) - 1) < 1e-6


def test_zero_shot_picks_right_label():
    svc = EmbeddingService(FakeEncoder())
    label, p = svc.zero_shot(svc.encode_text("dress"), "category", ["t-shirt", "dress", "jeans"])
    assert label == "dress" and p > 0.5


def test_index_search_exact_k_and_filtered():
    _, vecs = catalogue()
    idx = faiss.IndexFlatIP(vecs.shape[1])
    idx.add(vecs)
    svc = IndexService(idx)
    scores, ids = svc.search(vecs[0], 5)
    assert len(ids) == 5 and ids[0] == 0 and scores[0] == pytest.approx(1.0, abs=1e-5)
    _, ids = svc.search(vecs[0], 5, allowed=np.array([10, 11, 12]))
    assert set(ids.tolist()) == {10, 11, 12}
    assert len(svc.search(vecs[0], 5, allowed=np.array([], dtype=np.int64))[1]) == 0
    np.testing.assert_allclose(svc.vector(3), vecs[3], atol=1e-6)


def test_index_handles_out_of_distribution_query():
    _, vecs = catalogue()
    idx = faiss.IndexFlatIP(vecs.shape[1])
    idx.add(vecs)
    _, ids = IndexService(idx).search(-np.ones(vecs.shape[1], np.float32), 4)
    assert len(ids) == 4


def test_metadata_positions_line_up():
    items, _ = catalogue()
    meta = MetadataService(items)
    for pos in (0, 7, 23):
        assert meta.get(pos)["position"] == pos
        assert meta.position_of(meta.get(pos)["item_id"]) == pos


def test_metadata_detects_drift():
    items, _ = catalogue()
    items[3]["position"] = 99
    with pytest.raises(ValueError, match="drift"):
        MetadataService(items)


def test_metadata_filters():
    meta = MetadataService(catalogue()[0])
    assert meta.matching_positions({}) is None
    assert len(meta.matching_positions({"colour": ["red"]})) == 12
    with pytest.raises(UnknownFilterValue):
        meta.matching_positions({"colour": ["chartreuse"]})
    with pytest.raises(UnknownFilterValue):
        meta.matching_positions({"material": ["silk"]})


def test_compatibility_map_covers_all_13_categories():
    compat = CompatibilityMap.load(BACKEND_DIR / "app/data/compatibility.json")
    all_cats = [c for cats in compat.groups.values() for c in cats]
    assert len(all_cats) == len(set(all_cats)) == 13
    for cat in all_cats:
        targets = compat.targets(cat)
        assert targets, cat
        assert all(compat.group_of(cat) != g for g, _ in targets)  # never duplicates the item


def test_settings_parse_comma_separated_origins(monkeypatch):
    monkeypatch.setenv("ALLOWED_ORIGINS", "https://a.vercel.app, http://localhost:5173")
    s = Settings(_env_file=None)
    assert s.allowed_origins == ["https://a.vercel.app", "http://localhost:5173"]
