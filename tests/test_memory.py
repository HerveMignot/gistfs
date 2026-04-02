"""Tests for GistMemory key-value memory layer."""

from gistfs import GistMemory


class TestGistMemoryCreate:
    def test_create_returns_memory(self, github_token):
        """create() returns a GistMemory with a valid gist."""
        mem = GistMemory.create(
            description="[gistfs-test] memory create",
            token=github_token,
        )
        assert mem.gfs.gist_id
        assert isinstance(mem, GistMemory)
        # Cleanup
        mem.gfs.delete_gist()


class TestGistMemoryPutGet:
    def test_put_and_get(self, gist_id, github_token):
        """Store and retrieve a value."""
        with GistMemory(gist_id, token=github_token) as mem:
            mem.put("key1", {"data": "hello"})
            result = mem.get("key1")
            assert result == {"data": "hello"}

    def test_get_missing_returns_none(self, gist_id, github_token):
        """Getting a missing key returns None."""
        with GistMemory(gist_id, token=github_token) as mem:
            assert mem.get("nonexistent_key") is None

    def test_put_overwrites(self, gist_id, github_token):
        """Putting the same key overwrites the value."""
        with GistMemory(gist_id, token=github_token) as mem:
            mem.put("overwrite_key", {"v": 1})
            mem.put("overwrite_key", {"v": 2})
            assert mem.get("overwrite_key") == {"v": 2}


class TestGistMemoryDelete:
    def test_delete_existing(self, gist_id, github_token):
        """Deleting an existing key returns True."""
        with GistMemory(gist_id, token=github_token) as mem:
            mem.put("del_key", {"tmp": True})
            assert mem.delete("del_key") is True
            assert mem.get("del_key") is None

    def test_delete_missing(self, gist_id, github_token):
        """Deleting a missing key returns False."""
        with GistMemory(gist_id, token=github_token) as mem:
            assert mem.delete("never_existed") is False


class TestGistMemoryCollections:
    def test_separate_collections(self, gist_id, github_token):
        """Keys in different collections are independent."""
        with GistMemory(gist_id, token=github_token) as mem:
            mem.put("shared_key", {"source": "a"}, collection="col_a")
            mem.put("shared_key", {"source": "b"}, collection="col_b")
            assert mem.get("shared_key", collection="col_a") == {"source": "a"}
            assert mem.get("shared_key", collection="col_b") == {"source": "b"}

    def test_get_all(self, gist_id, github_token):
        """get_all() returns all key-value pairs in a collection."""
        with GistMemory(gist_id, token=github_token) as mem:
            mem.put("ga_1", {"a": 1}, collection="getall_test")
            mem.put("ga_2", {"b": 2}, collection="getall_test")
            all_data = mem.get_all(collection="getall_test")
            assert all_data["ga_1"] == {"a": 1}
            assert all_data["ga_2"] == {"b": 2}

    def test_keys(self, gist_id, github_token):
        """keys() lists all keys in a collection."""
        with GistMemory(gist_id, token=github_token) as mem:
            mem.put("k1", {"x": 1}, collection="keys_test")
            mem.put("k2", {"x": 2}, collection="keys_test")
            keys = mem.keys(collection="keys_test")
            assert "k1" in keys
            assert "k2" in keys

    def test_collections_list(self, gist_id, github_token):
        """collections() lists all collection names."""
        with GistMemory(gist_id, token=github_token) as mem:
            mem.put("x", {"v": 1}, collection="list_col_a")
            mem.put("x", {"v": 1}, collection="list_col_b")
            cols = mem.collections()
            assert "list_col_a" in cols
            assert "list_col_b" in cols


class TestGistMemoryContextManager:
    def test_context_manager(self, gist_id, github_token):
        """GistMemory works as a context manager."""
        with GistMemory(gist_id, token=github_token) as mem:
            mem.put("ctx_key", {"ctx": True})
            assert mem.get("ctx_key") == {"ctx": True}
