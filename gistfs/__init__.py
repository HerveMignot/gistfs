"""gistfs — Use GitHub Gists as a persistent key-value filesystem for AI agents."""

from .core import GistFS, GistFile
from .memory import GistMemory

__all__ = ["GistFS", "GistFile", "GistMemory"]
__version__ = "0.1.0"
