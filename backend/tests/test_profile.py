"""Profile: info, interests, favorites, collections, history, For-you picks, account."""

import sqlite3

import pytest

from app.services import profile as profile_mod

PW = "lookbook123"


def item(i: int) -> str:
    return f"train-{i:06d}-1"


def signup(client, email="tanzila@example.com", name="Tanzila Tahreem"):
    r = client.post("/auth/register", json={"name": name, "email": email, "password": PW})
    assert r.status_code == 201, r.text
    return r


@pytest.fixture()
def c(make_client):
    client = make_client(auth_enabled=True)
    signup(client)
    return client


# ------------------------------------------------------------------- auth
@pytest.mark.parametrize("method,path", [
    ("get", "/me/profile"), ("patch", "/me/profile"), ("put", "/me/interests"), ("get", "/me/favorites"),
    ("put", f"/me/favorites/{item(0)}"), ("get", "/me/collections"), ("post", "/me/collections"),
    ("get", "/me/history"), ("get", "/me/recommendations"), ("post", "/me/password"),
])
def test_every_me_route_needs_a_session(make_client, method, path):
    client = make_client(auth_enabled=True)
    r = getattr(client, method)(path) if method in ("get", "delete") else getattr(client, method)(path, json={})
    assert r.status_code == 401


def test_profile_needs_a_real_user_even_when_auth_is_off(client):
    assert client.get("/me/profile").status_code == 401


# ---------------------------------------------------------------- profile
def test_profile_defaults_and_update(c):
    p = c.get("/me/profile").json()
    assert p["user"]["name"] == "Tanzila Tahreem"
    assert p["profile"] == {"bio": "", "location": "", "avatar_color": "rose"}
    assert p["stats"] == {"favorites": 0, "collections": 0, "searches": 0}
    assert "minimal" in p["style_presets"] and len(p["avatar_colors"]) == 8

    r = c.patch("/me/profile", json={"name": "  Tanzila  T ", "bio": "Loves denim.", "location": "Bengaluru",
                                     "avatar_color": "violet"})
    assert r.status_code == 200
    body = r.json()
    assert body["user"]["name"] == "Tanzila T"
    assert body["profile"] == {"bio": "Loves denim.", "location": "Bengaluru", "avatar_color": "violet"}
    assert c.get("/auth/me").json()["user"]["name"] == "Tanzila T"


def test_profile_validation(c):
    assert c.patch("/me/profile", json={"avatar_color": "neon"}).json()["error"]["code"] == "invalid_avatar_color"
    assert c.patch("/me/profile", json={"name": "   "}).json()["error"]["code"] == "invalid_name"
    assert c.patch("/me/profile", json={"bio": "x" * 281}).status_code == 422
    assert c.patch("/me/profile", json={"is_admin": True}).status_code == 422


def test_interests_are_validated_against_the_catalogue(c):
    ok = c.put("/me/interests", json={"categories": ["trousers"], "colours": ["red"], "styles": ["Minimal", "minimal"]})
    assert ok.status_code == 200
    assert ok.json() == {"categories": ["trousers"], "colours": ["red"], "styles": ["minimal"]}
    bad = c.put("/me/interests", json={"categories": ["shoes"]})
    assert bad.status_code == 400 and bad.json()["error"]["code"] == "unsupported_filter"
    assert c.put("/me/interests", json={"styles": ["x" * 25]}).json()["error"]["code"] == "invalid_style"


# -------------------------------------------------------------- favorites
def test_favorites_crud_is_idempotent_and_newest_first(c):
    assert c.put(f"/me/favorites/{item(1)}").status_code == 200
    assert c.put(f"/me/favorites/{item(2)}").json()["ids"] == [item(2), item(1)]
    assert c.put(f"/me/favorites/{item(2)}").json()["ids"] == [item(2), item(1)]  # idempotent
    favs = c.get("/me/favorites").json()
    assert favs["total"] == 2 and favs["items"][0]["item_id"] == item(2) and "saved_at" in favs["items"][0]
    assert c.delete(f"/me/favorites/{item(2)}").json()["ids"] == [item(1)]
    assert c.delete(f"/me/favorites/{item(2)}").status_code == 200  # removing twice is fine


