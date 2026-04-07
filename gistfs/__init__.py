"""gistfs — Use GitHub Gists as a persistent key-value filesystem for AI agents."""

from .core import GistFS, GistFile
from .memory import GistMemory

__all__ = ["GistFS", "GistFile", "GistMemory"]

try:
    from .crypto import generate_key, derive_key
    __all__ += ["generate_key", "derive_key"]
except ImportError:
    pass
__version__ = "0.3.0"
