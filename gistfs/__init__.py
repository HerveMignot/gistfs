"""gistfs — Use GitHub Gists as a persistent key-value filesystem for AI agents."""

from .core import GistFS, GistFile
from .crypto import generate_key, derive_key
from .memory import GistMemory

__all__ = ["GistFS", "GistFile", "GistMemory", "generate_key", "derive_key"]
__version__ = "0.2.0"
