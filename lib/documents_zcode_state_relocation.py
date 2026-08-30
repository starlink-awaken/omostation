"""Fail-closed relocation of ZCode client state out of Documents."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import stat
import subprocess
import tempfile
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

SCHEMA = "documents.zcode-state-relocation/v1"
INSPECTION_SCHEMA = "documents.zcode-state-relocation-inspection/v1"
VOLATILE_SETTING_KEYS = frozenset({"lastWorkspaceSession"})
CRITICAL_PATHS = (
    "v2/tasks-index.sqlite",
    "v2/tasks-index.sqlite-wal",
    "v2/tasks-index.sqlite-shm",
    "v2/config.json",
    "v2/credentials.json",
    "v2/sessions",
    "v2/logs",
    "v2/checkpoints",
    "v2/crash",
    "v2/certs",
    "v2/agent-config",
    "workspace/default",
    "plugin-workspace",
)


class RelocationError(RuntimeError):
    """A stable, user-facing relocation failure."""


@dataclass(frozen=True)
class RelocationPaths:
    source_base: Path
    target_base: Path
    settings: Path
    manifest: Path

    @property
    def source_root(self) -> Path:
        return self.source_base / ".zcode"

    @property
    def target_root(self) -> Path:
        return self.target_base / ".zcode"

    @property
    def source_state(self) -> Path:
        return self.source_root / "v2"

    @property
    def target_state(self) -> Path:
        return self.target_root / "v2"


def _sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _canonical_digest(value: object) -> str:
    rendered = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return _sha256_bytes(rendered.encode("utf-8"))


def _load_json_mapping(path: Path, label: str) -> dict[str, Any]:
    try:
        metadata = path.lstat()
    except OSError as exc:
        raise RelocationError(f"{label} unavailable: {path}") from exc
    if not stat.S_ISREG(metadata.st_mode) or stat.S_ISLNK(metadata.st_mode):
        raise RelocationError(f"{label} must be a regular non-symlink file: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise RelocationError(f"{label} is malformed: {path}") from exc
    if not isinstance(payload, dict):
        raise RelocationError(f"{label} must be a JSON object: {path}")
    return payload


def _settings_snapshot(path: Path) -> dict[str, Any]:
    payload = _load_json_mapping(path, "settings")
    unrelated = dict(payload)
    unrelated.pop("dataBaseDir", None)
    protected = {key: value for key, value in unrelated.items() if key not in VOLATILE_SETTING_KEYS}
    return {
        "payload": payload,
        "mode": path.stat().st_mode & 0o777,
        "sha256": _sha256_file(path),
        "unrelated_digest": _canonical_digest(unrelated),
        "protected_digest": _canonical_digest(protected),
    }


def _critical_inventory(root: Path) -> dict[str, dict[str, Any]]:
    inventory: dict[str, dict[str, Any]] = {}
    missing: list[str] = []
    for relative in CRITICAL_PATHS:
        candidate = root / relative
        try:
            metadata = candidate.lstat()
        except OSError:
            missing.append(relative)
            continue
        if stat.S_ISLNK(metadata.st_mode):
            missing.append(relative)
            continue
        kind = "directory" if stat.S_ISDIR(metadata.st_mode) else "file" if stat.S_ISREG(metadata.st_mode) else "other"
        if kind == "other":
            missing.append(relative)
            continue
        record: dict[str, Any] = {
            "kind": kind,
            "mode": metadata.st_mode & 0o777,
            "size": metadata.st_size,
        }
        if kind == "file":
            record["sha256"] = _sha256_file(candidate)
        inventory[relative] = record
    if missing:
        raise RelocationError("critical state is incomplete: " + ", ".join(sorted(missing)))
    return inventory


def _tree_summary(root: Path) -> dict[str, int]:
    files = 0
    directories = 0
    symlinks = 0
    bytes_total = 0
    for current_root, directory_names, file_names in os.walk(root, followlinks=False):
        directories += 1
        current = Path(current_root)
        for name in directory_names:
            if (current / name).is_symlink():
                symlinks += 1
        for name in file_names:
            path = current / name
            try:
                metadata = path.lstat()
            except OSError as exc:
                raise RelocationError(f"state changed during inventory: {path}") from exc
            if stat.S_ISLNK(metadata.st_mode):
                symlinks += 1
            elif stat.S_ISREG(metadata.st_mode):
                files += 1
                bytes_total += metadata.st_size
    return {
        "files": files,
        "directories": directories,
        "symlinks": symlinks,
        "bytes": bytes_total,
    }


def _state_snapshot(root: Path) -> dict[str, Any]:
    try:
        metadata = root.lstat()
    except OSError as exc:
        raise RelocationError(f"source state unavailable: {root}") from exc
    if not stat.S_ISDIR(metadata.st_mode) or stat.S_ISLNK(metadata.st_mode):
        raise RelocationError(f"source state must be a directory: {root}")
    return {
        "device": metadata.st_dev,
        "inode": metadata.st_ino,
        "tree": _tree_summary(root),
        "critical": _critical_inventory(root),
    }


def _nearest_existing(path: Path) -> Path:
    candidate = path
    while not candidate.exists():
        parent = candidate.parent
        if parent == candidate:
            raise RelocationError(f"no existing target ancestor: {path}")
        candidate = parent
    return candidate


def require_same_device(*, source_device: int, target_device: int) -> None:
    if source_device != target_device:
        raise RelocationError("source and target must be on the same filesystem for atomic relocation")


def require_free_space(*, required_bytes: int, available_bytes: int) -> None:
    if available_bytes < required_bytes:
        raise RelocationError("insufficient target disk space for verified copy")


def _validate_path_relationships(paths: RelocationPaths) -> None:
    source = paths.source_root.absolute()
    target = paths.target_root.absolute()
    manifest = paths.manifest.absolute()
    if source == target or source in target.parents or target in source.parents:
        raise RelocationError("source and target must be disjoint")
    if source in manifest.parents or target in manifest.parents:
        raise RelocationError("manifest must stay outside source and target")


def _atomic_write_bytes(path: Path, content: bytes, mode: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary: str | None = None
    try:
        with tempfile.NamedTemporaryFile(dir=str(path.parent), prefix=f".{path.name}.", delete=False) as stream:
            temporary = stream.name
            os.chmod(temporary, mode)
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        temporary = None
        os.chmod(path, mode)
    finally:
        if temporary is not None:
            try:
                Path(temporary).unlink()
            except FileNotFoundError:
                pass


def _atomic_write_json(path: Path, payload: dict[str, Any], mode: int = 0o600) -> None:
    content = (json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    _atomic_write_bytes(path, content, mode)


def _is_zcode_executable(command: str) -> bool:
    name = Path(command).name
    return (
        name == "ZCode"
        or name.startswith("ZCode Helper")
        or name == "ZCode Computer Use"
        or name.startswith("zcode-host-local")
        or name in {"zcode-cli", "zcode-node-repl-mcp"}
    )


def _parse_process_table(process_table: str) -> list[dict[str, Any]]:
    processes: list[dict[str, Any]] = []
    for line in process_table.splitlines():
        fields = line.strip().split(None, 2)
        if len(fields) != 3:
            continue
        pid_text, parent_text, command = fields
        if _is_zcode_executable(command):
            try:
                processes.append({"pid": int(pid_text), "ppid": int(parent_text), "command": command})
            except ValueError:
                continue
    return processes


def _processes_from_system() -> list[dict[str, Any]]:
    completed = subprocess.run(
        ["ps", "-axo", "pid=,ppid=,comm="],
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        raise RelocationError("unable to inspect running processes")
    return _parse_process_table(completed.stdout)


def _handles_from_system(processes: Sequence[dict[str, Any]], roots: Iterable[Path]) -> list[str]:
    pids = [str(item.get("pid")) for item in processes if isinstance(item.get("pid"), int)]
    if not pids:
        return []
    completed = subprocess.run(
        ["lsof", "-n", "-P", "-p", ",".join(pids)],
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode not in (0, 1):
        raise RelocationError("unable to inspect ZCode open files")
    prefixes = [str(root.absolute()) for root in roots]
    handles: list[str] = []
    for line in completed.stdout.splitlines():
        for prefix in prefixes:
            position = line.find(prefix)
            if position >= 0:
                handles.append(line[position:])
                break
    return sorted(set(handles))


def inspect_relocation(
    paths: RelocationPaths,
    *,
    active_processes: Sequence[dict[str, Any]] | None = None,
    source_handles: Sequence[str] | None = None,
    target_handles: Sequence[str] | None = None,
) -> dict[str, Any]:
    _validate_path_relationships(paths)
    processes = list(active_processes) if active_processes is not None else _processes_from_system()
    source_open = list(source_handles) if source_handles is not None else _handles_from_system(processes, (paths.source_root,))
    target_open = list(target_handles) if target_handles is not None else _handles_from_system(processes, (paths.target_root,))
    source_present = paths.source_root.exists()
    target_present = paths.target_root.exists()
    critical_complete = False
    critical_error: str | None = None
    selected_root: Path | None = paths.source_root if source_present else paths.target_root if target_present else None
    if selected_root is not None:
        try:
            _critical_inventory(selected_root)
            critical_complete = True
        except RelocationError as exc:
            critical_error = str(exc)
    settings = _settings_snapshot(paths.settings)
    payload = settings["payload"]
    return {
        "schema": INSPECTION_SCHEMA,
        "status": "active" if processes else "quiescent",
        "source_present": source_present,
        "target_present": target_present,
        "critical_complete": critical_complete,
        "critical_error": critical_error,
        "configured_base": payload.get("dataBaseDir"),
        "processes": [{"pid": item.get("pid"), "command": item.get("command")} for item in processes],
        "source_handles": source_open,
        "target_handles": target_open,
        "manifest_present": paths.manifest.exists(),
        "settings_sha256": settings["sha256"],
        "settings_unrelated_digest": settings["unrelated_digest"],
    }


def _require_quiescent(processes: Sequence[dict[str, Any]], handles: Sequence[str]) -> None:
    if processes:
        raise RelocationError("ZCode must be quiescent before relocation")
    if handles:
        raise RelocationError("source handle remains open before relocation")


def apply_relocation(
    paths: RelocationPaths,
    *,
    active_processes: Sequence[dict[str, Any]] | None = None,
    source_handles: Sequence[str] | None = None,
) -> dict[str, Any]:
    _validate_path_relationships(paths)
    processes = list(active_processes) if active_processes is not None else _processes_from_system()
    handles = list(source_handles) if source_handles is not None else _handles_from_system(processes, (paths.source_root,))
    _require_quiescent(processes, handles)
    if paths.target_root.exists():
        raise RelocationError(f"target already exists: {paths.target_root}")
    if paths.manifest.exists():
        raise RelocationError(f"manifest already exists: {paths.manifest}")
    source = _state_snapshot(paths.source_root)
    target_ancestor = _nearest_existing(paths.target_base)
    require_free_space(required_bytes=int(source["tree"]["bytes"]), available_bytes=shutil.disk_usage(target_ancestor).free)

    settings = _settings_snapshot(paths.settings)
    setting_payload = dict(settings["payload"])
    if setting_payload.get("dataBaseDir") != str(paths.source_base):
        raise RelocationError("settings dataBaseDir does not match the source base")
    backup_name = "setting.json.before"
    backup = paths.manifest.parent / backup_name
    if backup.exists():
        raise RelocationError(f"settings backup already exists: {backup}")

    paths.manifest.parent.mkdir(parents=True, exist_ok=True)
    original_settings = paths.settings.read_bytes()
    _atomic_write_bytes(backup, original_settings, int(settings["mode"]))
    paths.target_base.mkdir(parents=True, exist_ok=True)

    preparing = paths.target_base / f".zcode.preparing-{os.getpid()}"
    published = False
    try:
        shutil.copytree(paths.source_root, preparing, symlinks=True, copy_function=shutil.copy2)
        prepared = _state_snapshot(preparing)
        if prepared["tree"] != source["tree"] or prepared["critical"] != source["critical"]:
            raise RelocationError("copied state does not match the preflight inventory")
        os.replace(preparing, paths.target_root)
        published = True
        setting_payload["dataBaseDir"] = str(paths.target_base)
        _atomic_write_json(paths.settings, setting_payload, int(settings["mode"]))
    except Exception as exc:
        if preparing.exists():
            shutil.rmtree(preparing)
        if published and paths.target_root.exists():
            shutil.rmtree(paths.target_root)
        _atomic_write_bytes(paths.settings, original_settings, int(settings["mode"]))
        raise RelocationError(f"relocation transaction rolled back: {exc}") from exc

    after_settings = _settings_snapshot(paths.settings)
    target = _state_snapshot(paths.target_root)
    if target["tree"] != source["tree"] or target["critical"] != source["critical"]:
        shutil.rmtree(paths.target_root)
        _atomic_write_bytes(paths.settings, original_settings, int(settings["mode"]))
        raise RelocationError("relocated state does not match the preflight inventory")
    if after_settings["unrelated_digest"] != settings["unrelated_digest"]:
        shutil.rmtree(paths.target_root)
        _atomic_write_bytes(paths.settings, original_settings, int(settings["mode"]))
        raise RelocationError("unrelated settings changed; transaction rolled back")

    manifest: dict[str, Any] = {
        "schema": SCHEMA,
        "status": "applied",
        "source_base": str(paths.source_base),
        "source_root": str(paths.source_root),
        "target_base": str(paths.target_base),
        "target_root": str(paths.target_root),
        "settings": str(paths.settings),
        "settings_backup": backup_name,
        "settings_before_sha256": settings["sha256"],
        "settings_after_sha256": after_settings["sha256"],
        "settings_unrelated_digest": settings["unrelated_digest"],
        "settings_protected_digest": settings["protected_digest"],
        "source_device": source["device"],
        "source_inode": source["inode"],
        "target_inode": target["inode"],
        "tree": source["tree"],
        "critical": source["critical"],
        "rollback": "quiesce ZCode and restore settings backup; source remains intact until finalize",
    }
    _atomic_write_json(paths.manifest, manifest)
    return {
        "schema": SCHEMA,
        "status": "applied",
        "source_present": True,
        "target_present": paths.target_root.exists(),
        "manifest": str(paths.manifest),
        "tree": source["tree"],
    }


def verify_relocation(
    paths: RelocationPaths,
    *,
    active_processes: Sequence[dict[str, Any]] | None = None,
    source_handles: Sequence[str] | None = None,
    target_handles: Sequence[str] | None = None,
) -> dict[str, Any]:
    manifest = _load_json_mapping(paths.manifest, "manifest")
    if manifest.get("schema") != SCHEMA or manifest.get("status") not in {"applied", "recovered", "finalized"}:
        raise RelocationError("manifest is not a verifiable relocation receipt")
    if not paths.target_root.exists():
        raise RelocationError("target state is unavailable after relocation")
    _critical_inventory(paths.target_root)
    settings = _settings_snapshot(paths.settings)
    if settings["payload"].get("dataBaseDir") != str(paths.target_base):
        raise RelocationError("settings dataBaseDir does not match the target base")
    backup_name = manifest.get("settings_backup")
    if not isinstance(backup_name, str) or Path(backup_name).name != backup_name:
        raise RelocationError("manifest settings backup is invalid")
    backup = paths.manifest.parent / backup_name
    if _sha256_file(backup) != manifest.get("settings_before_sha256"):
        raise RelocationError("settings backup hash mismatch")
    backup_settings = _settings_snapshot(backup)
    expected_protected_digest = manifest.get("settings_protected_digest", backup_settings["protected_digest"])
    if backup_settings["protected_digest"] != expected_protected_digest:
        raise RelocationError("manifest protected settings digest mismatch")
    if settings["protected_digest"] != expected_protected_digest:
        raise RelocationError("protected settings drifted after relocation")

    processes = list(active_processes) if active_processes is not None else _processes_from_system()
    if not processes:
        raise RelocationError("restarted ZCode process is not present")
    source_open = list(source_handles) if source_handles is not None else _handles_from_system(processes, (paths.source_root,))
    if source_open:
        raise RelocationError("source handle remains after relocation")
    target_open = list(target_handles) if target_handles is not None else _handles_from_system(processes, (paths.target_root,))
    if not target_open:
        raise RelocationError("restarted ZCode has no target state handle")
    database_path = str(paths.target_state / "tasks-index.sqlite")
    if not any(handle.startswith(database_path) for handle in target_open):
        raise RelocationError("restarted ZCode has no target database handle")
    return {
        "schema": SCHEMA,
        "status": "relocated",
        "source_present": paths.source_root.exists(),
        "target_present": True,
        "process_count": len(processes),
        "source_handle_count": 0,
        "target_handle_count": len(target_open),
        "configured_base": str(paths.target_base),
    }


def rollback_relocation(
    paths: RelocationPaths,
    *,
    active_processes: Sequence[dict[str, Any]] | None = None,
    target_handles: Sequence[str] | None = None,
) -> dict[str, Any]:
    manifest = _load_json_mapping(paths.manifest, "manifest")
    if manifest.get("schema") != SCHEMA or manifest.get("status") not in {"applied", "finalized", "recovered"}:
        raise RelocationError("manifest is not a rollback-capable relocation receipt")
    processes = list(active_processes) if active_processes is not None else _processes_from_system()
    handles = list(target_handles) if target_handles is not None else _handles_from_system(processes, (paths.target_root,))
    if processes:
        raise RelocationError("ZCode must be quiescent before rollback")
    if handles:
        raise RelocationError("target handle remains open before rollback")
    if not paths.target_root.exists():
        raise RelocationError("target state is unavailable for rollback")
    _critical_inventory(paths.target_root)
    backup_name = manifest.get("settings_backup")
    if not isinstance(backup_name, str) or Path(backup_name).name != backup_name:
        raise RelocationError("manifest settings backup is invalid")
    backup = paths.manifest.parent / backup_name
    backup_bytes = backup.read_bytes()
    if _sha256_bytes(backup_bytes) != manifest.get("settings_before_sha256"):
        raise RelocationError("settings backup hash mismatch")

    recovery_source = paths.manifest.parent / "source-before-finalize.zcode"
    if not paths.source_root.exists() and recovery_source.exists():
        paths.source_base.mkdir(parents=True, exist_ok=True)
        os.replace(recovery_source, paths.source_root)
    if not paths.source_root.exists():
        raise RelocationError("rollback source is unavailable")
    _atomic_write_bytes(paths.settings, backup_bytes, paths.settings.stat().st_mode & 0o777)
    manifest["status"] = "rolled_back"
    _atomic_write_json(paths.manifest, manifest)
    return {
        "schema": SCHEMA,
        "status": "rolled_back",
        "source_present": paths.source_root.exists(),
        "target_present": True,
    }


def finalize_relocation(
    paths: RelocationPaths,
    *,
    active_processes: Sequence[dict[str, Any]] | None = None,
    source_handles: Sequence[str] | None = None,
    target_handles: Sequence[str] | None = None,
) -> dict[str, Any]:
    manifest = _load_json_mapping(paths.manifest, "manifest")
    if manifest.get("schema") != SCHEMA or manifest.get("status") != "applied":
        raise RelocationError("manifest is not ready for finalize")
    if not paths.source_root.exists() or not paths.target_root.exists():
        raise RelocationError("source and target must both exist before finalize")
    processes = list(active_processes) if active_processes is not None else _processes_from_system()
    if not processes:
        raise RelocationError("restarted ZCode process is not present")
    source_open = list(source_handles) if source_handles is not None else _handles_from_system(processes, (paths.source_root,))
    if source_open:
        raise RelocationError("source handle remains before finalize")
    target_open = list(target_handles) if target_handles is not None else _handles_from_system(processes, (paths.target_root,))
    database_path = str(paths.target_state / "tasks-index.sqlite")
    if not any(handle.startswith(database_path) for handle in target_open):
        raise RelocationError("restarted ZCode has no target database handle")
    recovery_source = paths.manifest.parent / "source-before-finalize.zcode"
    if recovery_source.exists():
        raise RelocationError("finalize recovery payload already exists")
    os.replace(paths.source_root, recovery_source)
    manifest["status"] = "finalized"
    manifest["finalized_source"] = recovery_source.name
    _atomic_write_json(paths.manifest, manifest)
    return {"schema": SCHEMA, "status": "finalized", "source_present": False, "target_present": True}


def default_process_probe() -> list[dict[str, Any]]:
    """Expose the process probe for the CLI without widening mutation authority."""

    return _processes_from_system()
