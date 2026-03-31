"""Tests for LangGraph GistStore integration."""

import pytest

try:
    from gistfs.integrations.langgraph import GistStore
except ImportError:
    pytestmark = pytest.mark.skip("langgraph-checkpoint not installed")
    GistStore = None


class TestGistStore:
    @pytest.fixture()
    def store(self, gist_id, github_token):
        return GistStore(gist_id, token=github_token)

    def test_put_and_get(self, store):
        store.put(("test", "ns"), "key1", {"data": "value"})
        item = store.get(("test", "ns"), "key1")
        assert item is not None
        assert item.value == {"data": "value"}
        assert item.key == "key1"
        assert item.namespace == ("test", "ns")

    def test_get_missing(self, store):
        item = store.get(("test", "missing"), "nope")
        assert item is None

    def test_put_overwrites(self, store):
        store.put(("test", "overwrite"), "k", {"v": 1})
        store.put(("test", "overwrite"), "k", {"v": 2})
        item = store.get(("test", "overwrite"), "k")
        assert item.value == {"v": 2}

    def test_put_preserves_created_at(self, store):
        store.put(("test", "timestamps"), "k", {"v": 1})
        item1 = store.get(("test", "timestamps"), "k")
        store.put(("test", "timestamps"), "k", {"v": 2})
        item2 = store.get(("test", "timestamps"), "k")
        assert item2.created_at == item1.created_at
        assert item2.updated_at >= item1.updated_at

    def test_delete(self, store):
        store.put(("test", "del"), "dk", {"tmp": True})
        store.delete(("test", "del"), "dk")
        assert store.get(("test", "del"), "dk") is None


class TestGistStoreSearch:
    @pytest.fixture()
    def store(self, gist_id, github_token):
        s = GistStore(gist_id, token=github_token)
        s.put(("search", "a"), "item1", {"color": "red", "size": 10})
        s.put(("search", "a"), "item2", {"color": "blue", "size": 20})
        s.put(("search", "b"), "item3", {"color": "red", "size": 30})
        return s

    def test_search_by_prefix(self, store):
        results = store.search(("search",))
        keys = {r.key for r in results}
        assert "item1" in keys
        assert "item2" in keys
        assert "item3" in keys

    def test_search_with_filter(self, store):
        results = store.search(("search",), filter={"color": "red"})
        keys = {r.key for r in results}
        assert "item1" in keys
        assert "item3" in keys
        assert "item2" not in keys

    def test_search_with_limit(self, store):
        results = store.search(("search",), limit=1)
        assert len(results) == 1

    def test_search_specific_namespace(self, store):
        results = store.search(("search", "a"))
        keys = {r.key for r in results}
        assert "item1" in keys
        assert "item2" in keys
        assert "item3" not in keys


class TestGistStoreListNamespaces:
    @pytest.fixture()
    def store(self, gist_id, github_token):
        s = GistStore(gist_id, token=github_token)
        s.put(("lns", "x"), "k", {"v": 1})
        s.put(("lns", "y"), "k", {"v": 1})
        return s

    def test_list_namespaces(self, store):
        namespaces = store.list_namespaces(prefix=("lns",))
        assert ("lns", "x") in namespaces
        assert ("lns", "y") in namespaces

    def test_list_namespaces_with_max_depth(self, store):
        namespaces = store.list_namespaces(prefix=("lns",), max_depth=1)
        # Truncated to depth 1
        assert all(len(ns) <= 1 for ns in namespaces)