def test_favoriting_an_unknown_item_is_404(c):
    assert c.put("/me/favorites/train-999999-9").status_code == 404


def test_favorites_cap(c, monkeypatch):
    monkeypatch.setattr(profile_mod, "MAX_FAVORITES", 2)
    c.put(f"/me/favorites/{item(0)}")
    c.put(f"/me/favorites/{item(1)}")
    r = c.put(f"/me/favorites/{item(2)}")
    assert r.status_code == 400 and r.json()["error"]["code"] == "limit_reached"


# ------------------------------------------------------------ collections
def test_collections_lifecycle(c):
    r = c.post("/me/collections", json={"name": "  Summer  "})
    assert r.status_code == 201 and r.json()["name"] == "Summer"
    cid = r.json()["id"]
    assert c.post("/me/collections", json={"name": "summer"}).status_code == 409  # case-insensitive

    added = c.put(f"/me/collections/{cid}/items/{item(3)}").json()
    assert added["count"] == 1 and added["cover"][0]["item_id"] == item(3)
    assert item(3) in c.get("/me/favorites/ids").json()["ids"]  # adding also saves it

    assert c.patch(f"/me/collections/{cid}", json={"name": "Holiday"}).json()["name"] == "Holiday"
    listed = c.get("/me/collections").json()["collections"]
    assert [x["name"] for x in listed] == ["Holiday"] and listed[0]["count"] == 1

    # Un-saving removes it from every collection.
    c.delete(f"/me/favorites/{item(3)}")
    assert c.get(f"/me/collections/{cid}").json()["count"] == 0

    c.put(f"/me/collections/{cid}/items/{item(4)}")
    assert c.delete(f"/me/collections/{cid}/items/{item(4)}").json()["count"] == 0
    assert item(4) in c.get("/me/favorites/ids").json()["ids"]  # stays saved
    assert c.delete(f"/me/collections/{cid}").status_code == 204
    assert c.get(f"/me/collections/{cid}").status_code == 404


def test_users_cannot_touch_each_others_data(make_client):
    a = make_client(auth_enabled=True)
    signup(a, "a@example.com", "Alice")
    cid = a.post("/me/collections", json={"name": "Mine"}).json()["id"]
    a.put(f"/me/favorites/{item(5)}")
    a.post("/search/text", json={"query": "red dress"})

    b = make_client(auth_enabled=True)
    signup(b, "b@example.com", "Bob")
    assert b.get("/me/favorites/ids").json()["ids"] == []
    assert b.get("/me/collections").json()["collections"] == []
    assert b.get("/me/history").json()["entries"] == []
    assert b.get(f"/me/collections/{cid}").status_code == 404
    assert b.patch(f"/me/collections/{cid}", json={"name": "Stolen"}).status_code == 404
    assert b.put(f"/me/collections/{cid}/items/{item(6)}").status_code == 404
    assert b.delete(f"/me/collections/{cid}").status_code == 404
    assert a.get(f"/me/collections/{cid}").json()["name"] == "Mine"


# ---------------------------------------------------------------- history
def test_text_searches_are_recorded_deduplicated_and_capped(c, monkeypatch):
    monkeypatch.setattr(profile_mod, "MAX_HISTORY", 3)
    for q in ["red dress", "blue jeans", "Red Dress", "jacket", "top"]:
        assert c.post("/search/text", json={"query": q}).status_code == 200
    entries = c.get("/me/history").json()["entries"]
    assert [e["query"] for e in entries] == ["top", "jacket", "Red Dress"]
    c.delete(f"/me/history/{entries[0]['id']}")
    assert [e["query"] for e in c.get("/me/history").json()["entries"]] == ["jacket", "Red Dress"]
    assert c.delete("/me/history").status_code == 204
    assert c.get("/me/history").json()["entries"] == []


def test_failed_searches_are_not_recorded(c):
    c.post("/search/text", json={"query": "   "})
    assert c.get("/me/history").json()["entries"] == []


