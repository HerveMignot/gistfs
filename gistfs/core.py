"""Core GistFS class — use GitHub Gists as a persistent key-value filesystem."""

from __future__ import annotations

import io
import json
import os
from typing import Any

import requests


GITHUB_API_GISTS = "https://api.github.com/gists/{gist_id}"
GITHUB_API_GISTS_BASE = "https://api.github.com/gists"


class GistFS:
    """A filesystem-like interface backed by a single GitHub Gist.

    Each "file" in the gist stores a JSON-serialized value, giving you a
    persistent key-value store accessible from anywhere with an internet
    connection.

    Usage::

        with GistFS(gist_id="abc123") as gfs:
            gfs.write("state.json", {"counter": 1})
            data = gfs.read("state.json")
            print(gfs.list_files())
            gfs.delete("state.json")

    The token is read from the ``GITHUB_TOKEN`` environment variable by
    default, or can be passed explicitly.  Read-only operations on public
    gists work without a token.
    """

    def __init__(
        self,
        gist_id: str,
        token: str | None = None,
        *,
        auto_sync: bool = True,
        encryption_key: str | None = None,
    ) -> None:
        self.gist_id = gist_id
        self.token = token or os.environ.get("GITHUB_TOKEN", "")
        self.auto_sync = auto_sync
        self.encryption_key = encryption_key
        self._url = GITHUB_API_GISTS.format(gist_id=gist_id)
        self._cache: dict[str, Any] | None = None

    # ── factory ───────────────────────────────────────────────────────

    @classmethod
    def create(
        cls,
        description: str = "",
        *,
        public: bool = False,
        token: str | None = None,
        init_files: dict[str, Any] | None = None,
        encryption_key: str | None = None,
    ) -> GistFS:
        """Create a new GitHub Gist and return a :class:`GistFS` bound to it.

        Parameters
        ----------
        description:
            Gist description shown on GitHub.
        public:
            If ``True`` the gist is public; otherwise it is secret (default).
        token:
            GitHub personal access token.  Falls back to ``GITHUB_TOKEN``.
        init_files:
            Optional mapping of ``{filename: content}`` to seed the gist with.
            If *None*, a single placeholder file ``_gistfs.json`` is created.

        Returns
        -------
        GistFS
            A new instance already synced with the freshly created gist.
        """
        resolved_token = token or os.environ.get("GITHUB_TOKEN", "")
        if not resolved_token:
            raise ValueError(
                "A GitHub token is required to create a gist. "
                "Set GITHUB_TOKEN or pass token=."
            )

        if init_files:
            files_payload = {}
            for fname, data in init_files.items():
                raw = json.dumps(data, ensure_ascii=False, default=str)
                if encryption_key:
                    from .crypto import encrypt
                    raw = encrypt(raw, encryption_key)
                files_payload[fname] = {"content": raw}
        else:
            init_content = "{}"
            if encryption_key:
                from .crypto import encrypt
                init_content = encrypt(init_content, encryption_key)
            files_payload = {"_gistfs.json": {"content": init_content}}

        payload: dict[str, Any] = {
            "description": description,
            "public": public,
            "files": files_payload,
        }
        headers = {
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {resolved_token}",
        }
        resp = requests.post(GITHUB_API_GISTS_BASE, headers=headers, json=payload)
        resp.raise_for_status()

        gist_id = resp.json()["id"]
        instance = cls(gist_id, token=resolved_token, encryption_key=encryption_key)
        instance.sync()
        return instance

    # ── context manager ──────────────────────────────────────────────

    def __enter__(self) -> GistFS:
        self.sync()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:  # noqa: ANN001
        self._cache = None
        return None

    # ── public API ───────────────────────────────────────────────────

    def sync(self) -> None:
        """Fetch the latest gist state from GitHub."""
        resp = self._get_request()
        resp.raise_for_status()
        gist = resp.json()
        self._cache = {}
        for fname, fdata in gist.get("files", {}).items():
            raw = fdata["content"]
            if self.encryption_key:
                raw = self._decrypt(raw)
            try:
                self._cache[fname] = json.loads(raw)
            except (json.JSONDecodeError, TypeError):
                self._cache[fname] = raw

    def read(self, filename: str) -> Any:
        """Read and return the parsed content of *filename*."""
        self._ensure_synced()
        assert self._cache is not None
        if filename not in self._cache:
            raise FileNotFoundError(f"{filename!r} not found in gist {self.gist_id}")
        return self._cache[filename]

    def write(self, filename: str, data: Any) -> None:
        """Write *data* (JSON-serializable) to *filename* in the gist."""
        content = json.dumps(data, ensure_ascii=False, default=str)
        if self.encryption_key:
            content = self._encrypt(content)
        payload = {"files": {filename: {"content": content}}}
        resp = self._patch_request(payload)
        resp.raise_for_status()
        # Update local cache
        self._ensure_synced()
        assert self._cache is not None
        self._cache[filename] = data

    def delete(self, filename: str) -> bool:
        """Delete *filename* from the gist.  Returns True if it existed."""
        self._ensure_synced()
        assert self._cache is not None
        if filename not in self._cache:
            return False
        # GitHub API: setting content to empty string with null deletes the file
        payload = {"files": {filename: None}}
        resp = self._patch_request(payload)
        resp.raise_for_status()
        self._cache.pop(filename, None)
        return True

    def list_files(self) -> list[str]:
        """Return a list of filenames in the gist."""
        self._ensure_synced()
        assert self._cache is not None
        return list(self._cache.keys())

    def exists(self, filename: str) -> bool:
        """Check whether *filename* exists in the gist."""
        self._ensure_synced()
        assert self._cache is not None
        return filename in self._cache

    def read_all(self) -> dict[str, Any]:
        """Return all files as a ``{filename: content}`` dict."""
        self._ensure_synced()
        assert self._cache is not None
        return dict(self._cache)

    def open(self, filename: str, mode: str = "r") -> GistFile:
        """Open a file in the gist, returning a file-like object.

        Supported modes: ``"r"`` (read), ``"w"`` (write), ``"a"`` (append),
        ``"r+"`` (read and write).

        Usage::

            with gfs.open("notes.txt", "w") as f:
                f.write("hello world")

            with gfs.open("notes.txt", "r") as f:
                content = f.read()
        """
        if mode not in ("r", "w", "a", "r+"):
            raise ValueError(f"Unsupported mode {mode!r} — use 'r', 'w', 'a', or 'r+'")
        return GistFile(self, filename, mode)

    # ── helpers ──────────────────────────────────────────────────────

    def _encrypt(self, plaintext: str) -> str:
        """Encrypt and base64-encode *plaintext*."""
        from .crypto import encrypt
        return encrypt(plaintext, self.encryption_key)

    def _decrypt(self, ciphertext: str) -> str:
        """Decode and decrypt *ciphertext*."""
        from .crypto import decrypt
        return decrypt(ciphertext, self.encryption_key)

    def _ensure_synced(self) -> None:
        if self._cache is None:
            if self.auto_sync:
                self.sync()
            else:
                raise RuntimeError("GistFS not synced — call .sync() first")

    def _headers(self, *, auth: bool = True) -> dict[str, str]:
        headers = {"Accept": "application/vnd.github+json"}
        if auth and self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    def _get_request(self) -> requests.Response:
        return requests.get(self._url, headers=self._headers(auth=bool(self.token)))

    def _patch_request(self, payload: dict) -> requests.Response:
        if not self.token:
            raise ValueError(
                "A GitHub token is required for write operations. "
                "Set GITHUB_TOKEN or pass token= to GistFS()."
            )
        return requests.patch(self._url, headers=self._headers(), json=payload)

    def __repr__(self) -> str:
        return f"GistFS(gist_id={self.gist_id!r})"


