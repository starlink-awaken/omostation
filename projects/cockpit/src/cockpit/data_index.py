from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

_WORKSPACE_ROOT_ENV = "WORKSPACE_ROOT"
_WORKSPACE_SENTINEL = ".omo"
_DATA_INDEX_DIR = Path("data/_index")
_CATALOG_FILE = "catalog.json"
_TYPES_FILE = "types.json"
_GC_POLICY_FILE = "gc-policy.json"

_DEFAULT_TYPES: list[dict[str, Any]] = [
    {
        "id": "sqlite_database",
        "label": "SQLite database",
        "extensions": [".db", ".sqlite", ".sqlite3"],
        "retention_class": "durable",
    },
    {
        "id": "backup_archive",
        "label": "Backup archive",
        "extensions": [".tar", ".tgz", ".zip"],
        "retention_class": "durable",
    },
    {
        "id": "json_document",
        "label": "JSON document",
        "extensions": [".json"],
        "retention_class": "durable",
    },
    {
        "id": "runtime_log",
        "label": "Runtime log",
        "extensions": [".log"],
        "retention_class": "ephemeral",
    },
    {
        "id": "temporary_artifact",
        "label": "Temporary artifact",
        "extensions": [".tmp", ".temp", ".cache"],
        "retention_class": "ephemeral",
    },
]


@dataclass(frozen=True)
class DataIndexPaths:
    workspace_root: Path
    data_root: Path
    runtime_root: Path
    registry_path: Path
    metadata_root: Path
    tmp_root: Path


def resolve_workspace_root(start: Path | None = None) -> Path:
    env_root = os.environ.get(_WORKSPACE_ROOT_ENV)
    candidates: list[Path] = []
    if env_root:
        candidates.extend(_expand_candidate(Path(env_root)))
    if start is not None:
        candidates.extend(_expand_candidate(start))
    candidates.extend(_expand_candidate(Path.cwd()))
    candidates.extend(_expand_candidate(Path(__file__).resolve()))

    seen: set[Path] = set()
    for candidate in candidates:
        if candidate in seen:
            continue
        seen.add(candidate)
        if (candidate / _WORKSPACE_SENTINEL).exists() and (candidate / "data").exists():
            return candidate
    raise FileNotFoundError("unable to locate workspace root containing .omo and data/")


def build_data_index(workspace_root: Path | None = None) -> dict[str, Any]:
    paths = _paths(workspace_root)
    registry = _load_registry(paths.registry_path)
    directories = _collect_directories(paths.data_root)
    types = list(_DEFAULT_TYPES)
    gc_policy = _default_gc_policy()

    catalog = {
        "generated_at": _iso_now(),
        "workspace_root": str(paths.workspace_root),
        "registry_ref": _relative(paths.registry_path, paths.workspace_root),
        "directories": directories,
        "spaces": [space.get("id") for space in registry.get("spaces", []) if isinstance(space, dict)],
        "roots": _collect_registry_roots(registry),
    }
    _write_json(paths.metadata_root / _CATALOG_FILE, catalog)
    _write_json(paths.metadata_root / _TYPES_FILE, {"generated_at": _iso_now(), "types": types})
    _write_json(paths.metadata_root / _GC_POLICY_FILE, gc_policy)
    return {
        "registry_ref": catalog["registry_ref"],
        "directories": directories,
        "types": types,
        "gc_policy": gc_policy,
    }


def load_type_registry(workspace_root: Path | None = None) -> list[dict[str, Any]]:
    paths = _paths(workspace_root)
    type_file = paths.metadata_root / _TYPES_FILE
    if not type_file.exists():
        build_data_index(paths.workspace_root)
    payload = json.loads(type_file.read_text(encoding="utf-8"))
    return list(payload.get("types", []))


def load_gc_policy(workspace_root: Path | None = None) -> dict[str, Any]:
    paths = _paths(workspace_root)
    policy_file = paths.metadata_root / _GC_POLICY_FILE
    if not policy_file.exists():
        build_data_index(paths.workspace_root)
    return json.loads(policy_file.read_text(encoding="utf-8"))


def sweep_tmp_data(
    workspace_root: Path | None = None,
    *,
    max_age_seconds: int | None = None,
    now: float | None = None,
) -> dict[str, Any]:
    paths = _paths(workspace_root)
    policy = load_gc_policy(paths.workspace_root)
    effective_now = time.time() if now is None else float(now)
    configured_age = int(policy["scopes"][0]["max_age_seconds"])
    ttl = int(max_age_seconds if max_age_seconds is not None else configured_age)

    deleted_paths: list[str] = []
    kept_paths: list[str] = []
    if paths.tmp_root.exists():
        for candidate in sorted(path for path in paths.tmp_root.rglob("*") if path.is_file()):
            age = effective_now - candidate.stat().st_mtime
            relative = _relative(candidate, paths.workspace_root)
            if age > ttl:
                candidate.unlink()
                deleted_paths.append(relative)
            else:
                kept_paths.append(relative)
    return {
        "scope": "data/tmp",
        "max_age_seconds": ttl,
        "deleted_paths": deleted_paths,
        "kept_paths": kept_paths,
    }


def _paths(workspace_root: Path | None) -> DataIndexPaths:
    root = resolve_workspace_root(workspace_root)
    return DataIndexPaths(
        workspace_root=root,
        data_root=root / "data",
        runtime_root=root / "runtime",
        registry_path=root / "spaces" / "registry.yaml",
        metadata_root=root / _DATA_INDEX_DIR,
        tmp_root=root / "data" / "tmp",
    )


def _expand_candidate(path: Path) -> list[Path]:
    base = path if path.is_dir() else path.parent
    return [base, *base.parents]


def _load_registry(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"spaces": []}
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return payload if isinstance(payload, dict) else {"spaces": []}


def _collect_directories(data_root: Path) -> list[str]:
    if not data_root.exists():
        return []
    directories = {
        _relative(path, data_root.parent)
        for path in data_root.rglob("*")
        if path.is_dir() and _DATA_INDEX_DIR.name not in path.parts
    }
    return sorted(directories)


def _collect_registry_roots(registry: dict[str, Any]) -> list[dict[str, Any]]:
    roots: list[dict[str, Any]] = []
    for space in registry.get("spaces", []):
        if not isinstance(space, dict):
            continue
        root_map = space.get("roots")
        if not isinstance(root_map, dict):
            continue
        roots.append({"space_id": space.get("id"), "roots": dict(root_map)})
    return roots


def _default_gc_policy() -> dict[str, Any]:
    return {
        "version": 1,
        "generated_at": _iso_now(),
        "scopes": [
            {
                "root": "data/tmp",
                "max_age_seconds": 24 * 60 * 60,
                "recursive": True,
            }
        ],
    }


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp_path.replace(path)


def _relative(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def _iso_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
