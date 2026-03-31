"""LlamaIndex KVStore backed by a GitHub Gist.

Install with::

    pip install gistfs[llamaindex]

Usage::

    from gistfs.integrations.llamaindex import GistKVStore

    store = GistKVStore(gist_id="abc123")
    store.put("doc1", {"text": "hello"}, collection="vectors")
    doc = store.get("doc1", collection="vectors")
"""

from __future__ import annotations

from typing import Any

from llama_index.core.storage.kvstore.types import (
    DEFAULT_COLLECTION,
    BaseKVStore,
)

from ..memory import GistMemory


class GistKVStore(BaseKVStore):
    """A LlamaIndex ``BaseKVStore`` that persists data in a GitHub Gist.

    Each *collection* is stored as a separate JSON file inside the gist
    (e.g. ``"docstore.json"``, ``"index_store.json"``).
    """

    @classmethod
    def create(
        cls,
        description: str = "",
        *,
        public: bool = False,
        token: str | None = None,
    ) -> GistKVStore:
        """Create a new gist and return a :class:`GistKVStore` bound to it."""
        mem = GistMemory.create(description=description, public=public, token=token)
        instance = cls.__new__(cls)
        instance._mem = mem
        return instance

    def __init__(
        self,
        gist_id: str,
        token: str | None = None,
    ) -> None:
        self._mem = GistMemory(gist_id, token=token)
        self._mem.gfs.sync()

    # ── sync methods ─────────────────────────────────────────────────

    def put(
        self,
        key: str,
        val: dict,
        collection: str = DEFAULT_COLLECTION,
    ) -> None:
        self._mem.put(key, val, collection=collection)

    def get(
        self,
        key: str,
        collection: str = DEFAULT_COLLECTION,
    ) -> dict | None:
        return self._mem.get(key, collection=collection)

    def get_all(
        self,
        collection: str = DEFAULT_COLLECTION,
    ) -> dict[str, dict]:
        return self._mem.get_all(collection=collection)

    def delete(
        self,
        key: str,
        collection: str = DEFAULT_COLLECTION,
    ) -> bool:
        return self._mem.delete(key, collection=collection)

    # ── async methods (delegate to sync) ─────────────────────────────

    async def aput(
        self,
        key: str,
        val: dict,
        collection: str = DEFAULT_COLLECTION,
    ) -> None:
        self.put(key, val, collection=collection)

    async def aget(
        self,
        key: str,
        collection: str = DEFAULT_COLLECTION,
    ) -> dict | None:
        return self.get(key, collection=collection)

    async def aget_all(
        self,
        collection: str = DEFAULT_COLLECTION,
    ) -> dict[str, dict]:
        return self.get_all(collection=collection)

    async def adelete(
        self,
        key: str,
        collection: str = DEFAULT_COLLECTION,
    ) -> bool:
        return self.delete(key, collection=collection)