class GistFile(io.StringIO):
    """File-like object for a single file in a gist.

    Wraps :class:`io.StringIO` so that standard file operations
    (``read``, ``write``, ``seek``, ``tell``, iteration) work as expected.
    On :meth:`close` (or exiting the context manager), any writes are
    flushed back to the gist.

    Do not instantiate directly — use :meth:`GistFS.open` instead.
    """

    def __init__(self, gfs: GistFS, filename: str, mode: str) -> None:
        self._gfs = gfs
        self._filename = filename
        self._mode = mode
        self._writable = mode in ("w", "a", "r+")

        # Seed the buffer with existing content for read / append / r+
        initial = ""
        if mode in ("r", "a", "r+"):
            try:
                content = gfs.read(filename)
                if isinstance(content, str):
                    initial = content
                else:
                    initial = json.dumps(content, ensure_ascii=False, default=str)
            except FileNotFoundError:
                if mode == "r":
                    raise
                # "a" and "r+" start empty if file doesn't exist

        super().__init__(initial)

        # Position cursor at end for append, at start for read/r+
        if mode == "a":
            self.seek(0, io.SEEK_END)
        else:
            self.seek(0)

    @property
    def name(self) -> str:
        return self._filename

    @property
    def mode(self) -> str:
        return self._mode

    def writable(self) -> bool:
        return self._writable

    def readable(self) -> bool:
        return self._mode in ("r", "r+")

    def write(self, s: str) -> int:
        if not self._writable:
            raise io.UnsupportedOperation("not writable")
        return super().write(s)

    def read(self, size: int = -1) -> str:
        if self._mode == "w":
            raise io.UnsupportedOperation("not readable")
        return super().read(size)

    def readline(self, size: int = -1) -> str:
        if self._mode == "w":
            raise io.UnsupportedOperation("not readable")
        return super().readline(size)

    def readlines(self, hint: int = -1) -> list[str]:
        if self._mode == "w":
            raise io.UnsupportedOperation("not readable")
        return super().readlines(hint)

    def close(self) -> None:
        if not self.closed and self._writable:
            self._flush_to_gist()
        super().close()

    def _flush_to_gist(self) -> None:
        """Push the buffer content to the gist as a raw string."""
        content = self.getvalue()
        if not content:
            return
        raw = content
        if self._gfs.encryption_key:
            raw = self._gfs._encrypt(raw)
        payload = {"files": {self._filename: {"content": raw}}}
        resp = self._gfs._patch_request(payload)
        resp.raise_for_status()
        # Update cache
        self._gfs._ensure_synced()
        assert self._gfs._cache is not None
        try:
            self._gfs._cache[self._filename] = json.loads(content)
        except (json.JSONDecodeError, ValueError):
            self._gfs._cache[self._filename] = content

    def __repr__(self) -> str:
        state = "closed" if self.closed else self._mode
        return f"GistFile({self._filename!r}, {state!r})"
