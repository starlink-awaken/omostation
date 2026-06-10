#!/usr/bin/env python3
"""Shared utility functions for OMO modules.

Consolidates duplicate boilerplate (UTC timestamps, YAML loading, I/O wrappers)
that was previously copy-pasted across omo_phase14/15/16 and other modules.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from .omo_io import write_text_atomic, write_yaml_atomic


def utc_now() -> str:
    """Return current UTC time as ISO-8601 string with Z suffix."""
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def load_yaml(path: Path) -> dict[str, Any]:
    """Read and parse a YAML file, returning {} if file is empty or missing."""
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def load_yaml_required(path: Path) -> dict[str, Any]:
    """Read and parse a YAML file, raising if file doesn't exist."""
    if not path.exists():
        raise FileNotFoundError(f"Required file not found: {path}")
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def write_yaml(path: Path, data: Any) -> None:
    """Write data as YAML atomically."""
    write_yaml_atomic(path, data)


def write_text(path: Path, text: str) -> None:
    """Write text atomically."""
    write_text_atomic(path, text)