# -------------------------------------------------------------- for you
def test_recommendations_empty_state(c):
    r = c.get("/me/recommendations").json()
    assert r == {"sections": [], "has_favorites": False, "has_interests": False}


def test_recommendations_from_favorites_exclude_them_and_explain(c):
    # Items 6..8 are red trousers in the test catalogue.
    for i in (6, 7):
        c.put(f"/me/favorites/{item(i)}")
    r = c.get("/me/recommendations?top_k=5").json()
    assert r["has_favorites"] and [s["key"] for s in r["sections"]] == ["favorites"]
    picks = r["sections"][0]["items"]
    ids = [p["item_id"] for p in picks]
    assert item(6) not in ids and item(7) not in ids
    assert picks[0]["category_key"] == "trousers"
    assert all(p["reason"].startswith("Because you liked this ") for p in picks)


def test_recommendations_from_interests_and_no_duplicates(c):
    c.put("/me/interests", json={"categories": ["long_sleeve_outwear"], "colours": ["blue"], "styles": ["jacket"]})
    only = c.get("/me/recommendations?top_k=4").json()
    assert [s["key"] for s in only["sections"]] == ["interests"]
    first = only["sections"][0]["items"][0]
    assert first["category_key"] == "long_sleeve_outwear"
    assert first["reason"].startswith("Matches your interest in blue")

    c.put(f"/me/favorites/{item(6)}")
    both = c.get("/me/recommendations?top_k=4").json()
    assert [s["key"] for s in both["sections"]] == ["favorites", "interests"]
    all_ids = [p["item_id"] for s in both["sections"] for p in s["items"]]
    assert len(all_ids) == len(set(all_ids)) and item(6) not in all_ids


# ---------------------------------------------------------------- account
def test_change_password(c):
    wrong = c.post("/me/password", json={"current_password": "nope12345", "new_password": "newpass123"})
    assert wrong.status_code == 401
    weak = c.post("/me/password", json={"current_password": PW, "new_password": "short"})
    assert weak.json()["error"]["code"] == "weak_password"
    assert c.post("/me/password", json={"current_password": PW, "new_password": "newpass123"}).status_code == 204
    c.post("/auth/logout"); c.cookies.clear()  # noqa: E702
    assert c.post("/auth/login", json={"email": "tanzila@example.com", "password": PW}).status_code == 401
    assert c.post("/auth/login", json={"email": "tanzila@example.com", "password": "newpass123"}).status_code == 200


def test_change_email(make_client):
    other = make_client(auth_enabled=True)
    signup(other, "taken@example.com", "Other")
    c = make_client(auth_enabled=True)
    signup(c)
    assert c.patch("/me/account", json={"email": "taken@example.com", "current_password": PW}).status_code == 409
    bad = c.patch("/me/account", json={"email": "not-an-email", "current_password": PW})
    assert bad.json()["error"]["code"] == "invalid_email"
    assert c.patch("/me/account", json={"email": "new@example.com", "current_password": "bad"}).status_code == 401
    ok = c.patch("/me/account", json={"email": " NEW@example.com ", "current_password": PW})
    assert ok.status_code == 200 and ok.json()["email"] == "new@example.com"


def test_delete_account_removes_everything(c, artifacts):
    c.put("/me/interests", json={"colours": ["red"]})
    cid = c.post("/me/collections", json={"name": "Board"}).json()["id"]
    c.put(f"/me/collections/{cid}/items/{item(1)}")
    c.post("/search/text", json={"query": "red dress"})

    assert c.request("DELETE", "/me/account", json={"password": "wrong-pass1"}).status_code == 401
    r = c.request("DELETE", "/me/account", json={"password": PW})
    assert r.status_code == 204
    assert c.get("/auth/me").json()["authenticated"] is False
    with sqlite3.connect(artifacts / "users.db") as db:
        for table in ("users", "profiles", "favorites", "collections", "collection_items", "search_history"):
            assert db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] == 0, table
    assert c.post("/auth/login", json={"email": "tanzila@example.com", "password": PW}).status_code == 401
