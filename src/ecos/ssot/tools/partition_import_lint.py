#!/usr/bin/env python3
"""ecos 逻辑分区 import 门禁 (ADR-0181 Phase 3).

用法:
  python -m ecos.ssot.tools.partition_import_lint
  python -m ecos.ssot.tools.partition_import_lint --json
  python -m ecos.ssot.tools.partition_import_lint --path src/ecos

Exit 0 = clean; 1 = violations.
"""

from __future__ import annotations

import argparse
import ast
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None  # type: ignore[assignment]


@dataclass
class Violation:
    rule: str
    path: str
    line: int
    message: str
    zone: str = ""
    detail: str = ""


def _ecos_root() -> Path:
    # .../src/ecos/ssot/tools/this.py → src/ecos
    return Path(__file__).resolve().parents[2]


def _src_root() -> Path:
    return _ecos_root().parent


def load_partition_map(path: Path | None = None) -> dict[str, Any]:
    if path is None:
        path = _ecos_root() / "ssot" / "registry" / "partition-map.yaml"
    if not path.exists():
        raise FileNotFoundError(f"partition-map not found: {path}")
    if yaml is None:
        raise RuntimeError("PyYAML required")
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return data


def resolve_zone(rel_posix: str, zones: dict[str, Any]) -> str | None:
    """Map 'ecos/workflow/foo.py' → zone name. rel is under src/."""
    # normalize
    if rel_posix.startswith("src/"):
        rel_posix = rel_posix[4:]
    best: tuple[int, str] | None = None
    for name, zdef in zones.items():
        for pref in zdef.get("path_prefixes", []):
            pref = pref.rstrip("/")
            if (
                rel_posix == pref
                or rel_posix.startswith(pref + "/")
                or rel_posix.startswith(pref)
            ):
                score = len(pref)
                if best is None or score > best[0]:
                    best = (score, name)
    return best[1] if best else None


def _module_to_rel(module: str) -> str | None:
    if not module.startswith("ecos"):
        return None
    parts = module.split(".")
    return "/".join(parts) + ".py"


def _zone_for_import(module: str, zones: dict[str, Any], src: Path) -> str | None:
    if not module.startswith("ecos"):
        return None
    parts = module.split(".")
    # try file then package
    candidates = [
        src / Path(*parts).with_suffix(".py"),
        src / Path(*parts) / "__init__.py",
    ]
    for c in candidates:
        if c.exists():
            rel = str(c.relative_to(src)).replace("\\", "/")
            # rel like ecos/workflow/x.py — but src is .../src, so path is ecos/...
            return resolve_zone(rel, zones)
    # climb
    for i in range(len(parts), 0, -1):
        pkg = src / Path(*parts[:i]) / "__init__.py"
        if pkg.exists():
            rel = str(pkg.relative_to(src)).replace("\\", "/")
            return resolve_zone(rel, zones)
        # synthetic prefix
        synth = "/".join(parts[:i]) + "/"
        z = resolve_zone(synth, zones)
        if z:
            return z
    return resolve_zone("/".join(parts) + "/", zones)


def _toplevel_import_nodes(tree: ast.AST) -> list[ast.AST]:
    """Module-level Import / ImportFrom only (not nested in functions/classes)."""
    body = getattr(tree, "body", [])
    return [n for n in body if isinstance(n, (ast.Import, ast.ImportFrom))]


def _all_import_nodes(tree: ast.AST) -> list[tuple[ast.AST, bool]]:
    """Return (node, is_toplevel) for all imports."""
    toplevel = set(id(n) for n in _toplevel_import_nodes(tree))
    out: list[tuple[ast.AST, bool]] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            out.append((node, id(node) in toplevel))
    return out


def _imported_modules(node: ast.AST) -> list[str]:
    if isinstance(node, ast.Import):
        return [a.name for a in node.names]
    if isinstance(node, ast.ImportFrom) and node.module:
        return [node.module]
    return []


