"""Shared utilities for bin/ssot/ scripts.

Consolidates patterns duplicated across 15+ scripts:
  - ROOT: workspace root path constant
  - load_yaml: safe multi-doc YAML loading
  - append_jsonl: fcntl-locked JSONL append
  - read_jsonl: tolerant JSONL reader
  - utc_now: UTC ISO-8601 timestamp
  - check_evidence: verify evidence_refs point to existing files
  - is_runnable_cmd / run_verification: verification command helpers

Design: sibling scripts import via ``from _shared import ...``.
Python adds the script's directory to sys.path[0] automatically,
so sibling imports work without any sys.path manipulation.
"""

from __future__ import annotations

import fcntl
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[2]


# ── YAML ─────────────────────────────────────────────────────────────

def load_yaml(path: Path) -> dict[str, Any]:
    """Load a YAML file, gracefully handling multi-doc. Returns {} if missing or empty.

    Only dict-rooted YAML documents are supported (the last doc wins for
    multi-doc files).  List-rooted YAML returns {} with a warning — callers
    that need list data should use yaml.safe_load_all directly.
    """
    if not path.exists():
        return {}
    docs = [d for d in yaml.safe_load_all(path.read_text(encoding="utf-8")) if d is not None]
    if not docs:
        return {}
    body = docs[-1]
    if not isinstance(body, dict):
        import warnings
        warnings.warn(f"YAML root is not a dict in {path}, returning empty dict", stacklevel=2)
        return {}
    return body


# ── JSONL I/O ────────────────────────────────────────────────────────

def append_jsonl(path: Path, entry: dict[str, Any]) -> None:
    """Append one JSON object as a JSONL line with fcntl locking (cross-process safe)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        fcntl.flock(f.fileno(), fcntl.LOCK_EX)
        try:
            f.write(json.dumps(entry, ensure_ascii=False, sort_keys=True) + "\n")
            f.flush()
        finally:
            fcntl.flock(f.fileno(), fcntl.LOCK_UN)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    """Read a JSONL file. Returns [] if missing. Tolerates malformed lines."""
    if not path.exists():
        return []
    entries: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").strip().split("\n"):
        if not line.strip():
            continue
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return entries


# ── Time ─────────────────────────────────────────────────────────────

def utc_now() -> str:
    """Return current UTC time as ISO-8601 with Z suffix, second precision.

    Microseconds are truncated intentionally — suitable for human-readable
    logs and display.  Not suitable for sort-order guarantees (two writes
    within the same second share a timestamp); use append-order / seqno
    for ordering.
    """


# ── Verification helpers ─────────────────────────────────────────────

def check_evidence(data: dict, root: Path) -> tuple[int, bool]:
    """Check whether evidence_refs point to existing files.

    Returns (ref_count, found_any).  Used by verify.py to detect
    "resolved but no evidence" fraud.
    """
    refs = data.get("evidence_refs") or []
    if not refs:
        return 0, False
    found = False
    for ref in refs:
        p = Path(ref)
        if not p.is_absolute():
            p = root / ref
        if p.exists():
            found = True
    return len(refs), found


def is_runnable_cmd(cmd: str) -> bool:
    """Check whether a verification_cmd is a real runnable shell command.

    Filters out comments, empty strings, and Chinese-text placeholders
    like '长期目标: ...' or '检查: ...'.
    """
    cmd = cmd.strip()
    if not cmd or cmd.startswith("#"):
        return False
    if "长期目标" in cmd or "检查" in cmd:
        return False
    return True


def run_verification(
    cmd: str, root: Path, *, timeout: int = 30
) -> tuple[bool | None, str | None]:
    """Run a verification command via subprocess.

    Returns (passed_or_None, error_tail_or_None).  The command is run
    via ``shell=True`` with timeout; stderr tail (last 300 chars) is
    captured on failure.
    """
    try:
        proc = subprocess.run(
            cmd, shell=True, cwd=root, capture_output=True, text=True,
            timeout=timeout, check=False,
        )
        return proc.returncode == 0, (proc.stderr[-300:] if proc.returncode != 0 else None)
    except Exception as exc:
        return False, str(exc)
