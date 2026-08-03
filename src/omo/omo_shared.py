#!/usr/bin/env python3
"""Shared utility functions for OMO modules.

Consolidates duplicate boilerplate (UTC timestamps, YAML loading, I/O wrappers)
that was previously copy-pasted across omo_phase14/15/16 and other modules.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

from .omo_io import write_text_atomic, write_yaml_atomic


def load_yaml_value_docs(text: str) -> Any:
    """Parse YAML text, preserving list payloads and merging multi-doc values."""
    docs = [doc for doc in yaml.safe_load_all(text) if doc is not None]
    if not docs:
        return {}
    if len(docs) == 1:
        return docs[0]
    if all(isinstance(doc, dict) for doc in docs):
        merged: dict[str, Any] = {}
        for doc in docs:
            merged.update(doc)
        return merged
    if all(isinstance(doc, list) for doc in docs):
        merged_list: list[Any] = []
        for doc in docs:
            merged_list.extend(doc)
        return merged_list
    return docs[-1]


def load_yaml_docs(text: str) -> dict[str, Any]:
    """Parse YAML text and merge multi-document frontmatter/body payloads."""
    payload = load_yaml_value_docs(text)
    return payload if isinstance(payload, dict) else {}


def utc_now() -> str:
    """Return current UTC time as ISO-8601 string with Z suffix."""
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_yaml(path: Path) -> dict[str, Any]:
    """Read and parse a YAML file, returning {} if file is empty or missing."""
    if not path.exists():
        return {}
    return load_yaml_docs(path.read_text(encoding="utf-8"))


def load_yaml_required(path: Path) -> dict[str, Any]:
    """Read and parse a YAML file, raising if file doesn't exist."""
    if not path.exists():
        raise FileNotFoundError(f"Required file not found: {path}")
    return load_yaml_docs(path.read_text(encoding="utf-8"))


def load_yaml_value(path: Path) -> Any:
    """Read and parse a YAML file, preserving top-level list payloads."""
    if not path.exists():
        return {}
    return load_yaml_value_docs(path.read_text(encoding="utf-8"))


def load_yaml_value_required(path: Path) -> Any:
    """Read and parse a YAML file, preserving top-level list payloads."""
    if not path.exists():
        raise FileNotFoundError(f"Required file not found: {path}")
    return load_yaml_value_docs(path.read_text(encoding="utf-8"))


def write_yaml(path: Path, data: Any) -> None:
    """Write data as YAML atomically."""
    write_yaml_atomic(path, data)


def write_text(path: Path, text: str) -> None:
    """Write text atomically."""
    write_text_atomic(path, text)
