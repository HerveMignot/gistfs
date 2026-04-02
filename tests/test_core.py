"""Tests for GistFS core functionality."""

from gistfs import GistFS


class TestGistFSCreate:
    def test_create_returns_gistfs(self, github_token):
        """create() returns a GistFS with a valid gist_id."""
        gfs = GistFS.create(
            description="[gistfs-test] create test",
            token=github_token,
        )
        assert gfs.gist_id
        assert isinstance(gfs, GistFS)
        # Has the seed file
        assert "_gistfs.json" in gfs.list_files()
        # Cleanup
        gfs.delete_gist()

    def test_create_with_init_files(self, github_token):
        """create() seeds the gist with provided files."""
        gfs = GistFS.create(
            description="[gistfs-test] init files",
            token=github_token,
            init_files={"config.json": {"version": 1}},
        )
        assert "config.json" in gfs.list_files()
        assert gfs.read("config.json") == {"version": 1}
        # Cleanup
        gfs.delete_gist()


class TestGistFSReadWrite:
    def test_write_and_read(self, test_gist):
        """Write data and read it back."""
        test_gist.write("test_rw.json", {"hello": "world"})
        result = test_gist.read("test_rw.json")
        assert result == {"hello": "world"}

    def test_write_overwrites(self, test_gist):
        """Writing to the same file overwrites the content."""
        test_gist.write("test_overwrite.json", {"v": 1})
        test_gist.write("test_overwrite.json", {"v": 2})
        assert test_gist.read("test_overwrite.json") == {"v": 2}

    def test_read_missing_raises(self, test_gist):
        """Reading a non-existent file raises FileNotFoundError."""
        import pytest
        with pytest.raises(FileNotFoundError):
            test_gist.read("does_not_exist.json")

    def test_write_nested_data(self, test_gist):
        """Complex nested structures survive the round trip."""
        data = {
            "users": [{"name": "Alice", "scores": [10, 20]}],
            "meta": {"nested": {"deep": True}},
        }
        test_gist.write("test_nested.json", data)
        assert test_gist.read("test_nested.json") == data


class TestGistFSDelete:
    def test_delete_existing(self, test_gist):
        """Deleting an existing file returns True."""
        test_gist.write("test_del.json", {"tmp": 1})
        assert test_gist.delete("test_del.json") is True
        assert "test_del.json" not in test_gist.list_files()

    def test_delete_missing(self, test_gist):
        """Deleting a non-existent file returns False."""
        assert test_gist.delete("never_existed.json") is False


class TestGistFSListAndExists:
    def test_list_files(self, test_gist):
        """list_files() includes written files."""
        test_gist.write("test_list.json", {})
        files = test_gist.list_files()
        assert "test_list.json" in files

    def test_exists(self, test_gist):
        """exists() returns correct boolean."""
        test_gist.write("test_exists.json", {})
        assert test_gist.exists("test_exists.json") is True
        assert test_gist.exists("nope.json") is False

    def test_read_all(self, test_gist):
        """read_all() returns a dict of all files."""
        test_gist.write("test_readall.json", {"a": 1})
        all_files = test_gist.read_all()
        assert isinstance(all_files, dict)
        assert "test_readall.json" in all_files
        assert all_files["test_readall.json"] == {"a": 1}


class TestGistFSContextManager:
    def test_context_manager(self, gist_id, github_token):
        """GistFS works as a context manager."""
        with GistFS(gist_id, token=github_token) as gfs:
            gfs.write("test_ctx.json", {"ctx": True})
            assert gfs.read("test_ctx.json") == {"ctx": True}

    def test_sync_on_enter(self, gist_id, github_token):
        """Entering the context manager syncs the cache."""
        with GistFS(gist_id, token=github_token) as gfs:
            files = gfs.list_files()
            assert isinstance(files, list)
