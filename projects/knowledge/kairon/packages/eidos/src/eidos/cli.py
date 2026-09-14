"""Compatibility stub for the historical ``eidos.cli`` module."""

from eidos.cli.cli import *  # noqa: F403
from eidos.cli.cli import main

__all__ = [*globals().get("__all__", []), "main"]  # noqa: PLE0604
