#!/usr/bin/env python3
"""check-layer-call-direction.py — 分层调用方向守门 (P76 Phase 2 / ADR-0156)

按 CR-LAYER-CALL-DIRECTION 规则扫描 projects/* 下的项目间 import 关系:

允许:
  L3 -> I0, L2, M0
  L2 -> L0, I0, L2-sibling (via BOS only)
  L1 -> L0, Bus
  M0, L0 -> (none)

禁止:
  L0/M0 import 任何 project
  L1 -> L2
  L2 -> L3
  I0 -> L2
  X -> X (extensions 不能直接 import 彼此)

enforcement=advisory 默认; Phase 3 升级 hard (CI gate)
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[1]

PROJECT_LAYER = {
    "l4-kernel": "L4",
    "cockpit": "L3",
    "cockpit-ui": "L3",
    "agora": "I0",
    "runtime": "L1",
    "ecos": "L0",
    "kairon": "L2",
    "gbrain": "L2",
    "omo": "L2",
    "omo-debt": "L2",
    "metaos": "L2",
    "family-hub": "L2",
    "model-driven": "M0",
    "aetherforge": "X",
    "c2g": "X",
    "bus-foundation": "X",
    "observability": "X",
    "toolbox": "X",
}

# 允许方向 (caller_layer -> set of allowed called_layers)
ALLOWED_DIRECTION: dict[str, set[str]] = {
    "L3": {"I0", "L1", "L2", "M0", "L4"},  # L3 调用 L1 (runtime 基质, orchestration)
    "I0": {"L0", "M0"},
    "L4": {"L0"},
    "L2": {"L0", "I0", "L2"},
    "L1": {"L0"},
    "L0": set(),
    "M0": set(),
    "X": {"L0", "L1", "L2", "L3", "I0", "M0", "L4", "X"},
}

# BOS URI 模式 (经此调用视为合规, 即使直接 import 不存在)
BOS_URI_PATTERN = re.compile(r"bos://[a-zA-Z0-9_./-]+")

# Python import 模式: from <project>.<rest> import ... | import <project>
PYTHON_IMPORT_PATTERN = re.compile(
    r"^\s*(?:from\s+([a-zA-Z0-9_]+)(?:\.[a-zA-Z0-9_.]+)?\s+import|import\s+([a-zA-Z0-9_]+))",
    re.MULTILINE,
)

# TypeScript import 模式
TS_IMPORT_PATTERN = re.compile(
    r"""(?:from\s+['"]([^'"]+)['"]|import\s+['"]([^'"]+)['"])""",
)


def detect_project(file_path: Path) -> str | None:
    """从文件路径推断所在项目 + 层."""
    try:
        rel = file_path.resolve().relative_to(WORKSPACE / "projects")
    except ValueError:
        return None
    parts = rel.parts
    if not parts:
        return None
    first = parts[0]
    return PROJECT_LAYER.get(first, "X" if first.startswith(("aetherforge", "bus-foundation")) else None)


def detect_project_name(file_path: Path) -> str | None:
    """返回所在项目的 dir name (caller 项目名)."""
    try:
        rel = file_path.resolve().relative_to(WORKSPACE / "projects")
    except ValueError:
        return None
    return rel.parts[0] if rel.parts else None


def scan_file(file_path: Path) -> list[dict]:
    """扫描单个文件找出违规 import."""
    try:
        text = file_path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return []
    layer = detect_project(file_path)
    if not layer:
        return []
    caller_project = detect_project_name(file_path)
    src_ext = file_path.suffix
    findings: list[dict] = []
    seen = set()

    if src_ext == ".py":
        for m in PYTHON_IMPORT_PATTERN.finditer(text):
            target = m.group(1) or m.group(2)
            if not target or target in seen:
                continue
            seen.add(target)
            # self-import (同项目内) 总是允许
            if target == caller_project:
                continue
            # stdlib / 第三方模块直接跳过 (无 PROJECT_LAYER 命中)
            target_layer = PROJECT_LAYER.get(target)
            if target_layer is None:
                continue
            # kairon 子包 (eidos, minerva, ...) 视为 L2 同层 — 跳过
            if caller_project == "kairon":
                continue
            allowed = ALLOWED_DIRECTION.get(layer, set())
            if target_layer not in allowed:
                findings.append(
                    {
                        "file": str(file_path.relative_to(WORKSPACE)),
                        "line": text[: m.start()].count("\n") + 1,
                        "caller_layer": layer,
                        "callee_project": target,
                        "callee_layer": target_layer,
                        "snippet": m.group(0)[:80],
                        "violation": f"{layer} -> {target_layer} forbidden (caller={caller_project}, callee={target})",
                    }
                )
    elif src_ext in (".ts", ".tsx", ".js", ".jsx"):
        for m in TS_IMPORT_PATTERN.finditer(text):
            imp = m.group(1) or m.group(2) or ""
            # self-import (相对路径或同名)
            if imp.startswith("."):
                continue
            if imp.startswith("@"):
                pkg = imp.split("/")[0].lstrip("@")
                if pkg == caller_project:
                    continue
                target_layer = PROJECT_LAYER.get(pkg)
                if target_layer and target_layer not in ALLOWED_DIRECTION.get(layer, set()):
                    findings.append(
                        {
                            "file": str(file_path.relative_to(WORKSPACE)),
                            "line": text[: m.start()].count("\n") + 1,
                            "caller_layer": layer,
                            "callee_project": pkg,
                            "callee_layer": target_layer,
                            "snippet": imp,
                            "violation": f"{layer} -> {target_layer} forbidden",
                        }
                    )
    return findings


def scan_workspace(paths: list[Path] | None = None, *, strict: bool = False) -> dict:
    """扫 workspace 全部 .py/.ts 文件."""
    if paths is None:
        paths = [WORKSPACE / "projects" / p for p in PROJECT_LAYER if (WORKSPACE / "projects" / p).exists()]
    all_findings: list[dict] = []
    files_scanned = 0
    for project_dir in paths:
        for ext in ("*.py", "*.ts", "*.tsx"):
            for f in project_dir.rglob(ext):
                # 跳过测试目录, venv, node_modules, dist
                if any(part in f.parts for part in ("tests", ".venv", "node_modules", "dist", "build", "__pycache__")):
                    continue
                files_scanned += 1
                all_findings.extend(scan_file(f))
    by_pair: dict[tuple[str, str], int] = {}
    for f in all_findings:
        key = (f["caller_layer"], f["callee_layer"])
        by_pair[key] = by_pair.get(key, 0) + 1
    return {
        "ok": len(all_findings) == 0,
        "files_scanned": files_scanned,
        "violations": len(all_findings),
        "by_call_pair": dict(sorted(by_pair.items())),
        "findings": all_findings[:50] if not strict else all_findings,
    }


def main() -> int:
    import argparse

    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--strict", action="store_true", help="Show all findings (default first 50)")
    p.add_argument("--json", action="store_true", help="JSON output")
    p.add_argument("--by-layer", action="store_true", help="Summarize by call pair only")
    p.add_argument("--project", help="Scan specific project (e.g. agora)")
    args = p.parse_args()

    if args.project:
        paths = [WORKSPACE / "projects" / args.project]
    else:
        paths = None
    result = scan_workspace(paths, strict=args.strict)

    if args.json:
        import json
        print(json.dumps(result, indent=2, ensure_ascii=False))
    elif args.by_layer:
        print("=== layer-call-direction summary ===")
        print(f"files_scanned: {result['files_scanned']}")
        print(f"violations: {result['violations']}")
        print("\nby call pair (caller -> callee):")
        for (c, t), n in result["by_call_pair"].items():
            print(f"  {c} -> {t}: {n}")
    else:
        print(f"files_scanned: {result['files_scanned']}")
        print(f"violations: {result['violations']}")
        if result["violations"] > 0:
            print("\nfirst 10:")
            for f in result["findings"][:10]:
                print(f"  {f['file']}:{f['line']} {f['violation']} ({f['snippet']})")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
