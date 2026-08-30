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
import subprocess
import sys
from pathlib import Path

import yaml

WORKSPACE = Path(__file__).resolve().parents[2]
RUNTIME_DIR = WORKSPACE / "runtime"
REGISTRY = WORKSPACE / ".omo/_truth/registry/runtime-projections.yaml"
GITIGNORE = WORKSPACE / ".gitignore"
PROJECTION_REGISTRY_REL = ".omo/_truth/registry/runtime-projections.yaml"

ALLOW_PATHS: tuple[str, ...] = (
    "runtime/README.md",
    "runtime/runtime-space-boundary.yaml",
    "runtime/system-runtime-boundary.yaml",
    "runtime/AGENTS.md",
    "runtime/coordination/handoffs/**",
    "runtime/cron/**",
    "runtime/sandbox/**",
    "runtime/logs/**",
    "runtime/data/**",
    "runtime/omo/**",
    "runtime/run-continuation/**",
    "runtime/ssot-stable/**",
)

# Final-tree admission is deliberately narrower than the worktree diagnostic
# above.  These are repository contracts, not output/cache exceptions.  A
# tracked path outside this list is forbidden even when .gitignore would match
# it in the checkout.
FINAL_TREE_ALLOW_PATHS: tuple[str, ...] = (
    "runtime/AGENTS.md",
    "runtime/README.md",
    "runtime/runtime-space-boundary.yaml",
    "runtime/system-runtime-boundary.yaml",
    "runtime/cron/**",
    "runtime/ssot-stable/**",
    "runtime/sandbox/**",
    "runtime/coordination/**",
)

REGULAR_FILE_MODES = frozenset({"100644", "100755"})

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
        if line.endswith("/"):
            # 目录模式 (gitignore trailing /) 匹配目录下所有内容;
            # rstrip("/") 会丢目录语义致 fnmatch 不匹配子路径 (P82 StageA 修:
            # runtime/agent-sessions/ 应匹配其下 IMPACT.md 等).
            patterns.append(line.rstrip("/") + "/**")
        else:
            patterns.append(line)
    return patterns


def projection_paths_from_documents(documents: object) -> set[str]:
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


def load_projection_paths() -> set[str]:
    if not REGISTRY.exists():
        return set()
    documents = [doc for doc in yaml.safe_load_all(REGISTRY.read_text(encoding="utf-8")) if doc]
    return projection_paths_from_documents(documents)


