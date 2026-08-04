#!/usr/bin/env python3
"""GaC surface check: Memory OS SSOT / ports / env example / ops docs (Phase 8).

Validates declaration integrity — does not require Neo4j to be running.
Exit 0 on pass, 1 on hard fail.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

REQUIRED_FILES = [
    ".omo/_truth/registry/memory-os.yaml",
    ".omo/_truth/registry/memory-rbac.yaml",
    ".omo/standards/memory-os-ops.md",
    "docs/architecture/memory-os.md",
    "docs/operations/memory-os-neo4j-local.md",
    "docs/operations/memory-os.env.example",
    "docs/operations/memory-os-adapter-audit.md",
    "bin/memory-os-neo4j-up.sh",
    "bin/memory-os-env.sh",
    ".agents/skills/memory-recall/SKILL.md",
    "projects/kairon/packages/mos/src/mos/neo4j_writer.py",
    "projects/kairon/packages/mos/src/mos/rbac.py",
    "projects/kairon/packages/mos/docker-compose.yml",
]

REQUIRED_ENV_KEYS = [
    "NEO4J_URI",
    "NEO4J_USER",
    "NEO4J_PASSWORD",
    "MOS_TEMPORAL",
    "MOS_RBAC",
]

REQUIRED_PORTS = {7474: "neo4j-http", 7687: "neo4j-bolt"}


def _load_port_registry() -> dict:
    path = ROOT / "protocols" / "port-registry.yaml"
    if not path.is_file():
        return {}
    try:
        import yaml  # type: ignore

        return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception:
        # minimal parse for ports section keys
        text = path.read_text(encoding="utf-8")
        ports: dict[int, str] = {}
        for line in text.splitlines():
            line = line.strip()
            if line[:1].isdigit() and ":" in line:
                num = line.split(":", 1)[0].strip()
                if num.isdigit():
                    ports[int(num)] = line
        return {"ports": {str(k): {"name": v} for k, v in ports.items()}, "_raw": True}


def main() -> int:
    errors: list[str] = []
    warns: list[str] = []

    for rel in REQUIRED_FILES:
        p = ROOT / rel
        if not p.is_file():
            errors.append(f"missing_file:{rel}")

    env_ex = ROOT / "docs/operations/memory-os.env.example"
    if env_ex.is_file():
        text = env_ex.read_text(encoding="utf-8")
        for key in REQUIRED_ENV_KEYS:
            if key not in text:
                errors.append(f"env_example_missing_key:{key}")

    reg = _load_port_registry()
    ports = reg.get("ports") or {}
    env_vars = reg.get("env_vars") or {}
    for port, name in REQUIRED_PORTS.items():
        key = str(port)
        entry = ports.get(port) or ports.get(key)
        if not entry:
            errors.append(f"port_unregistered:{port}({name})")
        env_key = env_vars.get(port) or env_vars.get(key)
        if not env_key:
            warns.append(f"port_env_var_missing:{port}")

    mos = ROOT / ".omo/_truth/registry/memory-os.yaml"
    if mos.is_file():
        body = mos.read_text(encoding="utf-8")
        for needle in ("env_defaults", "neo4j", "phase7", "rbac_policy"):
            if needle not in body:
                warns.append(f"memory-os.yaml_missing_marker:{needle}")

    cockpit_env = ROOT / "projects/cockpit/.env.example"
    if cockpit_env.is_file():
        ctext = cockpit_env.read_text(encoding="utf-8")
        if "NEO4J_URI" not in ctext:
            errors.append("cockpit_.env.example_missing_NEO4J_URI")

    if errors:
        print(f"FAIL memory-os surfaces ({len(errors)} errors, {len(warns)} warns)")
        for e in errors:
            print(f"  ERROR {e}")
        for w in warns:
            print(f"  WARN  {w}")
        return 1

    print(f"OK memory-os surfaces ({len(REQUIRED_FILES)} files, ports 7474/7687 registered)")
    for w in warns:
        print(f"  WARN  {w}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
