"""ProfileStore — everything a signed-in person keeps on their account.

Profile info, interests, favorites, collections and recent searches live in the
same SQLite file as the accounts (``USERS_DB_PATH``). Every table references
``users(id) ON DELETE CASCADE``, so deleting an account removes all of it, and
every query is scoped by ``user_id``: one person can never read or change
another person's rows.

Rules the store enforces (the API only validates shapes):
* adding an item to a collection also favorites it;
* un-favoriting removes the item from all of that user's collections;
* search history keeps the 20 most recent distinct queries (case-insensitive).
"""

from __future__ import annotations

import json
import sqlite3
import time
from contextlib import closing
from dataclasses import dataclass, field
from pathlib import Path

MAX_FAVORITES = 500
MAX_COLLECTIONS = 20
MAX_COLLECTION_ITEMS = 200
MAX_HISTORY = 20

AVATAR_COLORS = ("rose", "amber", "emerald", "sky", "violet", "slate", "gold", "coral")
STYLE_PRESETS = ("minimal", "streetwear", "boho", "formal", "sporty", "vintage", "casual", "party")


class LimitReached(Exception):
    def __init__(self, what: str, limit: int):
        super().__init__(f"You can keep at most {limit} {what}.")
        self.what, self.limit = what, limit


class CollectionNotFound(LookupError):
    pass


class CollectionNameTaken(ValueError):
    pass


@dataclass
class Interests:
    categories: list[str] = field(default_factory=list)
    colours: list[str] = field(default_factory=list)
    styles: list[str] = field(default_factory=list)

    @property
    def empty(self) -> bool:
        return not (self.categories or self.colours or self.styles)

    def as_dict(self) -> dict:
        return {"categories": self.categories, "colours": self.colours, "styles": self.styles}


@dataclass
class Profile:
    bio: str = ""
    location: str = ""
    avatar_color: str = AVATAR_COLORS[0]
    interests: Interests = field(default_factory=Interests)


@dataclass
class Collection:
    id: int
    name: str
    created_at: float
    item_ids: list[str]  # newest first


SCHEMA = """
CREATE TABLE IF NOT EXISTS profiles (
    user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    bio TEXT NOT NULL DEFAULT '',
    location TEXT NOT NULL DEFAULT '',
    avatar_color TEXT NOT NULL DEFAULT 'rose',
    interests_json TEXT NOT NULL DEFAULT '{}',
    updated_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS favorites (
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    item_id TEXT NOT NULL,
    created_at REAL NOT NULL,
    PRIMARY KEY (user_id, item_id)
);
CREATE TABLE IF NOT EXISTS collections (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    created_at REAL NOT NULL,
    UNIQUE (user_id, name COLLATE NOCASE)
);
CREATE TABLE IF NOT EXISTS collection_items (
    collection_id INTEGER NOT NULL REFERENCES collections(id) ON DELETE CASCADE,
    item_id TEXT NOT NULL,
    added_at REAL NOT NULL,
    PRIMARY KEY (collection_id, item_id)
);
CREATE TABLE IF NOT EXISTS search_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    query TEXT NOT NULL,
    created_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_history_user ON search_history (user_id, created_at DESC);
"""


