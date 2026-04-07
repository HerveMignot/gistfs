"""Encryption helpers for GistFS — Fernet symmetric encryption with base64 encoding.

Requires the ``cryptography`` package::

    pip install gistfs[encryption]
"""

from __future__ import annotations

import base64
import os


def _get_fernet(key: str):
    """Return a Fernet instance, raising a helpful error if cryptography is missing."""
    try:
        from cryptography.fernet import Fernet
    except ImportError:
        raise ImportError(
            "The 'cryptography' package is required for encryption. "
            "Install it with: pip install gistfs[encryption]"
        ) from None
    return Fernet(key.encode())


def generate_key() -> str:
    """Generate a new Fernet encryption key and return it as a URL-safe base64 string."""
    try:
        from cryptography.fernet import Fernet
    except ImportError:
        raise ImportError(
            "The 'cryptography' package is required for encryption. "
            "Install it with: pip install gistfs[encryption]"
        ) from None
    return Fernet.generate_key().decode()


def derive_key(passphrase: str, salt: bytes | None = None) -> tuple[str, bytes]:
    """Derive a Fernet key from a passphrase using PBKDF2.

    Returns ``(key, salt)`` — store the salt alongside the key so you can
    re-derive later with the same passphrase.
    """
    try:
        from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
        from cryptography.hazmat.primitives import hashes
    except ImportError:
        raise ImportError(
            "The 'cryptography' package is required for encryption. "
            "Install it with: pip install gistfs[encryption]"
        ) from None

    if salt is None:
        salt = os.urandom(16)
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=480_000,
    )
    key = base64.urlsafe_b64encode(kdf.derive(passphrase.encode()))
    return key.decode(), salt


def encrypt(plaintext: str, key: str) -> str:
    """Encrypt *plaintext* and return a base64-encoded ciphertext string."""
    f = _get_fernet(key)
    return base64.urlsafe_b64encode(f.encrypt(plaintext.encode())).decode()


def decrypt(ciphertext: str, key: str) -> str:
    """Decrypt a base64-encoded *ciphertext* string back to plaintext."""
    f = _get_fernet(key)
    return f.decrypt(base64.urlsafe_b64decode(ciphertext.encode())).decode()
