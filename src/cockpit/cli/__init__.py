"""Cockpit CLI package — split from monolithic cli.py (T6-10)."""

from ._subcommands import register_subcommands

__all__ = ["register_subcommands"]
