#!/usr/bin/env python3
"""Runtime stamp policy guard (P74 stage 2, runtime/.watch-dispatch-stamps.json 治理).

Confirms runtime artifacts that are not SSOT either:
  - match a .gitignore rule (so they remain local-only)
  - are registered in .omo/_truth/registry/runtime-projections.yaml
  - or are explicitly allowlisted by omo-runtime-stamp-policy::ALLOW_PATHS.

This prevents silent accumulation of untracked runtime files (P71 类 B recurrence).

Mirrors git's gitignore semantics including `**` directory globs and directory
patterns ending with `/`. Negation patterns (`!pattern`) are tracked but not
currently needed; kept in the signature for future use.
"""
from __future__ import annotations

import argparse
import fnmatch
import json
import sys
from pathlib import Path

import yaml


WORKSPACE = Path(__file__).resolve().parents[2]
RUNTIME_DIR = WORKSPACE / "runtime"
REGISTRY = WORKSPACE / ".omo/_truth/registry/runtime-projections.yaml"
GITIGNORE = WORKSPACE / ".gitignore"

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

# Tracked runtime files (returned by `git ls-files runtime/`). These are part
# of the watch/continuation subsystem design and should not be flagged as
# orphans even when ignored by .gitignore or absent from allow_paths.
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
    """Return tracked runtime paths via `git ls-files runtime/`.

    Cached at module level after first call. If git is unavailable, an empty
    list is returned so the guard degrades gracefully (tracked files would
    simply be reported alongside any other orphan — but `runtime/omo/**` and
    `runtime/run-continuation/**` ALLOW_PATHS still cover most cases).
    """
    global _TRACKED_OVERRIDE
    if _TRACKED_OVERRIDE:
        return _TRACKED_OVERRIDE
    try:
        import subprocess

        result = subprocess.run(
            ["git", "ls-files", "runtime/"],
            cwd=WORKSPACE,
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
    # gitignore-style ** matches any number of directories; emulate via split.
    if "**" in pattern:
        return _gitignore_match(pattern, rel_path)
    return fnmatch.fnmatch(rel_path, pattern)


def _gitignore_match(pattern: str, rel_path: str) -> bool:
    """Approximate gitignore semantics for patterns containing `**`.

    Splits the pattern on `/` and the path on `/`, then matches each segment
    with fnmatch. `**` matches zero or more path segments.
    """
    pat_parts = pattern.split("/")
    path_parts = rel_path.split("/")
    return _match_segments(pat_parts, path_parts)


def _match_segments(pat: list[str], path: list[str]) -> bool:
    if not pat:
        return not path
    head, *tail = pat
    if head == "**":
        # `**` may match zero or more segments.
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


def main() -> int:
    parser = argparse.ArgumentParser(description="Runtime stamp policy guard")
    parser.add_argument("--json", action="store_true", help="emit JSON report")
    args = parser.parse_args()

    if not RUNTIME_DIR.exists():
        report = {"ok": True, "runtime_dir_exists": False, "orphan_paths": []}
        if args.json:
            json.dump(report, sys.stdout, indent=2, sort_keys=True)
            sys.stdout.write("\n")
        else:
            print("[OK] omo-runtime-stamp-policy: runtime/ directory absent")
        return 0

    ignore_patterns = load_gitignore_patterns()
    projection_paths = load_projection_paths()
    tracked = set(load_tracked_runtime_files())

    orphans: list[dict[str, object]] = []
    for path in sorted(RUNTIME_DIR.rglob("*")):
        if path.is_dir():
            continue
        rel_path = path.relative_to(WORKSPACE).as_posix()
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

    if args.json:
        json.dump(report, sys.stdout, indent=2, sort_keys=True)
        sys.stdout.write("\n")
    else:
        status = "OK" if report["ok"] else "FAIL"
        print(
            f"[{status}] omo-runtime-stamp-policy: {len(orphans)} orphan file(s) under runtime/"
        )
        for orphan in orphans:
            print(f"  - {orphan['path']} ({orphan['size']} bytes)")

    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())