"""Shared utilities for swarm_engine modules — migrated from bin/ssot/_shared.py.

Provides ROOT path, UTC timestamp, YAML loading, and JSONL I/O helpers
that the migrated scripts (risk_engine, trust_adjuster, workers/*, etc.)
depend on.
"""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

# Workspace root: packages/swarm/src/swarm_engine/_shared.py
# → parents[5] = workspace root (swarm_engine → src → swarm → packages → aetherforge → projects → workspace)
_ROOT_OVERRIDE = os.environ.get("WORKSPACE_ROOT", "")
ROOT = Path(_ROOT_OVERRIDE) if _ROOT_OVERRIDE else Path(__file__).resolve().parents[5]


def utc_now() -> str:
    """UTC ISO-8601 timestamp."""
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_yaml(path: Path | str) -> Any:
    """Safe YAML loading."""
    p = Path(path)
    if not p.exists():
        return None
    with open(p) as f:
        return yaml.safe_load(f)


def load_yaml_value(path: Path | str) -> Any:
    """Alias for load_yaml — backward compat with omo_shared."""
    return load_yaml(path)


def append_jsonl(path: Path | str, record: dict) -> None:
    """Append a record to JSONL file."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "a") as f:
        f.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")


def read_jsonl(path: Path | str) -> list[dict]:
    """Read JSONL file tolerantly."""
    p = Path(path)
    if not p.exists():
        return []
    results = []
    with open(p) as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    results.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    return results
