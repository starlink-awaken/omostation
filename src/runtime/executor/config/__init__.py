"""Reload-safe facade for runtime.executor.config.config."""

from __future__ import annotations

import importlib

from . import config as _config

importlib.reload(_config)

from .config import *  # noqa: F403

REGISTRY_PATH = _config.REGISTRY_PATH


def _sync_overrides() -> None:
    _config.REGISTRY_PATH = REGISTRY_PATH


def _load_registry():
    _sync_overrides()
    return _config._load_registry()


def _query_registry_port(known_names):
    _sync_overrides()
    return _config._query_registry_port(known_names)