class ProfileStore:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self._connect()) as db, db:
            db.executescript(SCHEMA)

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys = ON")
        return db

    # ------------------------------------------------------------------ profile
    def get_profile(self, user_id: int) -> Profile:
        with closing(self._connect()) as db:
            row = db.execute("SELECT * FROM profiles WHERE user_id = ?", (user_id,)).fetchone()
        if row is None:
            return Profile()
        try:
            raw = json.loads(row["interests_json"] or "{}")
        except json.JSONDecodeError:
            raw = {}
        interests = Interests(**{k: list(raw.get(k, [])) for k in ("categories", "colours", "styles")})
        return Profile(bio=row["bio"], location=row["location"], avatar_color=row["avatar_color"], interests=interests)

    def _upsert(self, user_id: int, **fields) -> None:
        current = self.get_profile(user_id)
        values = {
            "bio": current.bio, "location": current.location, "avatar_color": current.avatar_color,
            "interests_json": json.dumps(current.interests.as_dict()),
        }
        values.update(fields)
        with closing(self._connect()) as db, db:
            db.execute(
                """INSERT INTO profiles (user_id, bio, location, avatar_color, interests_json, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?)
                   ON CONFLICT(user_id) DO UPDATE SET bio = excluded.bio, location = excluded.location,
                     avatar_color = excluded.avatar_color, interests_json = excluded.interests_json,
                     updated_at = excluded.updated_at""",
                (user_id, values["bio"], values["location"], values["avatar_color"], values["interests_json"],
                 time.time()),
            )

    def update_profile(self, user_id: int, *, bio: str | None = None, location: str | None = None,
                       avatar_color: str | None = None) -> Profile:
        fields = {k: v for k, v in {"bio": bio, "location": location, "avatar_color": avatar_color}.items()
                  if v is not None}
        if fields:
            self._upsert(user_id, **fields)
        return self.get_profile(user_id)

    def set_interests(self, user_id: int, interests: Interests) -> Profile:
        self._upsert(user_id, interests_json=json.dumps(interests.as_dict()))
        return self.get_profile(user_id)

    # ---------------------------------------------------------------- favorites
    def favorites(self, user_id: int) -> list[tuple[str, float]]:
        """``(item_id, saved_at)``, newest first."""
        with closing(self._connect()) as db:
            rows = db.execute(
                "SELECT item_id, created_at FROM favorites WHERE user_id = ? ORDER BY created_at DESC, rowid DESC",
                (user_id,),
            ).fetchall()
        return [(r["item_id"], r["created_at"]) for r in rows]

    def favorite_ids(self, user_id: int) -> list[str]:
        return [i for i, _ in self.favorites(user_id)]

    def add_favorite(self, user_id: int, item_id: str, db: sqlite3.Connection | None = None) -> bool:
        """Idempotent. Returns True when newly added."""
        own = db is None
        conn = db or self._connect()
        try:
            exists = conn.execute(
                "SELECT 1 FROM favorites WHERE user_id = ? AND item_id = ?", (user_id, item_id)
            ).fetchone()
            if exists:
                return False
            n = conn.execute("SELECT COUNT(*) FROM favorites WHERE user_id = ?", (user_id,)).fetchone()[0]
            if n >= MAX_FAVORITES:
                raise LimitReached("favorites", MAX_FAVORITES)
            conn.execute("INSERT INTO favorites (user_id, item_id, created_at) VALUES (?, ?, ?)",
                         (user_id, item_id, time.time()))
            if own:
                conn.commit()
            return True
        finally:
            if own:
                conn.close()

    def remove_favorite(self, user_id: int, item_id: str) -> None:
        with closing(self._connect()) as db, db:
            db.execute("DELETE FROM favorites WHERE user_id = ? AND item_id = ?", (user_id, item_id))
            db.execute(
                """DELETE FROM collection_items WHERE item_id = ? AND collection_id IN
                   (SELECT id FROM collections WHERE user_id = ?)""",
                (item_id, user_id),
            )

    # -------------------------------------------------------------- collections
    def collections(self, user_id: int) -> list[Collection]:
        with closing(self._connect()) as db:
            cols = db.execute(
                "SELECT id, name, created_at FROM collections WHERE user_id = ? ORDER BY created_at DESC, id DESC",
                (user_id,),
            ).fetchall()
            out = []
            for c in cols:
                items = db.execute(
                    "SELECT item_id FROM collection_items WHERE collection_id = ? ORDER BY added_at DESC, rowid DESC",
                    (c["id"],),
                ).fetchall()
                out.append(Collection(c["id"], c["name"], c["created_at"], [r["item_id"] for r in items]))
        return out

    def collection(self, user_id: int, collection_id: int) -> Collection:
        for c in self.collections(user_id):
            if c.id == collection_id:
                return c
        raise CollectionNotFound(collection_id)

    def create_collection(self, user_id: int, name: str) -> Collection:
        with closing(self._connect()) as db, db:
            n = db.execute("SELECT COUNT(*) FROM collections WHERE user_id = ?", (user_id,)).fetchone()[0]
            if n >= MAX_COLLECTIONS:
                raise LimitReached("collections", MAX_COLLECTIONS)
            try:
                cur = db.execute("INSERT INTO collections (user_id, name, created_at) VALUES (?, ?, ?)",
                                 (user_id, name, time.time()))
            except sqlite3.IntegrityError as exc:
                raise CollectionNameTaken(name) from exc
            new_id = int(cur.lastrowid)
        return self.collection(user_id, new_id)

    def _owned(self, db: sqlite3.Connection, user_id: int, collection_id: int) -> None:
        if not db.execute("SELECT 1 FROM collections WHERE id = ? AND user_id = ?",
                          (collection_id, user_id)).fetchone():
            raise CollectionNotFound(collection_id)

    def rename_collection(self, user_id: int, collection_id: int, name: str) -> Collection:
        with closing(self._connect()) as db, db:
            self._owned(db, user_id, collection_id)
            try:
                db.execute("UPDATE collections SET name = ? WHERE id = ?", (name, collection_id))
            except sqlite3.IntegrityError as exc:
                raise CollectionNameTaken(name) from exc
        return self.collection(user_id, collection_id)

    def delete_collection(self, user_id: int, collection_id: int) -> None:
        with closing(self._connect()) as db, db:
            self._owned(db, user_id, collection_id)
            db.execute("DELETE FROM collections WHERE id = ?", (collection_id,))

    def add_to_collection(self, user_id: int, collection_id: int, item_id: str) -> Collection:
        with closing(self._connect()) as db, db:
            self._owned(db, user_id, collection_id)
            exists = db.execute("SELECT 1 FROM collection_items WHERE collection_id = ? AND item_id = ?",
                                (collection_id, item_id)).fetchone()
            if not exists:
                n = db.execute("SELECT COUNT(*) FROM collection_items WHERE collection_id = ?",
                               (collection_id,)).fetchone()[0]
                if n >= MAX_COLLECTION_ITEMS:
                    raise LimitReached("items in a collection", MAX_COLLECTION_ITEMS)
                self.add_favorite(user_id, item_id, db=db)  # collections are groups of favorites
                db.execute("INSERT INTO collection_items (collection_id, item_id, added_at) VALUES (?, ?, ?)",
                           (collection_id, item_id, time.time()))
        return self.collection(user_id, collection_id)

    def remove_from_collection(self, user_id: int, collection_id: int, item_id: str) -> Collection:
        with closing(self._connect()) as db, db:
            self._owned(db, user_id, collection_id)
            db.execute("DELETE FROM collection_items WHERE collection_id = ? AND item_id = ?",
                       (collection_id, item_id))
        return self.collection(user_id, collection_id)

    # ------------------------------------------------------------------ history
    def record_search(self, user_id: int, query: str) -> None:
        query = " ".join(query.split())[:200]
        if not query:
            return
        with closing(self._connect()) as db, db:
            db.execute("DELETE FROM search_history WHERE user_id = ? AND lower(query) = lower(?)", (user_id, query))
            db.execute("INSERT INTO search_history (user_id, query, created_at) VALUES (?, ?, ?)",
                       (user_id, query, time.time()))
            db.execute(
                """DELETE FROM search_history WHERE user_id = ? AND id NOT IN
                   (SELECT id FROM search_history WHERE user_id = ? ORDER BY created_at DESC, id DESC LIMIT ?)""",
                (user_id, user_id, MAX_HISTORY),
            )

    def history(self, user_id: int) -> list[dict]:
        with closing(self._connect()) as db:
            rows = db.execute(
                "SELECT id, query, created_at FROM search_history WHERE user_id = ? ORDER BY created_at DESC, id DESC",
                (user_id,),
            ).fetchall()
        return [{"id": r["id"], "query": r["query"], "created_at": r["created_at"]} for r in rows]

    def delete_history(self, user_id: int, entry_id: int | None = None) -> None:
        with closing(self._connect()) as db, db:
            if entry_id is None:
                db.execute("DELETE FROM search_history WHERE user_id = ?", (user_id,))
            else:
                db.execute("DELETE FROM search_history WHERE user_id = ? AND id = ?", (user_id, entry_id))

    # -------------------------------------------------------------------- stats
    def stats(self, user_id: int) -> dict:
        with closing(self._connect()) as db:
            q = lambda sql: int(db.execute(sql, (user_id,)).fetchone()[0])  # noqa: E731
            return {
                "favorites": q("SELECT COUNT(*) FROM favorites WHERE user_id = ?"),
                "collections": q("SELECT COUNT(*) FROM collections WHERE user_id = ?"),
                "searches": q("SELECT COUNT(*) FROM search_history WHERE user_id = ?"),
            }
