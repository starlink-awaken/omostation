"""Compatibility stub for the historical ``eidos.schema`` module."""

from eidos.core.schema import *  # noqa: F403
from eidos.core.schema import _SCHEMA_MIGRATIONS

__all__ = [*globals().get("__all__", []), "_SCHEMA_MIGRATIONS"]  # noqa: PLE0604
