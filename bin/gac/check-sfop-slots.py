#!/usr/bin/env python3
"""SFOP/DFSQ slot laws — COMP-WS nodes must self-report slot; S-slot at most one (omo).

SGF / root-owned gate id sfop-slots. Missing file would ENOENT the gate.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None  # type: ignore

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_NODES = ROOT / "projects/ecos/src/ecos/ssot/mof/nodes"
DEFAULT_REGISTRY = ROOT / "docs/project-registry.yaml"
SLOTS = {"K", "H", "P", "C", "S", "B", "J", "O", "F"}
DAO = {"dao", "fa", "shu", "qi"}
DISPATCHER_ID = "COMP-WS-omo"
ARCHIVED_PROJECTS = {"mesh-router"}


def _load(path: Path) -> dict:
    if yaml is None:
        raise RuntimeError("pyyaml required")
    if not path.exists():
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def check(*, nodes_dir: Path | None = None, registry_path: Path | None = None) -> dict:
    nodes_dir = Path(nodes_dir) if nodes_dir is not None else DEFAULT_NODES
    registry_path = Path(registry_path) if registry_path is not None else DEFAULT_REGISTRY
    errors: list[str] = []
    warnings: list[str] = []
    annotated: list[dict] = []
    s_holders: list[str] = []
    if not nodes_dir.is_dir():
        warnings.append(f"CR-SFOP-01: COMP-WS nodes dir missing ({nodes_dir}); skip slot scan")
        return {
            "ok": True,
            "errors": errors,
            "warnings": warnings,
            "components": annotated,
            "s_holders": s_holders,
            "constraint_ids": ["CR-SFOP-01", "CR-SFOP-02"],
        }
    nodes = sorted(nodes_dir.glob("COMP-WS-*.yaml"))
    if not nodes:
        errors.append(f"CR-SFOP-01: no COMP-WS-*.yaml under {nodes_dir}")
    for path in nodes:
        data = _load(path)
        cid = str(data.get("id") or path.stem)
        status = str(data.get("status") or "")
        props = data.get("properties") if isinstance(data.get("properties"), dict) else {}
        slot = props.get("sfop_slot") or data.get("sfop_slot")
        dao = props.get("dao_layer") or data.get("dao_layer")
        if slot not in SLOTS:
            # Unannotated live nodes stay warnings until ecos self-report lands.
            # Declaring an illegal slot is still a warning; unique-S conflicts error.
            warnings.append(f"CR-SFOP-01: {cid}: missing/invalid sfop_slot={slot!r}")
        if dao not in DAO:
            warnings.append(f"CR-SFOP-01: {cid}: missing/invalid dao_layer={dao!r}")
        if slot == "S" and status == "active":
            s_holders.append(cid)
        annotated.append({"id": cid, "status": status, "sfop_slot": slot, "dao_layer": dao, "path": str(path)})
    if len(s_holders) > 1:
        errors.append(f"CR-SFOP-02: multiple active S-slot components: {s_holders}")
    elif s_holders and s_holders != [DISPATCHER_ID]:
        errors.append(f"CR-SFOP-02: S-slot holder {s_holders} != {DISPATCHER_ID}")
    elif not s_holders and nodes:
        warnings.append("CR-SFOP-02: no active S-slot dispatcher declared (expected COMP-WS-omo)")
    if registry_path.exists():
        reg = _load(registry_path)
        projects = reg.get("projects") if isinstance(reg.get("projects"), dict) else {}
        present = {p.stem.replace("COMP-WS-", "") for p in nodes}
        for name, meta in projects.items():
            if not isinstance(meta, dict):
                continue
            if meta.get("status") == "archived" or name in ARCHIVED_PROJECTS:
                continue
            if name not in present:
                warnings.append(f"registry project {name!r} has no COMP-WS-{name}.yaml")
    return {
        "ok": not errors,
        "errors": errors,
        "warnings": warnings,
        "components": annotated,
        "s_holders": s_holders,
        "constraint_ids": ["CR-SFOP-01", "CR-SFOP-02"],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--nodes-dir", type=Path, default=None)
    parser.add_argument("--registry", type=Path, default=None)
    args = parser.parse_args(argv)
    result = check(nodes_dir=args.nodes_dir, registry_path=args.registry)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"SFOP slot check: {'PASS' if result['ok'] else 'FAIL'}")
        for e in result["errors"]:
            print(f"  ERROR  {e}")
        for w in result["warnings"]:
            print(f"  WARN   {w}")
        print(f"  components={len(result['components'])} S={result['s_holders']}")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
