#!/usr/bin/env python3
"""CR-X4-MEMORY-OS-SURFACE-INTEGRITY: Memory OS light gate (blocking).

Validates SSOT files, env keys, ports, CLI/smoke surfaces, and help catalog test.
Exit 0 = pass; exit 1 = hard fail (CI / make memory-os-check).
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

# Required SSOT / ops surfaces (must exist for Memory OS to be "declared")
REQUIRED_PATHS = [
    ".omo/_truth/registry/memory-os.yaml",
    ".omo/_truth/registry/memory-rbac.yaml",
    ".omo/standards/memory-os-ops.md",
    ".omo/_knowledge/decisions/0372-memory-os-control-plane.md",
    "docs/architecture/memory-os.md",
    "docs/operations/memory-os-neo4j-local.md",
    "docs/operations/memory-os.env.example",
    "docs/operations/memory-os-epic-retro.md",
    "bin/memory-os-env.sh",
    "bin/memory-os-neo4j-up.sh",
    "bin/memory-os-smoke.sh",
    "bin/memory-os-asof-seed.sh",
    "bin/gac/check-memory-os-surfaces.py",
    ".agents/skills/memory-recall/SKILL.md",
    "projects/kairon/packages/mos/pyproject.toml",
    "projects/cockpit/src/cockpit/commands/help_map.py",
    "projects/cockpit/src/cockpit/tests/test_help_discover_ssot.py",
    "projects/cockpit/src/cockpit/tests/test_status_memory_os_line.py",
    "protocols/port-registry.yaml",
]

REQUIRED_ENV_KEYS = (
    "NEO4J_URI",
    "NEO4J_USER",
    "NEO4J_PASSWORD",
    "NEO4J_HTTP_PORT",
    "NEO4J_BOLT_PORT",
)

REQUIRED_PORTS = (7474, 7687)


def _read(rel: str) -> str | None:
    p = REPO_ROOT / rel
    if not p.is_file():
        return None
    try:
        return p.read_text(encoding="utf-8")
    except OSError:
        return None


def check_required_paths() -> list[str]:
    missing: list[str] = []
    for rel in REQUIRED_PATHS:
        if not (REPO_ROOT / rel).is_file():
            missing.append(rel)
    return missing


def check_env_example() -> list[str]:
    errs: list[str] = []
    text = _read("docs/operations/memory-os.env.example")
    if text is None:
        return ["docs/operations/memory-os.env.example unreadable"]
    for key in REQUIRED_ENV_KEYS:
        if not re.search(rf"(?m)^{re.escape(key)}=", text):
            errs.append(f"env.example missing key: {key}")
    return errs


def check_cockpit_env_example() -> list[str]:
    errs: list[str] = []
    text = _read("projects/cockpit/.env.example")
    if text is None:
        # cockpit submodule may be sparse in some checkouts — soft fail only if path missing entirely
        return ["projects/cockpit/.env.example missing"]
    for key in ("NEO4J_URI", "NEO4J_USER", "NEO4J_PASSWORD"):
        if key not in text:
            errs.append(f"cockpit .env.example missing: {key}")
    return errs


def check_ports() -> list[str]:
    errs: list[str] = []
    text = _read("protocols/port-registry.yaml")
    if text is None:
        return ["protocols/port-registry.yaml unreadable"]
    for port in REQUIRED_PORTS:
        # Accept either bare key "  7474:" or env map form
        if not re.search(rf"(?m)^\s*{port}\s*:", text) and f"{port}" not in text:
            errs.append(f"port {port} not registered in port-registry.yaml")
    # Prefer explicit neo4j naming when present
    if "neo4j" not in text.lower() and "NEO4J" not in text:
        errs.append("port-registry.yaml has no neo4j/NEO4J mention")
    return errs


def check_registry_ssot() -> list[str]:
    errs: list[str] = []
    text = _read(".omo/_truth/registry/memory-os.yaml")
    if text is None:
        return ["memory-os.yaml unreadable"]
    for needle in (
        "id: memory-os",
        "surface_check:",
        "bos://memory/mos/",
        "phase10",
    ):
        if needle not in text:
            errs.append(f"memory-os.yaml missing marker: {needle}")
    return errs


def check_help_catalog_mentions_memory() -> list[str]:
    errs: list[str] = []
    text = _read("projects/cockpit/src/cockpit/commands/help_map.py")
    if text is None:
        return ["help_map.py unreadable"]
    if 'name="memory"' not in text and "name='memory'" not in text and 'CmdRow("memory"' not in text:
        # accept various row constructors
        if not re.search(r'["\']memory["\']', text):
            errs.append("help_map.py does not catalog 'memory' command")
    return errs


def main() -> int:
    hard: list[str] = []
    soft: list[str] = []

    missing = check_required_paths()
    if missing:
        hard.extend(f"missing required path: {m}" for m in missing)

    hard.extend(check_env_example())
    hard.extend(check_ports())
    hard.extend(check_registry_ssot())
    hard.extend(check_help_catalog_mentions_memory())

    cockpit_env = check_cockpit_env_example()
    # cockpit env is required when submodule is present
    if (REPO_ROOT / "projects/cockpit").is_dir():
        hard.extend(cockpit_env)
    else:
        soft.extend(cockpit_env)

    print("Memory OS light gate (CR-X4-MEMORY-OS-SURFACE-INTEGRITY)")
    print(f"  required_paths: {len(REQUIRED_PATHS)}")
    if soft:
        print(f"  soft warnings ({len(soft)}):")
        for s in soft:
            print(f"    WARN {s}")
    if hard:
        print(f"  HARD FAIL ({len(hard)}):")
        for h in hard:
            print(f"    FAIL {h}")
        print("  fix: restore SSOT/ops surfaces listed in .omo/standards/memory-os-ops.md")
        return 1

    print("  OK all required Memory OS surfaces present")
    print("  OK env.example keys + ports + registry + help catalog")
    return 0


if __name__ == "__main__":
    sys.exit(main())
