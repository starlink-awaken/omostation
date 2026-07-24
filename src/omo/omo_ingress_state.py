from __future__ import annotations

import importlib.util
import io
import sys
from contextlib import redirect_stdout
from copy import deepcopy
from pathlib import Path
from typing import Any

import yaml

from omo.omo_audit import record as record_audit
from omo.omo_governance_data import (
    build_governance_data,
    normalize_governance_data_json,
    serialize_governance_data,
)
from omo.omo_ingress_paths import (
    _audit_log_path,
    _delivery_root,
    _lock_path,
    _timestamp_slug,
    _utc_now,
    _workspace_relative,
)
from omo.omo_io import fcntl_lock, write_text_if_changed, write_yaml_atomic
from omo.omo_shared import load_yaml

STATE_SYNC_TARGET = (
    ".omo/state/health.yaml + .omo/state/system.yaml + "
    "BRIEF.md + .omo/_control/governance-data.json"
)


def _load_root_module(workspace_root: Path, name: str, relative_path: str):
    module_path = workspace_root / relative_path
    module_key = f"_workspace_{name.replace('-', '_')}"
    cached = sys.modules.get(module_key)
    if cached is not None:
        return cached
    spec = importlib.util.spec_from_file_location(module_key, module_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {name} from {module_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_key] = module
    spec.loader.exec_module(module)
    return module


def normalize_health_yaml(payload: str) -> str:
    """Compare health projection semantically, ignoring generation timestamps."""
    lines = []
    for line in payload.splitlines():
        if line.startswith(("# generated_at:", "generated_at:")):
            continue
        lines.append(line)
    return "\n".join(lines).strip()


def normalize_system_yaml(payload: str) -> str:
    data = yaml.safe_load(payload) or {}
    if isinstance(data, dict):
        data = deepcopy(data)
        data.pop("health_score_generated_at", None)
    return yaml.safe_dump(data, allow_unicode=True, sort_keys=True)


def normalize_brief_md(payload: str) -> str:
    lines = []
    for line in payload.splitlines():
        if line.startswith("> **Generated**:"):
            lines.append("> **Generated**: `<runtime>`")
        else:
            lines.append(line)
    return "\n".join(lines).strip()


def _build_health_projection(workspace_root: Path) -> tuple[str, dict[str, Any]]:
    compass_radar = _load_root_module(
        workspace_root, "compass_radar", "bin/compass_radar.py"
    )
    omo_dir = workspace_root / ".omo"
    output = omo_dir / "state" / "health.yaml"
    with redirect_stdout(io.StringIO()):
        report, _runtime_summary, _age_desc = compass_radar.build_health_projection(
            omo_dir=omo_dir,
            output=output,
        )
    return compass_radar.render_yaml(
        report
    ), compass_radar.build_system_projection_updates(
        workspace_root=workspace_root,
        report=report,
    )


def _build_brief_content(workspace_root: Path) -> str:
    generate_brief = _load_root_module(
        workspace_root, "generate-brief", "bin/mof/generate-brief.py"
    )
    return generate_brief.generate_brief_content()


def _system_payload(
    system_path: Path,
    system_updates: dict[str, Any],
) -> str:
    payload = load_yaml(system_path)
    if not isinstance(payload, dict):
        raise ValueError(
            f"state/system.yaml top-level must be a mapping: {system_path}"
        )
    payload.update(deepcopy(system_updates))
    return yaml.safe_dump(payload, allow_unicode=True, sort_keys=False)


def _preview_write(
    path: Path,
    payload: str,
    *,
    normalize,
) -> dict[str, Any]:
    if not path.exists():
        return {"path": str(path), "changed": True, "reason": "missing"}
    current = path.read_text(encoding="utf-8")
    changed = normalize(current) != normalize(payload)
    return {
        "path": str(path),
        "changed": changed,
        "reason": "content" if changed else "unchanged",
    }


def _write_or_preview(
    path: Path,
    payload: str,
    *,
    normalize,
    dry_run: bool,
) -> dict[str, Any]:
    preview = _preview_write(path, payload, normalize=normalize)
    if not dry_run and preview["changed"]:
        changed = write_text_if_changed(path, payload, normalize=normalize)
        preview["changed"] = changed
        preview["reason"] = "written" if changed else "unchanged"
    return preview


def _mirror_projection(path: Path, content: str, normalize=None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    write_text_if_changed(path, content, normalize=normalize or (lambda x: x))


def _record_state_sync(
    omo_dir: Path,
    *,
    actor: str,
    source_ref: str,
    timestamp: str,
    writes: list[dict[str, Any]],
) -> str:
    from omo.omo_ingress import _record_mutation, _record_trail

    changed_paths = [
        _workspace_relative(Path(item["path"]), workspace_root=omo_dir.parent)
        for item in writes
        if item.get("changed")
    ]
    artifact = {
        "kind": "state_projection_sync",
        "actor": actor,
        "source_ref": source_ref,
        "created_at": timestamp,
        "target": STATE_SYNC_TARGET,
        "changed_paths": changed_paths,
        "write_count": len(changed_paths),
        "writes": [
            {
                **item,
                "path": _workspace_relative(
                    Path(str(item["path"])), workspace_root=omo_dir.parent
                ),
            }
            for item in writes
        ],
    }
    artifact_path = (
        _delivery_root(omo_dir)
        / "state"
        / f"state-sync-{_timestamp_slug(timestamp)}.yaml"
    )
    write_yaml_atomic(artifact_path, artifact)
    artifact_ref = _workspace_relative(artifact_path, workspace_root=omo_dir.parent)
    details = (
        f"actor={actor} source_ref={source_ref or '-'} "
        f"changed={','.join(changed_paths) if changed_paths else '-'} artifact={artifact_ref}"
    )
    record_audit(
        action="ingress_sync_state_projection",
        debt_id="",
        actor=actor,
        details=details,
        audit_file=_audit_log_path(omo_dir),
    )
    _record_trail(
        omo_dir,
        actor=f"broker:{actor}",
        action="sync_state_projection",
        target=STATE_SYNC_TARGET,
        parent_step_id=f"ingress:state-sync:{timestamp}",
    )
    _record_mutation(
        omo_dir,
        actor=actor,
        action="sync_state_projection",
        target=STATE_SYNC_TARGET,
        artifact_ref=artifact_ref,
        source_ref=source_ref,
        broker_ref="projects/omo/src/omo/omo_ingress_state.py:sync_state_projection",
        created_at=timestamp,
        extra={"changed_paths": changed_paths, "write_count": len(changed_paths)},
    )
    return artifact_ref


def sync_state_projection(
    workspace_root: Path,
    *,
    dry_run: bool = False,
    actor: str = "omo state sync",
    source_ref: str = "omo-state:sync",
    health_content: str | None = None,
    system_updates: dict[str, Any] | None = None,
    brief_content: str | None = None,
    governance_data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Synchronize high-churn runtime projections through one OMO writer."""
    workspace_root = workspace_root.resolve()
    omo_dir = workspace_root / ".omo"
    if not omo_dir.is_dir():
        raise FileNotFoundError(f"missing .omo directory: {omo_dir}")

    timestamp = _utc_now()
    runtime_state_dir = omo_dir / "state" / "runtime"
    runtime_state_dir.mkdir(parents=True, exist_ok=True)

    # Canonical paths under .omo/state/runtime/ (ADR-0129)
    health_path = runtime_state_dir / "health.yaml"
    brief_path = runtime_state_dir / "brief.md"
    governance_data_path = runtime_state_dir / "governance-data.json"

    # Legacy paths kept during ADR-0129 migration (ADR-0129 Phase 1 dual-write)
    legacy_health_path = omo_dir / "state" / "health.yaml"
    legacy_brief_path = workspace_root / "BRIEF.md"
    legacy_governance_data_path = omo_dir / "_control" / "governance-data.json"

    system_path = omo_dir / "state" / "system.yaml"

    with fcntl_lock(_lock_path(omo_dir)):
        if health_content is None or system_updates is None:
            health_content, system_updates = _build_health_projection(workspace_root)
        system_updates = dict(system_updates)
        system_updates["governance_feedback_last_run"] = timestamp
        system_updates["updated_at"] = timestamp
        system_payload = _system_payload(system_path, system_updates)
        writes = [
            _write_or_preview(
                health_path,
                health_content,
                normalize=normalize_health_yaml,
                dry_run=dry_run,
            ),
            _write_or_preview(
                system_path,
                system_payload,
                normalize=normalize_system_yaml,
                dry_run=dry_run,
            ),
        ]
        if brief_content is None:
            brief_content = _build_brief_content(workspace_root)
        if governance_data is None:
            governance_data = build_governance_data(workspace_root)
        writes.extend(
            [
                _write_or_preview(
                    brief_path,
                    brief_content,
                    normalize=normalize_brief_md,
                    dry_run=dry_run,
                ),
                _write_or_preview(
                    governance_data_path,
                    serialize_governance_data(governance_data),
                    normalize=normalize_governance_data_json,
                    dry_run=dry_run,
                ),
            ]
        )

        # ADR-0129 Phase 1: dual-write legacy paths for backward compatibility.
        # These are shallow copies and are not recorded as separate mutations;
        # the canonical writes above hold the authoritative projection state.
        if not dry_run:
            _mirror_projection(
                legacy_health_path, health_content, normalize=normalize_health_yaml
            )
            _mirror_projection(
                legacy_brief_path, brief_content, normalize=normalize_brief_md
            )
            _mirror_projection(
                legacy_governance_data_path,
                serialize_governance_data(governance_data),
                normalize=normalize_governance_data_json,
            )
        changed_count = sum(1 for item in writes if item.get("changed"))
        artifact_ref = ""
        if not dry_run and changed_count:
            artifact_ref = _record_state_sync(
                omo_dir,
                actor=actor,
                source_ref=source_ref,
                timestamp=timestamp,
                writes=writes,
            )

    return {
        "ok": True,
        "dry_run": dry_run,
        "actor": actor,
        "source_ref": source_ref,
        "target": STATE_SYNC_TARGET,
        "changed_count": changed_count,
        "artifact_ref": artifact_ref,
        "writes": [
            {
                **item,
                "path": _workspace_relative(
                    Path(str(item["path"])), workspace_root=workspace_root
                ),
            }
            for item in writes
        ],
    }
