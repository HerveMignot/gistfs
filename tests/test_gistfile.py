"""Tests for GistFile file-like interface."""

import io

import pytest

from gistfs import GistFS


class TestGistFileWrite:
    def test_write_mode(self, test_gist):
        """Write text via file-like interface."""
        with test_gist.open("filelike_w.txt", "w") as f:
            f.write("hello world")
        assert test_gist.read("filelike_w.txt") == "hello world"

    def test_write_multiple(self, test_gist):
        """Multiple writes are concatenated."""
        with test_gist.open("filelike_multi.txt", "w") as f:
            f.write("line1\n")
            f.write("line2\n")
        assert test_gist.read("filelike_multi.txt") == "line1\nline2\n"

    def test_write_json_string(self, test_gist):
        """Writing a JSON string is parsed back as structured data."""
        import json
        data = {"key": "value", "n": 42}
        with test_gist.open("filelike_json.json", "w") as f:
            f.write(json.dumps(data))
        assert test_gist.read("filelike_json.json") == data

    def test_write_not_readable(self, test_gist):
        """Write-mode files cannot be read."""
        with test_gist.open("filelike_wnr.txt", "w") as f:
            with pytest.raises(io.UnsupportedOperation):
                f.read()


class TestGistFileRead:
    def test_read_mode(self, test_gist):
        """Read text via file-like interface."""
        with test_gist.open("filelike_r.txt", "w") as f:
            f.write("content here")
        with test_gist.open("filelike_r.txt", "r") as f:
            assert f.read() == "content here"

    def test_read_structured(self, test_gist):
        """Reading a structured value returns its JSON representation."""
        test_gist.write("filelike_rs.json", {"a": 1})
        with test_gist.open("filelike_rs.json", "r") as f:
            content = f.read()
        assert '"a"' in content
        assert "1" in content

    def test_read_missing_raises(self, test_gist):
        """Opening a missing file in read mode raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            test_gist.open("does_not_exist.txt", "r")

    def test_read_not_writable(self, test_gist):
        """Read-mode files cannot be written to."""
        test_gist.write("filelike_rnw.txt", "data")
        with test_gist.open("filelike_rnw.txt", "r") as f:
            with pytest.raises(io.UnsupportedOperation):
                f.write("nope")

    def test_readline(self, test_gist):
        """readline() works on multi-line content."""
        test_gist.write("filelike_rl.txt", "line1\nline2\nline3")
        with test_gist.open("filelike_rl.txt", "r") as f:
            first = f.readline()
        assert "line1" in first

    def test_readlines(self, test_gist):
        """readlines() returns a list of lines."""
        test_gist.write("filelike_rls.txt", "a\nb\nc")
        with test_gist.open("filelike_rls.txt", "r") as f:
            lines = f.readlines()
        assert len(lines) >= 1

    def test_iteration(self, test_gist):
        """File object is iterable line by line."""
        test_gist.write("filelike_iter.txt", "x\ny\nz")
        with test_gist.open("filelike_iter.txt", "r") as f:
            lines = list(f)
        assert len(lines) >= 1


class TestGistFileAppend:
    def test_append_mode(self, test_gist):
        """Append mode adds to existing content."""
        with test_gist.open("filelike_a.txt", "w") as f:
            f.write("start")
        with test_gist.open("filelike_a.txt", "a") as f:
            f.write(" end")
        with test_gist.open("filelike_a.txt", "r") as f:
            content = f.read()
        assert "start" in content
        assert "end" in content

    def test_append_creates_new(self, test_gist):
        """Append mode on a missing file creates it."""
        with test_gist.open("filelike_anew.txt", "a") as f:
            f.write("fresh")
        assert test_gist.read("filelike_anew.txt") == "fresh"


class TestGistFileReadWrite:
    def test_rw_mode(self, test_gist):
        """r+ mode allows both reading and writing."""
        test_gist.write("filelike_rw.txt", "original")
        with test_gist.open("filelike_rw.txt", "r+") as f:
            content = f.read()
            assert "original" in content
            f.write(" modified")
        with test_gist.open("filelike_rw.txt", "r") as f:
            result = f.read()
        assert "modified" in result

    def test_rw_creates_new(self, test_gist):
        """r+ mode on a missing file creates it."""
        with test_gist.open("filelike_rwnew.txt", "r+") as f:
            f.write("new content")
        assert test_gist.read("filelike_rwnew.txt") == "new content"


class TestGistFileSeekTell:
    def test_seek_and_tell(self, test_gist):
        """seek() and tell() work correctly."""
        with test_gist.open("filelike_st.txt", "w") as f:
            f.write("abcdef")
            f.seek(0)
            assert f.tell() == 0
            f.seek(3)
            assert f.tell() == 3


class TestGistFileProperties:
    def test_name(self, test_gist):
        test_gist.write("filelike_props.txt", "x")
        with test_gist.open("filelike_props.txt", "r") as f:
            assert f.name == "filelike_props.txt"

    def test_mode(self, test_gist):
        test_gist.write("filelike_props.txt", "x")
        with test_gist.open("filelike_props.txt", "r") as f:
            assert f.mode == "r"

    def test_repr(self, test_gist):
        test_gist.write("filelike_props.txt", "x")
        f = test_gist.open("filelike_props.txt", "r")
        assert "filelike_props.txt" in repr(f)
        assert "'r'" in repr(f)
        f.close()
        assert "closed" in repr(f)

    def test_invalid_mode(self, test_gist):
        with pytest.raises(ValueError, match="Unsupported mode"):
            test_gist.open("x.txt", "x")
