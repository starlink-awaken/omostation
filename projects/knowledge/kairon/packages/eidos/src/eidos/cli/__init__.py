"""Compatibility exports for ``eidos.cli`` package imports."""

from .cli import *  # noqa: F403
from .cli import main

__all__ = [*globals().get("__all__", []), "main"]  # noqa: PLE0604