def load_treeish_projection_paths(treeish: str) -> set[str]:
    """Read projection paths from the same immutable revision being admitted."""
    probe = subprocess.run(
        ["git", "ls-tree", "-r", "--name-only", treeish, "--", PROJECTION_REGISTRY_REL],
        cwd=WORKSPACE,
        capture_output=True,
        text=True,
        check=False,
    )
    if probe.returncode != 0:
        raise ValueError(f"treeish projection registry cannot be listed: {treeish}")
    if PROJECTION_REGISTRY_REL not in probe.stdout.splitlines():
        return set()

    result = subprocess.run(
        ["git", "show", f"{treeish}:{PROJECTION_REGISTRY_REL}"],
        cwd=WORKSPACE,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise ValueError(f"treeish projection registry cannot be read: {treeish}")
    try:
        documents = [doc for doc in yaml.safe_load_all(result.stdout) if doc]
    except yaml.YAMLError as exc:
        raise ValueError(f"treeish projection registry is invalid: {treeish}") from exc
    return projection_paths_from_documents(documents)


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


def load_treeish_runtime_entries(treeish: str) -> tuple[tuple[str, str, str], ...]:
    """Return sorted ``(mode, object_id, path)`` entries from one Git tree.

    The requested revision is the only source of runtime entries in this
    mode.  In particular, this function never walks, stats, or resolves files
    from the checkout filesystem.
    """
    if not isinstance(treeish, str) or not treeish or treeish.startswith("-") or any(
        char.isspace() for char in treeish
    ):
        raise ValueError("treeish must be a non-empty git revision")

    try:
        revision = subprocess.run(
            ["git", "rev-parse", "--verify", f"{treeish}^{{tree}}"],
            cwd=WORKSPACE,
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError as exc:
        raise ValueError(f"treeish is not readable: {treeish}") from exc
    if revision.returncode != 0:
        raise ValueError(f"treeish is not resolvable: {treeish}")

    try:
        result = subprocess.run(
            ["git", "ls-tree", "-r", "-z", treeish, "--", "runtime"],
            cwd=WORKSPACE,
            capture_output=True,
            check=False,
        )
    except OSError as exc:
        raise ValueError(f"treeish is not readable: {treeish}") from exc
    if result.returncode != 0:
        raise ValueError(f"treeish cannot be listed: {treeish}")

    entries: list[tuple[str, str, str]] = []
    for raw_entry in result.stdout.split(b"\0"):
        if not raw_entry:
            continue
        metadata, separator, raw_path = raw_entry.partition(b"\t")
        if not separator:
            raise ValueError(f"treeish contains malformed runtime entry: {treeish}")
        fields = metadata.split()
        if len(fields) != 3:
            raise ValueError(f"treeish contains malformed runtime entry: {treeish}")
        mode, _entry_type, object_id = fields
        entries.append(
            (
                mode.decode("ascii"),
                object_id.decode("ascii"),
                raw_path.decode("utf-8", errors="surrogateescape"),
            )
        )
    return tuple(sorted(entries, key=lambda entry: entry[2]))


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


def is_allowed(
    rel_path: str,
    ignore_patterns: list[str],
    projection_paths: set[str],
    tracked: set[str],
    *,
    allow_tracked: bool = True,
) -> bool:
    for allowed in ALLOW_PATHS:
        if _match(allowed, rel_path):
            return True
    if rel_path in projection_paths:
        return True
    if allow_tracked and rel_path in tracked:
        return True
    for pattern in ignore_patterns:
        if _match(pattern, rel_path):
            return True
    return False


def is_final_tree_allowed(rel_path: str, projection_paths: set[str]) -> bool:
    """Return whether a tracked runtime path is an explicit final-tree contract."""
    return any(_match(pattern, rel_path) for pattern in FINAL_TREE_ALLOW_PATHS) or rel_path in projection_paths


def evaluate_treeish(treeish: str) -> dict[str, object]:
    """Return stable, fail-closed admission findings for one immutable tree."""
    entries = load_treeish_runtime_entries(treeish)
    projection_paths = load_treeish_projection_paths(treeish)
    forbidden_tracked_paths = sorted(
        path
        for mode, _object_id, path in entries
        if mode in REGULAR_FILE_MODES and not is_final_tree_allowed(path, projection_paths)
    )
    invalid_modes = sorted(path for mode, _object_id, path in entries if mode not in REGULAR_FILE_MODES)
    return {
        "ok": not forbidden_tracked_paths and not invalid_modes,
        "treeish": treeish,
        "tracked_runtime_count": len(entries),
        "forbidden_tracked_paths": forbidden_tracked_paths,
        "invalid_modes": invalid_modes,
        # Preserve the historical human/report shape while making the exact
        # path list above authoritative for final-tree consumers.
        "orphan_paths": [{"path": path} for path in forbidden_tracked_paths],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Runtime stamp policy guard")
    parser.add_argument("--json", action="store_true", help="emit JSON report")
    parser.add_argument(
        "--treeish",
        default=None,
        help="audit runtime files from an immutable git tree instead of the checkout",
    )
    args = parser.parse_args()

    if args.treeish:
        try:
            report = evaluate_treeish(args.treeish)
        except (OSError, ValueError) as exc:
            print(f"[FAIL] omo-runtime-stamp-policy: {exc}", file=sys.stderr)
            return 2
        if args.json:
            json.dump(report, sys.stdout, indent=2, sort_keys=True)
            sys.stdout.write("\n")
        else:
            status = "OK" if report["ok"] else "FAIL"
            forbidden = report["forbidden_tracked_paths"]
            invalid = report["invalid_modes"]
            print(
                f"[{status}] omo-runtime-stamp-policy: "
                f"{len(forbidden)} forbidden tracked path(s), {len(invalid)} invalid mode(s)"
            )
            for path in forbidden:
                print(f"  - forbidden: {path}")
            for path in invalid:
                print(f"  - invalid mode: {path}")
        return 0 if report["ok"] else 1

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
    candidates = [
        (path.relative_to(WORKSPACE).as_posix(), path.stat().st_size)
        for path in sorted(RUNTIME_DIR.rglob("*"))
        if path.is_file()
    ]
    allow_tracked = True
    policy_ignore_patterns = ignore_patterns

    orphans: list[dict[str, object]] = []
    for rel_path, size in candidates:
        if is_allowed(
            rel_path,
            policy_ignore_patterns,
            projection_paths,
            tracked,
            allow_tracked=allow_tracked,
        ):
            continue
        orphans.append({"path": rel_path, "size": size})

    report = {
        "ok": not orphans,
        "runtime_dir_exists": True,
        "treeish": args.treeish,
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
        print(f"[{status}] omo-runtime-stamp-policy: {len(orphans)} orphan file(s) under runtime/")
        for orphan in orphans:
            print(f"  - {orphan['path']} ({orphan['size']} bytes)")

    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
