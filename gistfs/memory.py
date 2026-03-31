"""High-level key-value memory abstraction on top of GistFS.

Designed as a simple persistent memory for AI agents: each *collection*
maps to a JSON file in the gist, and each file holds a dict of key→value
entries.
"""

from __future__ import annotations

import json
from typing import Any

from .core import GistFS


def _collection_filename(collection: str) -> str:
    """Map a logical collection name to a gist filename."""
    if collection.endswith(".json"):
        return collection
    return f"{collection}.json"


class GistMemory:
    """Dict-like persistent memory backed by a GitHub Gist.

    Usage::

        with GistMemory(gist_id="abc123") as mem:
            mem.put("user_prefs", {"theme": "dark"})
            prefs = mem.get("user_prefs")
            mem.put("user_prefs", {"theme": "light"})  # overwrite
            mem.delete("user_prefs")

    Collections let you partition keys into separate files::

        mem.put("k1", {"a": 1}, collection="session_a")
        mem.put("k2", {"b": 2}, collection="session_b")
    """

    DEFAULT_COLLECTION = "memory"

    @classmethod
    def create(
        cls,
        description: str = "",
        *,
        public: bool = False,
        token: str | None = None,
        default_collection: str | None = None,
    ) -> GistMemory:
        """Create a new GitHub Gist and return a :class:`GistMemory` bound to it."""
        gfs = GistFS.create(description=description, public=public, token=token)
        instance = cls.__new__(cls)
        instance.gfs = gfs
        instance.default_collection = default_collection or cls.DEFAULT_COLLECTION
        return instance

    def __init__(
        self,
        gist_id: str,
        token: str | None = None,
        *,
        default_collection: str | None = None,
    ) -> None:
        self.gfs = GistFS(gist_id, token=token)
        self.default_collection = default_collection or self.DEFAULT_COLLECTION

    # ── context manager ──────────────────────────────────────────────

    def __enter__(self) -> GistMemory:
        self.gfs.__enter__()
        return self

    def __exit__(self, *args: object) -> None:
        self.gfs.__exit__(*args)

    # ── core operations ──────────────────────────────────────────────

    def put(
        self,
        key: str,
        value: dict[str, Any],
        collection: str | None = None,
    ) -> None:
        """Store *value* under *key* in *collection*."""
        collection = collection or self.default_collection
        store = self._load_collection(collection)
        store[key] = value
        self._save_collection(collection, store)

    def get(
        self,
        key: str,
        collection: str | None = None,
    ) -> dict[str, Any] | None:
        """Retrieve the value for *key*, or ``None`` if missing."""
        collection = collection or self.default_collection
        store = self._load_collection(collection)
        return store.get(key)

    def get_all(
        self,
        collection: str | None = None,
    ) -> dict[str, dict[str, Any]]:
        """Return every key-value pair in *collection*."""
        collection = collection or self.default_collection
        return self._load_collection(collection)

    def delete(
        self,
        key: str,
        collection: str | None = None,
    ) -> bool:
        """Delete *key* from *collection*.  Returns True if it existed."""
        collection = collection or self.default_collection
        store = self._load_collection(collection)
        if key not in store:
            return False
        del store[key]
        self._save_collection(collection, store)
        return True

    def keys(self, collection: str | None = None) -> list[str]:
        """List all keys in *collection*."""
        collection = collection or self.default_collection
        return list(self._load_collection(collection).keys())

    def collections(self) -> list[str]:
        """List all collection names in this gist."""
        return [
            f.removesuffix(".json")
            for f in self.gfs.list_files()
            if f.endswith(".json")
        ]

    # ── internal ─────────────────────────────────────────────────────

    def _load_collection(self, collection: str) -> dict[str, Any]:
        fname = _collection_filename(collection)
        try:
            data = self.gfs.read(fname)
        except FileNotFoundError:
            return {}
        if not isinstance(data, dict):
            return {}
        return data

    def _save_collection(
        self, collection: str, store: dict[str, Any]
    ) -> None:
        fname = _collection_filename(collection)
        self.gfs.write(fname, store)

    def __repr__(self) -> str:
        return f"GistMemory(gist_id={self.gfs.gist_id!r})"
