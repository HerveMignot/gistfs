"""LangGraph BaseStore backed by a GitHub Gist.

Install with::

    pip install gistfs[langgraph]

Usage::

    from gistfs.integrations.langgraph import GistStore

    store = GistStore(gist_id="abc123")
    store.put(("user", "prefs"), "theme", {"value": "dark"})
    item = store.get(("user", "prefs"), "theme")
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime, timezone
from fnmatch import fnmatch
from typing import Any

from langgraph.store.base import (
    BaseStore,
    GetOp,
    Item,
    ListNamespacesOp,
    Op,
    PutOp,
    Result,
    SearchItem,
    SearchOp,
)

from ..core import GistFS


def _ns_to_filename(namespace: tuple[str, ...]) -> str:
    """Convert a namespace tuple to a gist filename."""
    return "__".join(namespace) + ".json" if namespace else "__root__.json"


def _filename_to_ns(filename: str) -> tuple[str, ...] | None:
    """Convert a gist filename back to a namespace tuple."""
    if not filename.endswith(".json"):
        return None
    stem = filename.removesuffix(".json")
    if stem == "__root__":
        return ()
    return tuple(stem.split("__"))


class GistStore(BaseStore):
    """A LangGraph ``BaseStore`` that persists data in a GitHub Gist.

    Namespaces are mapped to gist files (e.g. namespace ``("user", "prefs")``
    becomes ``user__prefs.json``).  Each file contains a JSON dict mapping
    keys to ``{value, created_at, updated_at}`` records.
    """

    @classmethod
    def create(
        cls,
        description: str = "",
        *,
        public: bool = False,
        token: str | None = None,
    ) -> GistStore:
        """Create a new gist and return a :class:`GistStore` bound to it."""
        gfs = GistFS.create(description=description, public=public, token=token)
        instance = cls.__new__(cls)
        BaseStore.__init__(instance)
        instance._gfs = gfs
        return instance

    def __init__(self, gist_id: str, token: str | None = None) -> None:
        super().__init__()
        self._gfs = GistFS(gist_id, token=token)
        self._gfs.sync()

    # ── abstract method implementations ──────────────────────────────

    def batch(self, ops: Iterable[Op]) -> list[Result]:
        results: list[Result] = []
        for op in ops:
            if isinstance(op, GetOp):
                results.append(self._handle_get(op))
            elif isinstance(op, PutOp):
                self._handle_put(op)
                results.append(None)
            elif isinstance(op, SearchOp):
                results.append(self._handle_search(op))
            elif isinstance(op, ListNamespacesOp):
                results.append(self._handle_list_namespaces(op))
            else:
                results.append(None)
        return results

    async def abatch(self, ops: Iterable[Op]) -> list[Result]:
        return self.batch(ops)

    # ── operation handlers ───────────────────────────────────────────

    def _handle_get(self, op: GetOp) -> Item | None:
        store = self._load_ns(op.namespace)
        record = store.get(op.key)
        if record is None:
            return None
        return self._record_to_item(op.namespace, op.key, record)

    def _handle_put(self, op: PutOp) -> None:
        store = self._load_ns(op.namespace)
        if op.value is None:
            # Delete
            store.pop(op.key, None)
        else:
            now = datetime.now(timezone.utc).isoformat()
            existing = store.get(op.key)
            created = existing["created_at"] if existing else now
            store[op.key] = {
                "value": op.value,
                "created_at": created,
                "updated_at": now,
            }
        self._save_ns(op.namespace, store)

    def _handle_search(self, op: SearchOp) -> list[SearchItem]:
        results: list[SearchItem] = []
        # Find all namespaces that match the prefix
        for fname in self._gfs.list_files():
            ns = _filename_to_ns(fname)
            if ns is None:
                continue
            if not self._ns_matches_prefix(ns, op.namespace_prefix):
                continue
            store = self._load_ns(ns)
            for key, record in store.items():
                if op.filter and not self._matches_filter(record.get("value", {}), op.filter):
                    continue
                item = self._record_to_item(ns, key, record)
                results.append(
                    SearchItem(
                        namespace=item.namespace,
                        key=item.key,
                        value=item.value,
                        created_at=item.created_at,
                        updated_at=item.updated_at,
                        score=None,
                    )
                )
        # Apply offset and limit
        return results[op.offset : op.offset + op.limit]

    def _handle_list_namespaces(
        self, op: ListNamespacesOp
    ) -> list[tuple[str, ...]]:
        all_ns: list[tuple[str, ...]] = []
        for fname in self._gfs.list_files():
            ns = _filename_to_ns(fname)
            if ns is None:
                continue
            if op.match_conditions:
                if not all(self._check_condition(ns, cond) for cond in op.match_conditions):
                    continue
            if op.max_depth is not None:
                ns = ns[: op.max_depth]
            if ns not in all_ns:
                all_ns.append(ns)
        return all_ns[op.offset : op.offset + op.limit]

    # ── helpers ──────────────────────────────────────────────────────

    def _load_ns(self, namespace: tuple[str, ...]) -> dict[str, Any]:
        fname = _ns_to_filename(namespace)
        try:
            data = self._gfs.read(fname)
        except FileNotFoundError:
            return {}
        return data if isinstance(data, dict) else {}

    def _save_ns(self, namespace: tuple[str, ...], store: dict[str, Any]) -> None:
        fname = _ns_to_filename(namespace)
        self._gfs.write(fname, store)

    @staticmethod
    def _record_to_item(
        namespace: tuple[str, ...], key: str, record: dict[str, Any]
    ) -> Item:
        return Item(
            namespace=namespace,
            key=key,
            value=record.get("value", record),
            created_at=datetime.fromisoformat(record["created_at"]),
            updated_at=datetime.fromisoformat(record["updated_at"]),
        )

    @staticmethod
    def _ns_matches_prefix(
        ns: tuple[str, ...], prefix: tuple[str, ...]
    ) -> bool:
        if len(ns) < len(prefix):
            return False
        for n, p in zip(ns, prefix):
            if p == "*":
                continue
            if n != p:
                return False
        return True

    @staticmethod
    def _matches_filter(value: dict[str, Any], filt: dict[str, Any]) -> bool:
        for k, v in filt.items():
            if value.get(k) != v:
                return False
        return True

    @staticmethod
    def _check_condition(ns: tuple[str, ...], cond: Any) -> bool:
        path = tuple(cond.path)
        if cond.match_type == "prefix":
            return GistStore._ns_matches_prefix(ns, path)
        if cond.match_type == "suffix":
            if len(ns) < len(path):
                return False
            suffix = ns[-len(path) :]
            return all(
                p == "*" or s == p for s, p in zip(suffix, path)
            )
        return True
