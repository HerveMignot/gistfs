"""Core GistFS class — use GitHub Gists as a persistent key-value filesystem."""

from __future__ import annotations

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
    ) -> None:
        self.gist_id = gist_id
        self.token = token or os.environ.get("GITHUB_TOKEN", "")
        self.auto_sync = auto_sync
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
            files_payload = {
                fname: {"content": json.dumps(data, ensure_ascii=False, default=str)}
                for fname, data in init_files.items()
            }
        else:
            files_payload = {"_gistfs.json": {"content": "{}"}}

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
        instance = cls(gist_id, token=resolved_token)
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
            try:
                self._cache[fname] = json.loads(fdata["content"])
            except (json.JSONDecodeError, TypeError):
                self._cache[fname] = fdata["content"]

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

    # ── helpers ──────────────────────────────────────────────────────

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
