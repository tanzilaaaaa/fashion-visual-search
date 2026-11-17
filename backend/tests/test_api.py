"""Integration tests: every endpoint end to end through FastAPI's TestClient."""

from __future__ import annotations

from app.api.limiter import limiter
from tests.conftest import png_bytes


# --------------------------------------------------------------------- health
def test_health_reports_model_and_index(client):
    body = client.get("/health").json()
    assert body["status"] == "ok"
    assert body["model_loaded"] and body["index_loaded"]
    assert body["item_count"] == 24
    assert "index.faiss" not in str(body)  # never leak paths


def test_degraded_when_artifacts_missing(make_client, tmp_path):
    c = make_client(artifacts_dir=tmp_path / "nope")
    body = c.get("/health").json()
    assert body["status"] == "degraded" and not body["index_loaded"]
    assert str(tmp_path) not in str(body)
    r = c.post("/search/text", json={"query": "red dress"})
    assert r.status_code == 503 and r.json()["error"]["code"] == "not_ready"


# ---------------------------------------------------------------- text search
def test_text_search_ranks_matching_items_first(client):
    r = client.post("/search/text", json={"query": "red dress", "top_k": 3})
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 3
    assert all(it["category_key"] == "long_sleeve_dress" and it["colour"] == "red" for it in body["results"])
    scores = [it["score"] for it in body["results"]]
    assert scores == sorted(scores, reverse=True)
    assert body["detected"] == {"categories": sorted(
        ["short_sleeve_dress", "long_sleeve_dress", "vest_dress", "sling_dress"]), "colours": ["red"]}
    assert body["ranking"]["attribute_signal_used"] is True
    first = body["results"][0]
    assert first["image_url"] == f"/images/{first['item_id']}"
    assert set(first) >= {"item_id", "image_url", "category", "score", "similarity"}


def test_default_top_k_applied(client):
    assert client.post("/search/text", json={"query": "jacket"}).json()["total"] == 5


def test_weights_override_and_pure_similarity(client):
    body = client.post("/search/text", json={"query": "red dress", "beta": 0, "alpha": 1}).json()
    assert body["ranking"]["attribute_signal_used"] is False
    assert all(it["score"] == it["similarity"] for it in body["results"])


def test_empty_query_is_400_not_500(client):
    for q in ("", "    "):
        r = client.post("/search/text", json={"query": q})
        assert r.status_code == 400
        assert r.json()["error"]["code"] == "empty_query"


def test_query_too_long(client):
    r = client.post("/search/text", json={"query": "a" * 500})
    assert r.status_code == 400 and r.json()["error"]["code"] == "query_too_long"


def test_validation_errors_are_422(client):
    assert client.post("/search/text", json={"query": "x", "top_k": "abc"}).status_code == 422
    assert client.post("/search/text", json={"query": "x", "top_k": 0}).status_code == 422
    assert client.post("/search/text", json={"query": "x", "colour": "red"}).status_code == 422
    assert client.post("/search/text", json={}).status_code == 422


def test_category_filter_restricts_and_is_echoed(client):
    body = client.post("/search/text", json={
        "query": "red dress", "top_k": 10, "filters": {"category": ["trousers"]},
    }).json()
    assert body["applied_filters"] == {"category": ["trousers"]}
    assert body["total"] == 6
    assert {it["category_key"] for it in body["results"]} == {"trousers"}


def test_filters_combine_with_and(client):
    body = client.post("/search/text", json={
        "query": "anything", "top_k": 24, "filters": {"category": ["trousers"], "colour": ["blue"]},
    }).json()
    assert body["total"] == 3
    assert all(it["colour"] == "blue" and it["category_key"] == "trousers" for it in body["results"])


def test_unsupported_filter_value_rejected(client):
    r = client.post("/search/text", json={"query": "dress", "filters": {"category": ["hat"]}})
    assert r.status_code == 400 and r.json()["error"]["code"] == "unsupported_filter"


def test_text_cache_avoids_reencoding(make_client):
    from tests.conftest import FakeEncoder

    enc = FakeEncoder()
    c = make_client(encoder=enc)
    c.post("/search/text", json={"query": "Blue jeans"})
    calls = enc.text_calls
    c.post("/search/text", json={"query": "blue   JEANS"})
    assert enc.text_calls == calls


