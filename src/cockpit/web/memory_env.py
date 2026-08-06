"""Load Memory OS / Neo4j env for cockpit process and mos subprocesses.

Does not overwrite non-empty existing environment variables.
"""

from __future__ import annotations

import os
from collections.abc import Iterable
from pathlib import Path

from cockpit.compat import WORKSPACE_ROOT

_DEFAULTS: dict[str, str] = {
    "NEO4J_URI": "bolt://localhost:7687",
    "NEO4J_USER": "neo4j",
    "NEO4J_PASSWORD": "changeme",
    "NEO4J_HTTP_PORT": "7474",
    "NEO4J_BOLT_PORT": "7687",
    "MOS_TEMPORAL": "1",
    "MOS_RBAC": "1",
    "MOS_MEM0": "0",
    "MOS_GRAPHITI": "0",
}

_APPLIED = False


def _candidate_files(root: Path) -> list[Path]:
    """Later files override earlier (local secrets win over example defaults).

    Process non-empty env still wins in apply_memory_os_env (ops contract).
    Order matches .omo/standards/memory-os-ops.md inverted for merge-then-apply:
    example → cockpit .env → config/memory-os.env.
    """
    return [
        root / "docs" / "operations" / "memory-os.env.example",
        root / "projects" / "cockpit" / ".env",
        root / "config" / "memory-os.env",
    ]


def _parse_env_file(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    if not path.is_file():
        return out
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return out
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, _, val = line.partition("=")
        key = key.strip()
        val = val.strip().strip('"').strip("'")
        if key:
            out[key] = val
    return out


def apply_memory_os_env(
    *,
    root: Path | None = None,
    force: bool = False,
) -> dict[str, str]:
    """Merge defaults + env files into os.environ; return effective MOS-related keys."""
    global _APPLIED
    if _APPLIED and not force:
        return {
            k: os.environ.get(k, "")
            for k in list(_DEFAULTS) + ["MOS_HTTP_TIMEOUT", "MOS_STORE_PATH", "MOS_RBAC_PATH"]
            if os.environ.get(k)
        }

    workspace = Path(root or WORKSPACE_ROOT)
    merged: dict[str, str] = dict(_DEFAULTS)
    for path in _candidate_files(workspace):
        merged.update(_parse_env_file(path))

    applied: dict[str, str] = {}
    for key, val in merged.items():
        cur = os.environ.get(key)
        if cur is None or cur == "":
            os.environ[key] = val
            applied[key] = val
        else:
            applied[key] = cur

    _APPLIED = True
    return applied


def mos_subprocess_env(extra: dict[str, str] | None = None) -> dict[str, str]:
    """Env dict for `python -m mos` child processes."""
    apply_memory_os_env()
    env = {**os.environ, "MOS_STDIO": "1"}
    if extra:
        env.update(extra)
    # Prefer neo4j extra when URI configured so driver is available
    if env.get("NEO4J_URI"):
        # uv --with neo4j is handled by caller argv; keep flag for diagnostics
        env.setdefault("MOS_NEO4J_EXTRA", "1")
    return env


def mos_uv_extra_args() -> list[str]:
    """Return uv CLI extras when Neo4j is configured."""
    apply_memory_os_env()
    if (os.environ.get("NEO4J_URI") or "").strip():
        return ["--with", "neo4j"]
    return []
