"""UserStore — accounts in SQLite with scrypt-hashed passwords (stdlib only).

* Passwords are hashed with ``hashlib.scrypt`` (n=2^14, r=8, p=1, 16-byte random
  salt) and verified in constant time. Plain-text passwords are never stored or logged.
* Emails are normalised (trimmed, lower-cased) and unique.
* One short-lived connection per call keeps the store safe across FastAPI's
  threadpool without a global lock; SQLite serialises the writes.

On a free Hugging Face Space the container disk is ephemeral; point
``USERS_DB_PATH`` at ``/data/users.db`` with persistent storage enabled to keep
accounts across restarts.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import os
import re
import sqlite3
import time
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path

SCRYPT_N, SCRYPT_R, SCRYPT_P, KEY_LEN = 2**14, 8, 1, 32
EMAIL_RE = re.compile(r"^[^@\s]{1,64}@[^@\s]+\.[^@\s]{2,}$")


class EmailTaken(ValueError):
    pass


@dataclass(frozen=True)
class User:
    id: int
    name: str
    email: str
    created_at: float


def normalise_email(email: str) -> str:
    return email.strip().lower()


def valid_email(email: str) -> bool:
    return len(email) <= 254 and bool(EMAIL_RE.match(email))


def password_problem(password: str) -> str | None:
    """Human-readable reason a password is too weak, or ``None`` if acceptable."""
    if len(password) < 8:
        return "Password must be at least 8 characters."
    if len(password) > 128:
        return "Password must be at most 128 characters."
    if not re.search(r"[A-Za-z]", password) or not re.search(r"\d", password):
        return "Password must contain at least one letter and one number."
    return None


def _b64(b: bytes) -> str:
    return base64.b64encode(b).decode()


def hash_password(password: str, salt: bytes | None = None) -> str:
    salt = salt or os.urandom(16)
    key = hashlib.scrypt(password.encode(), salt=salt, n=SCRYPT_N, r=SCRYPT_R, p=SCRYPT_P, dklen=KEY_LEN)
    return f"scrypt${SCRYPT_N}${SCRYPT_R}${SCRYPT_P}${_b64(salt)}${_b64(key)}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algo, n, r, p, salt_b64, key_b64 = stored.split("$")
        if algo != "scrypt":
            return False
        expected = base64.b64decode(key_b64)
        key = hashlib.scrypt(password.encode(), salt=base64.b64decode(salt_b64),
                             n=int(n), r=int(r), p=int(p), dklen=len(expected))
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(key, expected)


# Verifying against this when the email is unknown keeps response time constant,
# so login timing doesn't reveal which emails have accounts.
_DUMMY_HASH = hash_password("timing-equaliser-not-a-real-password", salt=b"\0" * 16)


class UserStore:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self._connect()) as db, db:
            db.execute(
                """CREATE TABLE IF NOT EXISTS users (
                       id INTEGER PRIMARY KEY AUTOINCREMENT,
                       name TEXT NOT NULL,
                       email TEXT NOT NULL UNIQUE,
                       password_hash TEXT NOT NULL,
                       created_at REAL NOT NULL)"""
            )

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        return db

    @staticmethod
    def _user(row: sqlite3.Row | None) -> User | None:
        if row is None:
            return None
        return User(id=row["id"], name=row["name"], email=row["email"], created_at=row["created_at"])

    def create(self, name: str, email: str, password: str) -> User:
        email = normalise_email(email)
        pw_hash = hash_password(password)
        try:
            with closing(self._connect()) as db, db:
                cur = db.execute(
                    "INSERT INTO users (name, email, password_hash, created_at) VALUES (?, ?, ?, ?)",
                    (name.strip(), email, pw_hash, time.time()),
                )
                user_id = cur.lastrowid
        except sqlite3.IntegrityError as exc:
            raise EmailTaken(email) from exc
        return self.get(int(user_id))  # type: ignore[return-value]

    def get(self, user_id: int) -> User | None:
        with closing(self._connect()) as db:
            return self._user(db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone())

    def authenticate(self, email: str, password: str) -> User | None:
        with closing(self._connect()) as db:
            row = db.execute("SELECT * FROM users WHERE email = ?", (normalise_email(email),)).fetchone()
        if row is None:
            verify_password(password, _DUMMY_HASH)
            return None
        return self._user(row) if verify_password(password, row["password_hash"]) else None

    def count(self) -> int:
        with closing(self._connect()) as db:
            return int(db.execute("SELECT COUNT(*) FROM users").fetchone()[0])
