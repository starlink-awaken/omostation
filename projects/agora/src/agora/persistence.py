"""Shared JSON persistence — used by registry, event_bus, and market."""

from __future__ import annotations

import json
from pathlib import Path

import structlog

logger = structlog.get_logger(__name__)


def json_load(path: Path, default=None) -> dict | list:
    """Load JSON from path, returning default on failure."""
    try:
        return json.loads(path.read_text())
    except FileNotFoundError:
        return default if default is not None else {}
    except Exception as e:
        logger.warning("persistence_load_failed", path=str(path), error=str(e))
    return default if default is not None else {}


def json_save(path: Path, data: dict | list) -> bool:
    """Save data as JSON to path. Returns True on success."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False, default=str))
        return True
    except Exception as e:
        logger.warning("persistence_save_failed", path=str(path), error=str(e))
        return False
