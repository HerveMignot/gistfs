"""Tests for LlamaIndex GistKVStore integration."""

import pytest

try:
    from gistfs.integrations.llamaindex import GistKVStore
except ImportError:
    pytestmark = pytest.mark.skip("llama-index-core not installed")
    GistKVStore = None


class TestGistKVStore:
    @pytest.fixture()
    def store(self, gist_id, github_token):
        return GistKVStore(gist_id, token=github_token)

    def test_put_and_get(self, store):
        store.put("doc1", {"text": "hello"}, collection="test_li")
        result = store.get("doc1", collection="test_li")
        assert result == {"text": "hello"}

    def test_get_missing(self, store):
        assert store.get("missing_doc", collection="test_li_miss") is None

    def test_get_all(self, store):
        store.put("a", {"v": 1}, collection="test_li_all")
        store.put("b", {"v": 2}, collection="test_li_all")
        all_data = store.get_all(collection="test_li_all")
        assert all_data["a"] == {"v": 1}
        assert all_data["b"] == {"v": 2}

    def test_delete(self, store):
        store.put("del_doc", {"tmp": True}, collection="test_li_del")
        assert store.delete("del_doc", collection="test_li_del") is True
        assert store.get("del_doc", collection="test_li_del") is None

    def test_delete_missing(self, store):
        assert store.delete("nope", collection="test_li_del2") is False


class TestGistKVStoreAsync:
    @pytest.fixture()
    def store(self, gist_id, github_token):
        return GistKVStore(gist_id, token=github_token)

    @pytest.mark.asyncio
    async def test_aput_and_aget(self, store):
        await store.aput("async_doc", {"async": True}, collection="test_li_async")
        result = await store.aget("async_doc", collection="test_li_async")
        assert result == {"async": True}

    @pytest.mark.asyncio
    async def test_aget_all(self, store):
        await store.aput("aa", {"v": 1}, collection="test_li_aall")
        result = await store.aget_all(collection="test_li_aall")
        assert "aa" in result

    @pytest.mark.asyncio
    async def test_adelete(self, store):
        await store.aput("adel", {"tmp": True}, collection="test_li_adel")
        assert await store.adelete("adel", collection="test_li_adel") is True
