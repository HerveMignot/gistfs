"""Tests for encryption/decryption of gist file content."""

import requests

from gistfs import GistFS, generate_key
from gistfs.crypto import encrypt, decrypt


class TestCryptoHelpers:
    def test_roundtrip(self):
        """encrypt then decrypt returns the original string."""
        key = generate_key()
        plaintext = '{"secret": "value"}'
        ciphertext = encrypt(plaintext, key)
        assert ciphertext != plaintext
        assert decrypt(ciphertext, key) == plaintext

    def test_different_keys_produce_different_ciphertext(self):
        key1 = generate_key()
        key2 = generate_key()
        plaintext = "hello"
        assert encrypt(plaintext, key1) != encrypt(plaintext, key2)


class TestGistFSEncryption:
    def test_write_and_read_encrypted(self, github_token):
        """Data written with encryption_key is decrypted transparently on read."""
        key = generate_key()
        gfs = GistFS.create(
            description="[gistfs-test] encryption test",
            token=github_token,
            encryption_key=key,
        )
        try:
            gfs.write("secret.json", {"api_key": "sk-123"})
            assert gfs.read("secret.json") == {"api_key": "sk-123"}
        finally:
            gfs.delete_gist()

    def test_raw_content_is_encrypted_on_github(self, github_token):
        """The raw file content stored in the gist is not plaintext JSON."""
        key = generate_key()
        gfs = GistFS.create(
            description="[gistfs-test] encryption raw check",
            token=github_token,
            encryption_key=key,
        )
        try:
            gfs.write("secret.json", {"password": "hunter2"})

            # Fetch the gist directly without decryption
            resp = requests.get(
                f"https://api.github.com/gists/{gfs.gist_id}",
                headers={
                    "Authorization": f"Bearer {github_token}",
                    "Accept": "application/vnd.github+json",
                },
            )
            raw_content = resp.json()["files"]["secret.json"]["content"]
            assert "hunter2" not in raw_content
            assert "password" not in raw_content

            # But decrypting it manually gives back the original JSON
            decrypted = decrypt(raw_content, key)
            assert '"password"' in decrypted
            assert '"hunter2"' in decrypted
        finally:
            gfs.delete_gist()

    def test_context_manager_with_encryption(self, github_token):
        """Encryption works through the context manager (sync decrypts)."""
        key = generate_key()
        gfs = GistFS.create(
            description="[gistfs-test] encryption ctx",
            token=github_token,
            encryption_key=key,
        )
        try:
            gfs.write("data.json", {"count": 42})

            # Re-open with context manager — sync should decrypt
            with GistFS(gfs.gist_id, token=github_token, encryption_key=key) as gfs2:
                assert gfs2.read("data.json") == {"count": 42}
        finally:
            gfs.delete_gist()

    def test_gistfile_encryption(self, github_token):
        """GistFile (open) encrypts on flush and decrypts on read."""
        key = generate_key()
        gfs = GistFS.create(
            description="[gistfs-test] gistfile encryption",
            token=github_token,
            encryption_key=key,
        )
        try:
            with gfs.open("notes.txt", "w") as f:
                f.write("top secret note")

            # Re-sync to pick up the encrypted content from API
            gfs.sync()

            with gfs.open("notes.txt", "r") as f:
                assert f.read() == "top secret note"
        finally:
            gfs.delete_gist()