def lint_file(
    path: Path,
    src: Path,
    zones: dict[str, Any],
) -> list[Violation]:
    rel = str(path.relative_to(src)).replace("\\", "/")
    zone = resolve_zone(rel, zones)
    if zone is None:
        return []

    zdef = zones[zone]
    try:
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path))
    except SyntaxError as e:
        return [
            Violation(
                rule="SYNTAX",
                path=rel,
                line=e.lineno or 0,
                message=f"syntax error: {e.msg}",
                zone=zone,
            )
        ]

    viols: list[Violation] = []
    may_zones = set(zdef.get("may_import_zones", [zone]))
    forbid_ext = set(zdef.get("forbid_external_packages", []))
    lazy_only = set(zdef.get("lazy_only_external_packages", []))

    for node, is_top in _all_import_nodes(tree):
        for mod in _imported_modules(node):
            top = mod.split(".")[0]
            # external package rules
            if top in forbid_ext:
                viols.append(
                    Violation(
                        rule="CORE-NO-EXTERNAL"
                        if zone == "core"
                        else "ZONE-FORBID-EXTERNAL",
                        path=rel,
                        line=getattr(node, "lineno", 0),
                        message=f"{zone} must not import external package '{top}'",
                        zone=zone,
                        detail=mod,
                    )
                )
            if top in lazy_only and is_top:
                viols.append(
                    Violation(
                        rule="FABRIC-LAZY-EXTERNAL",
                        path=rel,
                        line=getattr(node, "lineno", 0),
                        message=f"{zone} must lazy-import '{top}' (not module top-level)",
                        zone=zone,
                        detail=mod,
                    )
                )
            # internal zone graph
            if top == "ecos":
                target_zone = _zone_for_import(mod, zones, src)
                if target_zone and target_zone not in may_zones:
                    viols.append(
                        Violation(
                            rule="ZONE-IMPORT-DIR",
                            path=rel,
                            line=getattr(node, "lineno", 0),
                            message=f"{zone} → {target_zone} forbidden (import {mod})",
                            zone=zone,
                            detail=mod,
                        )
                    )

    # path hack: fabric sys.path insert pointing at services
    if zone == "fabric":
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                # sys.path.insert(...)
                func = node.func
                if (
                    isinstance(func, ast.Attribute)
                    and func.attr == "insert"
                    and isinstance(func.value, ast.Attribute)
                    and func.value.attr == "path"
                ):
                    # check args for "services"
                    for arg in node.args:
                        if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                            if "services" in arg.value:
                                viols.append(
                                    Violation(
                                        rule="NO-PATH-HACK-TO-OPS",
                                        path=rel,
                                        line=node.lineno,
                                        message="fabric must not sys.path-insert services/",
                                        zone=zone,
                                    )
                                )
                    # Path(...) / "services"
                    dump = ast.dump(node)
                    if "services" in dump:
                        viols.append(
                            Violation(
                                rule="NO-PATH-HACK-TO-OPS",
                                path=rel,
                                line=node.lineno,
                                message="fabric must not sys.path-insert services/ (path hack)",
                                zone=zone,
                            )
                        )

    return viols


def lint_tree(src: Path | None = None, map_path: Path | None = None) -> list[Violation]:
    src = src or _src_root()
    pmap = load_partition_map(map_path)
    zones = pmap.get("zones", {})
    ecos_dir = src / "ecos"
    viols: list[Violation] = []
    for path in sorted(ecos_dir.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        # skip huge generated under mof if any .py besides small ones
        if (
            "ssot" in path.parts
            and "mof" in path.parts
            and path.stat().st_size > 100_000
        ):
            continue
        viols.extend(lint_file(path, src, zones))
    return viols


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="ecos partition import lint (ADR-0181)")
    ap.add_argument(
        "--path", type=Path, default=None, help="src root (default: package src)"
    )
    ap.add_argument("--map", type=Path, default=None, help="partition-map.yaml path")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    try:
        viols = lint_tree(args.path, args.map)
    except Exception as e:
        print(f"error: {e}", file=sys.stderr)
        return 2

    if args.json:
        print(
            json.dumps(
                {"violations": [asdict(v) for v in viols], "count": len(viols)},
                indent=2,
            )
        )
    else:
        if not viols:
            print("partition-import-lint: OK (0 violations)")
        else:
            print(f"partition-import-lint: FAIL ({len(viols)} violations)")
            for v in viols:
                print(f"  [{v.rule}] {v.path}:{v.line} {v.message}")
    return 1 if viols else 0


if __name__ == "__main__":
    raise SystemExit(main())
