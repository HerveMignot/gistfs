"""gistfs — Use GitHub Gists as a persistent key-value filesystem for AI agents."""

from .core import GistFS
from .memory import GistMemory

__all__ = ["GistFS", "GistMemory"]
__version__ = "0.1.0"