# --------------------------------------------------------------- image search
def test_image_search_returns_visual_matches(client):
    r = client.post("/search/image", files={"file": ("q.png", png_bytes((230, 5, 5)), "image/png")},
                    data={"top_k": "3"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["mode"] == "image" and body["total"] == 3
    assert body["results"][0]["colour"] == "red"
    assert "category" in body["inferred"] and "confidence" in body["inferred"]["category"]


def test_image_search_with_filters(client):
    r = client.post("/search/image", files={"file": ("q.jpg", png_bytes(fmt="JPEG"), "image/jpeg")},
                    data={"filters": '{"category": ["trousers"]}'})
    assert r.status_code == 200
    assert {it["category_key"] for it in r.json()["results"]} == {"trousers"}


def test_image_unsupported_type_400(client):
    r = client.post("/search/image", files={"file": ("q.gif", b"GIF89a....", "image/gif")})
    assert r.status_code == 400 and r.json()["error"]["code"] == "unsupported_type"


def test_image_spoofed_content_type_400(client):
    r = client.post("/search/image", files={"file": ("q.png", b"not really an image", "image/png")})
    assert r.status_code == 400 and r.json()["error"]["code"] == "unsupported_type"


def test_image_oversized_413(client):
    big = b"\x89PNG\r\n\x1a\n" + b"0" * (1024 * 1024 + 10)  # limit is 1 MB in tests
    r = client.post("/search/image", files={"file": ("big.png", big, "image/png")})
    assert r.status_code == 413 and r.json()["error"]["code"] == "payload_too_large"


def test_image_corrupt_400(client):
    r = client.post("/search/image", files={"file": ("bad.png", b"\x89PNG\r\n\x1a\nbroken", "image/png")})
    assert r.status_code == 400 and r.json()["error"]["code"] == "invalid_image"


def test_image_missing_file_and_bad_filters(client):
    assert client.post("/search/image", data={"top_k": "3"}).json()["error"]["code"] == "missing_file"
    r = client.post("/search/image", files={"file": ("q.png", png_bytes(), "image/png")},
                    data={"filters": "{not json"})
    assert r.status_code == 400 and r.json()["error"]["code"] == "malformed_filters"


# -------------------------------------------------------------------- items
def test_item_detail_and_404(client):
    r = client.get("/items/train-000000-1")
    assert r.status_code == 200
    assert r.json()["worn_with"] == ["train-000009-1"]
    assert client.get("/items/does-not-exist").status_code == 404
    assert client.get("/items/bad%20id!").status_code == 422


def test_find_similar_excludes_source(client):
    body = client.get("/items/train-000000-1/similar", params={"top_k": 5}).json()
    ids = [it["item_id"] for it in body["results"]]
    assert "train-000000-1" not in ids and len(ids) == 5
    assert body["results"][0]["category_key"] == "short_sleeve_top"
    assert body["results"][0]["reason"].startswith("Similar visual style")


def test_complete_the_look_uses_compatible_categories(client):
    body = client.get("/items/train-000000-1/recommendations", params={"per_group": 3}).json()
    groups = {g["group"]: g for g in body["groups"]}
    assert set(groups) == {"bottoms", "outerwear"}  # a top pairs with bottoms + outerwear
    assert {it["category_key"] for it in groups["bottoms"]["items"]} <= {"trousers", "shorts", "skirt"}
    assert all(it["reason"] for g in body["groups"] for it in g["items"])
    # The trousers photographed with this top get the worn-together reason.
    worn = [it for it in groups["bottoms"]["items"] if it["item_id"] == "train-000009-1"]
    assert worn and "same photo" in worn[0]["reason"]


def test_dress_pairs_only_with_outerwear(client):
    body = client.get("/items/train-000012-1/recommendations").json()
    assert [g["group"] for g in body["groups"]] == ["outerwear"]


def test_recommendations_unknown_item(client):
    assert client.get("/items/nope-1/recommendations").status_code == 404
    assert client.get("/items/nope-1/similar").status_code == 404


# ------------------------------------------------------------- meta endpoints
def test_filters_vocabulary(client):
    fields = client.get("/filters").json()["fields"]
    assert set(fields) == {"category", "colour", "source", "viewpoint"}
    cats = {o["value"]: o for o in fields["category"]["options"]}
    assert cats["trousers"]["count"] == 6 and cats["trousers"]["label"] == "Trousers"


def test_images_served_and_traversal_blocked(client):
    r = client.get("/images/train-000000-1")
    assert r.status_code == 200 and r.headers["content-type"] == "image/webp"
    assert "max-age" in r.headers["cache-control"]
    assert client.get("/images/unknown-1").status_code == 404
    assert client.get("/images/..%2Fmetadata.json").status_code in (404, 422)


def test_evaluation_endpoint(client, artifacts):
    body = client.get("/evaluation").json()
    assert body["manifest"]["item_count"] == 24 and "cleaning" not in body["manifest"]


def test_unknown_route_uses_error_shape(client):
    r = client.get("/nope")
    assert r.status_code == 404 and r.json()["error"]["code"] == "not_found"


def test_cors_allows_only_configured_origin(client):
    ok = client.options("/search/text", headers={
        "Origin": "http://localhost:5173", "Access-Control-Request-Method": "POST"})
    assert ok.headers.get("access-control-allow-origin") == "http://localhost:5173"
    bad = client.options("/search/text", headers={
        "Origin": "https://evil.example", "Access-Control-Request-Method": "POST"})
    assert "access-control-allow-origin" not in bad.headers


# --------------------------------------------------------------- security
def test_session_login_flow(make_client):
    c = make_client(auth_enabled=True, demo_password="s3cret", session_secret="test")
    assert c.post("/search/text", json={"query": "dress"}).status_code == 401
    assert c.get("/auth/me").json()["authenticated"] is False
    bad = c.post("/auth/login", json={"username": "demo", "password": "wrong"})
    assert bad.status_code == 401
    ok = c.post("/auth/login", json={"username": "demo", "password": "s3cret"})
    assert ok.status_code == 200 and "fvs_session" in ok.cookies
    assert c.post("/search/text", json={"query": "dress"}).status_code == 200
    assert c.get("/auth/me").json()["username"] == "demo"
    c.post("/auth/logout")
    c.cookies.clear()
    assert c.post("/search/text", json={"query": "dress"}).status_code == 401


def test_rate_limit_returns_429(make_client):
    c = make_client(rate_limit_enabled=True, rate_limit="2/minute")
    try:
        codes = [c.post("/search/text", json={"query": "dress"}).status_code for _ in range(3)]
        assert codes == [200, 200, 429]
    finally:
        limiter.reset()


def test_internal_errors_are_masked(make_client):
    class Exploding:
        dim, name = 16, "boom"

        def encode_texts(self, texts):
            raise RuntimeError("/secret/path/model.bin exploded")

        def encode_images(self, images):
            raise RuntimeError("boom")

    c = make_client(encoder=Exploding(), raise_server_exceptions=False)
    r = c.post("/search/text", json={"query": "dress"})
    assert r.status_code == 500
    assert "secret" not in r.text
    assert r.json()["error"]["code"] == "internal_error"
