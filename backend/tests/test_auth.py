"""Accounts: registration, sign-in, sessions, route gating and password storage."""

import sqlite3

import pytest

from app.services.users import UserStore, hash_password, password_problem, verify_password

GOOD = {"name": "Tanzila Tahreem", "email": "Tanzila@Example.com", "password": "lookbook123"}


@pytest.fixture()
def auth_client(make_client):
    return make_client(auth_enabled=True)


def test_search_and_items_require_a_session(auth_client):
    assert auth_client.post("/search/text", json={"query": "dress"}).status_code == 401
    assert auth_client.get("/items/train-000000-1").status_code == 401
    body = auth_client.post("/search/text", json={"query": "dress"}).json()
    assert body["error"]["code"] == "unauthorized"


def test_public_routes_stay_open(auth_client):
    for path in ("/health", "/filters", "/evaluation", "/showcase", "/images/train-000000-1"):
        assert auth_client.get(path).status_code == 200, path


def test_register_signs_in_and_normalises_email(auth_client):
    r = auth_client.post("/auth/register", json=GOOD)
    assert r.status_code == 201
    assert r.json()["user"] == {"id": 1, "name": "Tanzila Tahreem", "email": "tanzila@example.com"}
    assert "fvs_session" in r.cookies
    me = auth_client.get("/auth/me").json()
    assert me["authenticated"] is True and me["user"]["email"] == "tanzila@example.com"
    assert auth_client.post("/search/text", json={"query": "dress"}).status_code == 200


def test_duplicate_email_is_409_case_insensitive(auth_client):
    auth_client.post("/auth/register", json=GOOD)
    r = auth_client.post("/auth/register", json={**GOOD, "email": "  TANZILA@example.com "})
    assert r.status_code == 409 and r.json()["error"]["code"] == "email_taken"


@pytest.mark.parametrize("field,value,code", [
    ("password", "short1", "weak_password"),
    ("password", "lettersonly", "weak_password"),
    ("password", "12345678", "weak_password"),
    ("email", "not-an-email", "invalid_email"),
    ("name", "   ", "invalid_name"),
])
def test_register_validation(auth_client, field, value, code):
    r = auth_client.post("/auth/register", json={**GOOD, field: value})
    assert r.status_code == 400 and r.json()["error"]["code"] == code


def test_register_rejects_unknown_fields(auth_client):
    assert auth_client.post("/auth/register", json={**GOOD, "is_admin": True}).status_code == 422


def test_login_logout_cycle(make_client):
    c = make_client(auth_enabled=True)
    c.post("/auth/register", json=GOOD)
    c.post("/auth/logout")
    c.cookies.clear()
    assert c.get("/auth/me").json()["authenticated"] is False

    bad = c.post("/auth/login", json={"email": GOOD["email"], "password": "wrongpass1"})
    unknown = c.post("/auth/login", json={"email": "nobody@example.com", "password": "wrongpass1"})
    # Same status and message whether or not the email exists (no account enumeration).
    assert bad.status_code == unknown.status_code == 401
    assert bad.json() == unknown.json()

    ok = c.post("/auth/login", json={"email": "TANZILA@example.com", "password": GOOD["password"]})
    assert ok.status_code == 200 and ok.json()["user"]["name"] == "Tanzila Tahreem"
    assert c.post("/search/text", json={"query": "dress"}).status_code == 200


def test_tampered_or_foreign_cookie_is_rejected(make_client):
    c = make_client(auth_enabled=True)
    c.post("/auth/register", json=GOOD)
    token = c.cookies.get("fvs_session")
    c.cookies.clear()
    c.cookies.set("fvs_session", token[:-2] + ("AA" if not token.endswith("AA") else "BB"))
    assert c.get("/auth/me").json()["authenticated"] is False
    other = make_client(auth_enabled=True, session_secret="a-different-secret")
    other.cookies.set("fvs_session", token)
    assert other.get("/auth/me").json()["authenticated"] is False


def test_session_for_deleted_account_is_invalid(make_client, artifacts):
    c = make_client(auth_enabled=True)
    c.post("/auth/register", json=GOOD)
    with sqlite3.connect(artifacts / "users.db") as db:
        db.execute("DELETE FROM users")
    assert c.get("/auth/me").json()["authenticated"] is False
    assert c.post("/search/text", json={"query": "dress"}).status_code == 401


def test_auth_disabled_reports_open_session(client):
    me = client.get("/auth/me").json()
    assert me == {"authenticated": True, "auth_enabled": False, "user": None}


def test_register_rate_limited(make_client):
    c = make_client(auth_enabled=True, rate_limit_enabled=True)
    codes = [c.post("/auth/register", json={**GOOD, "email": f"u{i}@example.com"}).status_code for i in range(6)]
    assert codes[:5] == [201] * 5 and codes[5] == 429


# ------------------------------------------------------------- password storage
def test_passwords_are_salted_scrypt_hashes(tmp_path):
    store = UserStore(tmp_path / "u.db")
    store.create("A", "a@example.com", "lookbook123")
    with sqlite3.connect(tmp_path / "u.db") as db:
        stored = db.execute("SELECT password_hash FROM users").fetchone()[0]
    assert stored.startswith("scrypt$") and "lookbook123" not in stored
    assert hash_password("same-pass1") != hash_password("same-pass1")          # random salt
    assert verify_password("lookbook123", stored)
    assert not verify_password("lookbook124", stored)
    assert not verify_password("x", "garbage")


def test_password_policy():
    assert password_problem("lookbook123") is None
    assert password_problem("a1" * 70)                                          # > 128 chars
