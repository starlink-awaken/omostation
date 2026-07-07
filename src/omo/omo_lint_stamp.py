"""omo lint stamp-policy — P74 runtime 孤儿文件治理.

从 bin/omo-runtime-stamp-policy.py 迁移 (ADR-0130).

确认 runtime/ 下的非 SSOT 文件要么:
  - 匹配 .gitignore 规则 (保持 local-only)
  - 在 .omo/_truth/registry/runtime-projections.yaml 中注册
  - 在 ALLOW_PATHS 白名单中
  - 是 git tracked 文件

防止静默累积未追踪的 runtime 文件 (P71 类 B 复发).

退出码: 0 无孤儿, 1 有孤儿.
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import subprocess
import sys
from pathlib import Path

import yaml

from omo.omo_paths import OMO_ROOT, WORKSPACE_ROOT

RUNTIME_DIR = WORKSPACE_ROOT / "runtime"
REGISTRY = OMO_ROOT / "_truth" / "registry" / "runtime-projections.yaml"
GITIGNORE = WORKSPACE_ROOT / ".gitignore"

ALLOW_PATHS: tuple[str, ...] = (
    "runtime/README.md",
    "runtime/runtime-space-boundary.yaml",
    "runtime/system-runtime-boundary.yaml",
    "runtime/sandbox/**",
    "runtime/logs/**",
    "runtime/data/**",
    "runtime/omo/**",
    "runtime/run-continuation/**",
)

_TRACKED_OVERRIDE: tuple[str, ...] = ()


def load_gitignore_patterns() -> list[str]:
    if not GITIGNORE.exists():
        return []
    patterns: list[str] = []
    for raw in GITIGNORE.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or line.startswith("!"):
            continue
        patterns.append(line.rstrip("/"))
    return patterns


def load_projection_paths() -> set[str]:
    if not REGISTRY.exists():
        return set()
    documents = [doc for doc in yaml.safe_load_all(REGISTRY.read_text(encoding="utf-8")) if doc]
    paths: set[str] = set()
    for document in documents:
        if isinstance(document, dict) and "projections" in document:
            raw = document.get("projections") or {}
            if isinstance(raw, dict):
                for payload in raw.values():
                    if isinstance(payload, dict):
                        for key in ("canonical", "legacy"):
                            value = str(payload.get(key) or "")
                            if value:
                                paths.add(value)
    return paths


def load_tracked_runtime_files() -> tuple[str, ...]:
    global _TRACKED_OVERRIDE
    if _TRACKED_OVERRIDE:
        return _TRACKED_OVERRIDE
    try:
        result = subprocess.run(
            ["git", "ls-files", "runtime/"],
            cwd=WORKSPACE_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        return ()
    if result.returncode != 0:
        return ()
    paths = tuple(line.strip() for line in result.stdout.splitlines() if line.strip())
    _TRACKED_OVERRIDE = paths
    return paths


def _match(pattern: str, rel_path: str) -> bool:
    if pattern == rel_path:
        return True
    if pattern.endswith("/**"):
        prefix = pattern[:-3]
        if rel_path.startswith(prefix + "/") or rel_path == prefix:
            return True
    if pattern.endswith("/*"):
        prefix = pattern[:-2]
        if rel_path.startswith(prefix + "/"):
            return True
    if "**" in pattern:
        return _gitignore_match(pattern, rel_path)
    return fnmatch.fnmatch(rel_path, pattern)


def _gitignore_match(pattern: str, rel_path: str) -> bool:
    pat_parts = pattern.split("/")
    path_parts = rel_path.split("/")
    return _match_segments(pat_parts, path_parts)


def _match_segments(pat: list[str], path: list[str]) -> bool:
    if not pat:
        return not path
    head, *tail = pat
    if head == "**":
        if _match_segments(tail, path):
            return True
        if path:
            return _match_segments(pat, path[1:])
        return False
    if not path:
        return False
    if not fnmatch.fnmatch(path[0], head):
        return False
    return _match_segments(tail, path[1:])


def is_allowed(rel_path: str, ignore_patterns: list[str], projection_paths: set[str], tracked: set[str]) -> bool:
    for allowed in ALLOW_PATHS:
        if _match(allowed, rel_path):
            return True
    if rel_path in projection_paths:
        return True
    if rel_path in tracked:
        return True
    for pattern in ignore_patterns:
        if _match(pattern, rel_path):
            return True
    return False


def cmd_stamp_policy(json_output: bool = False) -> int:
    """P74: 验证 runtime/ 下文件必须 gitignored/tracked/allowlisted."""
    if not RUNTIME_DIR.exists():
        report = {"ok": True, "runtime_dir_exists": False, "orphan_paths": []}
        if json_output:
            json.dump(report, sys.stdout, indent=2, sort_keys=True)
            sys.stdout.write("\n")
        else:
            print("[OK] stamp-policy: runtime/ directory absent")
        return 0

    ignore_patterns = load_gitignore_patterns()
    projection_paths = load_projection_paths()
    tracked = set(load_tracked_runtime_files())

    orphans: list[dict[str, object]] = []
    for path in sorted(RUNTIME_DIR.rglob("*")):
        if path.is_dir():
            continue
        rel_path = path.relative_to(WORKSPACE_ROOT).as_posix()
        if is_allowed(rel_path, ignore_patterns, projection_paths, tracked):
            continue
        orphans.append({"path": rel_path, "size": path.stat().st_size})

    report = {
        "ok": not orphans,
        "runtime_dir_exists": True,
        "ignore_pattern_count": len(ignore_patterns),
        "projection_path_count": len(projection_paths),
        "tracked_runtime_count": len(tracked),
        "orphan_paths": orphans,
    }

    if json_output:
        json.dump(report, sys.stdout, indent=2, sort_keys=True)
        sys.stdout.write("\n")
    else:
        status = "OK" if report["ok"] else "FAIL"
        print(
            f"[{status}] stamp-policy: {len(orphans)} orphan file(s) under runtime/"
        )
        for orphan in orphans:
            print(f"  - {orphan['path']} ({orphan['size']} bytes)")

    return 0 if report["ok"] else 1
