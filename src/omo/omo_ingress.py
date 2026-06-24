from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any


from omo.omo_audit import record as record_audit
from omo.omo_io import AppendOnlyLog, fcntl_lock, write_text_atomic, write_yaml_atomic
from omo.omo_io_schemas import OmoTrailRecord
from omo.omo_promotion_request import (
    build_promotion_approval_request,
    promotion_approval_ref,
)
from omo.omo_task_schema import validate_task_data
from omo.omo_ingress_paths import (
    _artifact_lifecycle_fields,
    _audit_log_path,
    _delivery_root,
    _find_task_path,
    _load_yaml,
    _lock_path,
    _mutation_log_path,
    _registry_path,
    _safe_doc_name,
    _timestamp_slug,
    _trail_log_path,
    _utc_now,
)


def _load_registry(omo_dir: Path) -> dict[str, Any]:
    path = _registry_path(omo_dir)
    if not path.exists():
        return {
            "goals": {"by_id": {}, "by_source_ref": {}},
            "tasks": {"by_id": {}, "by_source_ref": {}},
            "debts": {"by_id": {}, "by_source_ref": {}},
            "capabilities": {"by_id": {}, "by_source_ref": {}},
        }
    data = _load_yaml(path)
    for key in ("goals", "tasks", "debts", "capabilities"):
        data.setdefault(key, {})
        data[key].setdefault("by_id", {})
        data[key].setdefault("by_source_ref", {})
    return data


def _write_registry(omo_dir: Path, registry: dict[str, Any]) -> None:
    write_yaml_atomic(_registry_path(omo_dir), registry)


def _record_mutation(
    omo_dir: Path,
    *,
    actor: str,
    action: str,
    target: str,
    artifact_ref: str,
    source_ref: str,
    broker_ref: str = "projects/omo/src/omo/omo_ingress.py",
    created_at: str | None = None,
    extra: dict[str, Any] | None = None,
) -> None:
    record: dict[str, Any] = {
        "created_at": created_at or _utc_now(),
        "actor": actor,
        "action": action,
        "target": target,
        "artifact_ref": artifact_ref,
        "source_ref": source_ref,
        "broker_ref": broker_ref,
        "result": "committed",
    }
    if extra:
        record.update(deepcopy(extra))
    AppendOnlyLog(_mutation_log_path(omo_dir)).append(record, sort_keys=False)


def _goal_fingerprint(
    *,
    goal_id: str,
    title: str,
    description: str,
    ingress_plane: str,
    source_ref: str,
    extra_fields: dict[str, Any] | None,
) -> dict[str, Any]:
    payload = {
        "id": goal_id,
        "title": title,
        "desc": description,
        "ingress_plane": ingress_plane,
        "source_ref": source_ref,
    }
    if extra_fields:
        payload["extra_fields"] = deepcopy(extra_fields)
    return payload


def _goal_existing_fingerprint(existing: dict[str, Any]) -> dict[str, Any]:
    payload = {
        "id": existing.get("id"),
        "title": existing.get("title", ""),
        "desc": existing.get("desc", ""),
        "ingress_plane": existing.get("ingress_plane", ""),
        "source_ref": existing.get("source_ref", ""),
    }
    extra_fields = {
        key: deepcopy(value)
        for key, value in existing.items()
        if key
        not in {
            "id",
            "title",
            "desc",
            "progress",
            "status",
            "tasks",
            "ingress_plane",
            "source_ref",
            "created_at",
        }
    }
    if extra_fields:
        payload["extra_fields"] = extra_fields
    return payload


def _task_payload_with_metadata(
    task_data: dict[str, Any],
    *,
    ingress_plane: str,
    source_ref: str,
) -> dict[str, Any]:
    payload = deepcopy(task_data)
    metadata = payload.setdefault("metadata", {})
    if isinstance(metadata, dict):
        metadata.setdefault("ingress_plane", ingress_plane)
        metadata.setdefault("broker", "projects/omo/src/omo/omo_ingress.py")
        if source_ref:
            metadata.setdefault("source_ref", source_ref)
    return payload


def _register_ingress(
    registry: dict[str, Any],
    *,
    kind: str,
    item_id: str,
    source_ref: str,
    artifact_ref: str,
    fingerprint: dict[str, Any],
    created_at: str,
) -> None:
    bucket = registry[kind]
    bucket["by_id"][item_id] = {
        "source_ref": source_ref,
        "artifact_ref": artifact_ref,
        "fingerprint": deepcopy(fingerprint),
        "created_at": created_at,
    }
    if source_ref:
        bucket["by_source_ref"][source_ref] = item_id


def _resolve_existing_goal(omo_dir: Path, goal_id: str) -> dict[str, Any] | None:
    goal_file = omo_dir / "goals" / "current.yaml"
    if not goal_file.exists():
        return None
    payload = _load_yaml(goal_file)
    for goal in payload.get("goals", []):
        if goal.get("id") == goal_id:
            return goal
    return None


def _record_trail(
    omo_dir: Path,
    *,
    actor: str,
    action: str,
    target: str,
    parent_step_id: str,
) -> None:
    trail_record = OmoTrailRecord(
        ts=_utc_now(),
        actor=actor,
        action=action,
        target=target,
        status="ok",
        duration_ms=0,
        parent_step_id=parent_step_id,
    )
    AppendOnlyLog(_trail_log_path(omo_dir)).append(
        trail_record.model_dump(), schema=OmoTrailRecord, sort_keys=True
    )


def create_goal(
    omo_dir: Path,
    *,
    goal_id: str,
    title: str,
    description: str,
    ingress_plane: str,
    source_ref: str = "",
    extra_fields: dict[str, Any] | None = None,
    now: str | None = None,
) -> dict[str, Any]:
    goal_file = omo_dir / "goals" / "current.yaml"
    if not goal_file.exists():
        raise FileNotFoundError(f"missing goals/current.yaml: {goal_file}")

    timestamp = now or _utc_now()
    fingerprint = _goal_fingerprint(
        goal_id=goal_id,
        title=title,
        description=description,
        ingress_plane=ingress_plane,
        source_ref=source_ref,
        extra_fields=extra_fields,
    )
    artifact_ref = f".omo/_delivery/ingress/goals/{goal_id}.yaml"

    with fcntl_lock(_lock_path(omo_dir)):
        registry = _load_registry(omo_dir)
        existing_goal = _resolve_existing_goal(omo_dir, goal_id)

        if source_ref:
            mapped_goal_id = registry["goals"]["by_source_ref"].get(source_ref)
            if mapped_goal_id and mapped_goal_id != goal_id:
                raise ValueError(
                    f"source_ref already mapped to different goal: {source_ref} -> {mapped_goal_id}"
                )

        if existing_goal is not None:
            existing_fingerprint = _goal_existing_fingerprint(existing_goal)
            if existing_fingerprint == fingerprint:
                _register_ingress(
                    registry,
                    kind="goals",
                    item_id=goal_id,
                    source_ref=source_ref,
                    artifact_ref=artifact_ref,
                    fingerprint=fingerprint,
                    created_at=str(existing_goal.get("created_at", timestamp)),
                )
                _write_registry(omo_dir, registry)
                return existing_goal
            raise ValueError(f"goal already exists with different payload: {goal_id}")

        payload = _load_yaml(goal_file)
        goals = payload.get("goals", [])
        new_goal: dict[str, Any] = {
            "id": goal_id,
            "title": title,
            "desc": description,
            "progress": 0.0,
            "status": "pending",
            "tasks": [],
            "ingress_plane": ingress_plane,
            "source_ref": source_ref,
            "created_at": timestamp,
        }
        if extra_fields:
            new_goal.update(deepcopy(extra_fields))

        goals.append(new_goal)
        payload["goals"] = goals
        write_yaml_atomic(goal_file, payload)

        artifact = {
            "kind": "goal_created",
            "goal_id": goal_id,
            "title": title,
            "ingress_plane": ingress_plane,
            "source_ref": source_ref,
            "created_at": timestamp,
            "goal_ref": ".omo/goals/current.yaml",
            **_artifact_lifecycle_fields(artifact_ref=artifact_ref),
        }
        artifact_path = _delivery_root(omo_dir) / "goals" / f"{goal_id}.yaml"
        write_yaml_atomic(artifact_path, artifact)
        _register_ingress(
            registry,
            kind="goals",
            item_id=goal_id,
            source_ref=source_ref,
            artifact_ref=artifact_ref,
            fingerprint=fingerprint,
            created_at=timestamp,
        )
        _write_registry(omo_dir, registry)

        parent_step_id = f"ingress:goal:{goal_id}:{timestamp}"
        details = (
            f"goal_id={goal_id} ingress_plane={ingress_plane} "
            f"source_ref={source_ref or '-'} artifact={artifact_path.relative_to(omo_dir.parent)}"
        )
        record_audit(
            action="ingress_create_goal",
            debt_id="",
            actor=ingress_plane,
            details=details,
            audit_file=_audit_log_path(omo_dir),
        )
        _record_trail(
            omo_dir,
            actor=f"broker:{ingress_plane}",
            action="create_goal",
            target=f".omo/goals/current.yaml#{goal_id}",
            parent_step_id=parent_step_id,
        )
        _record_mutation(
            omo_dir,
            actor=ingress_plane,
            action="create_goal",
            target=f".omo/goals/current.yaml#{goal_id}",
            artifact_ref=artifact["artifact_ref"],
            source_ref=source_ref,
            created_at=timestamp,
            extra={"goal_id": goal_id, "ingress_plane": ingress_plane},
        )
        return new_goal


def update_goal_progress(
    omo_dir: Path,
    *,
    goal_id: str,
    progress: float,
    actor: str,
    source_ref: str = "",
    now: str | None = None,
) -> dict[str, Any]:
    goal_file = omo_dir / "goals" / "current.yaml"
    if not goal_file.exists():
        raise FileNotFoundError(f"missing goals/current.yaml: {goal_file}")

    timestamp = now or _utc_now()
    with fcntl_lock(_lock_path(omo_dir)):
        payload = _load_yaml(goal_file)
        goals = payload.get("goals", [])
        target_goal: dict[str, Any] | None = None
        for goal in goals:
            if goal.get("id") == goal_id:
                target_goal = goal
                break
        if target_goal is None:
            raise ValueError(f"goal not found: {goal_id}")

        previous_progress = float(target_goal.get("progress", 0.0))
        previous_status = str(target_goal.get("status", "pending"))
        target_goal["progress"] = progress
        if progress >= 100:
            target_goal["status"] = "done"
        elif progress > 0:
            target_goal["status"] = "active"
        else:
            target_goal["status"] = "pending"
        write_yaml_atomic(goal_file, payload)

        artifact = {
            "kind": "goal_progress_updated",
            "goal_id": goal_id,
            "goal_ref": ".omo/goals/current.yaml",
            "progress": progress,
            "previous_progress": previous_progress,
            "status": target_goal["status"],
            "previous_status": previous_status,
            "actor": actor,
            "source_ref": source_ref,
            "updated_at": timestamp,
        }
        artifact_path = (
            _delivery_root(omo_dir)
            / "goals"
            / f"{goal_id}-progress-{_timestamp_slug(timestamp)}.yaml"
        )
        write_yaml_atomic(artifact_path, artifact)

        parent_step_id = f"ingress:goal-progress:{goal_id}:{timestamp}"
        details = (
            f"goal_id={goal_id} actor={actor} progress={progress} "
            f"source_ref={source_ref or '-'} artifact={artifact_path.relative_to(omo_dir.parent)}"
        )
        record_audit(
            action="ingress_update_goal_progress",
            debt_id="",
            actor=actor,
            details=details,
            audit_file=_audit_log_path(omo_dir),
        )
        _record_trail(
            omo_dir,
            actor=f"broker:{actor}",
            action="update_goal_progress",
            target=f".omo/goals/current.yaml#{goal_id}",
            parent_step_id=parent_step_id,
        )
        _record_mutation(
            omo_dir,
            actor=actor,
            action="update_goal_progress",
            target=f".omo/goals/current.yaml#{goal_id}",
            artifact_ref=f".omo/_delivery/ingress/goals/{artifact_path.name}",
            source_ref=source_ref,
            created_at=timestamp,
            extra={"goal_id": goal_id, "progress": progress},
        )
        return deepcopy(target_goal)


def create_knowledge_doc(
    omo_dir: Path,
    *,
    plane: str,
    title: str,
    content: str,
    actor: str,
    source_ref: str = "",
    now: str | None = None,
) -> dict[str, Any]:
    timestamp = now or _utc_now()
    safe_name = _safe_doc_name(title)
    doc_path = omo_dir / "_knowledge" / plane / f"{safe_name}.md"

    with fcntl_lock(_lock_path(omo_dir)):
        if doc_path.exists():
            raise ValueError(f"{doc_path.name} already exists")
        write_text_atomic(doc_path, f"# {title}\n\n{content}\n")
        artifact = {
            "kind": "knowledge_doc_created",
            "plane": plane,
            "title": title,
            "doc_ref": f".omo/_knowledge/{plane}/{safe_name}.md",
            "actor": actor,
            "source_ref": source_ref,
            "created_at": timestamp,
        }
        artifact_path = (
            _delivery_root(omo_dir)
            / "knowledge"
            / f"{plane}-{safe_name}-{_timestamp_slug(timestamp)}.yaml"
        )
        write_yaml_atomic(artifact_path, artifact)
        parent_step_id = f"ingress:knowledge:{plane}:{safe_name}:{timestamp}"
        details = (
            f"plane={plane} title={title} actor={actor} "
            f"source_ref={source_ref or '-'} artifact={artifact_path.relative_to(omo_dir.parent)}"
        )
        record_audit(
            action="ingress_create_knowledge_doc",
            debt_id="",
            actor=actor,
            details=details,
            audit_file=_audit_log_path(omo_dir),
        )
        _record_trail(
            omo_dir,
            actor=f"broker:{actor}",
            action="create_knowledge_doc",
            target=f".omo/_knowledge/{plane}/{safe_name}.md",
            parent_step_id=parent_step_id,
        )
        _record_mutation(
            omo_dir,
            actor=actor,
            action="create_knowledge_doc",
            target=f".omo/_knowledge/{plane}/{safe_name}.md",
            artifact_ref=f".omo/_delivery/ingress/knowledge/{artifact_path.name}",
            source_ref=source_ref,
            created_at=timestamp,
            extra={"plane": plane, "title": title},
        )
        return artifact


def create_standard_doc(
    omo_dir: Path,
    *,
    title: str,
    content: str,
    actor: str,
    source_ref: str = "",
    now: str | None = None,
) -> dict[str, Any]:
    timestamp = now or _utc_now()
    safe_name = _safe_doc_name(title)
    doc_path = omo_dir / "standards" / f"{safe_name}.md"

    with fcntl_lock(_lock_path(omo_dir)):
        if doc_path.exists():
            raise ValueError(f"{doc_path.name} already exists")
        write_text_atomic(doc_path, f"# {title}\n\n{content}\n")
        artifact = {
            "kind": "standard_doc_created",
            "title": title,
            "doc_ref": f".omo/standards/{safe_name}.md",
            "actor": actor,
            "source_ref": source_ref,
            "created_at": timestamp,
        }
        artifact_path = (
            _delivery_root(omo_dir)
            / "standards"
            / f"{safe_name}-{_timestamp_slug(timestamp)}.yaml"
        )
        write_yaml_atomic(artifact_path, artifact)
        parent_step_id = f"ingress:standard:{safe_name}:{timestamp}"
        details = (
            f"title={title} actor={actor} source_ref={source_ref or '-'} "
            f"artifact={artifact_path.relative_to(omo_dir.parent)}"
        )
        record_audit(
            action="ingress_create_standard_doc",
            debt_id="",
            actor=actor,
            details=details,
            audit_file=_audit_log_path(omo_dir),
        )
        _record_trail(
            omo_dir,
            actor=f"broker:{actor}",
            action="create_standard_doc",
            target=f".omo/standards/{safe_name}.md",
            parent_step_id=parent_step_id,
        )
        _record_mutation(
            omo_dir,
            actor=actor,
            action="create_standard_doc",
            target=f".omo/standards/{safe_name}.md",
            artifact_ref=f".omo/_delivery/ingress/standards/{artifact_path.name}",
            source_ref=source_ref,
            created_at=timestamp,
            extra={"title": title},
        )
        return artifact


def write_capability_registry_bundle(
    omo_dir: Path,
    *,
    bundle: dict[str, Any],
    actor: str,
    source_ref: str = "",
    now: str | None = None,
) -> dict[str, Any]:
    timestamp = now or _utc_now()
    capabilities_dir = omo_dir / "capabilities"
    index_content = str(bundle["index_content"])
    registries = deepcopy(bundle.get("registries") or {})
    if not isinstance(registries, dict) or not registries:
        raise ValueError("capability registries missing")
    artifact_ref = (
        f".omo/_delivery/ingress/capabilities/bundle-{_timestamp_slug(timestamp)}.yaml"
    )
    fingerprint = {
        "kind": "bundle",
        "registry_files": sorted(registries.keys()),
        "source_ref": source_ref,
    }

    with fcntl_lock(_lock_path(omo_dir)):
        registry = _load_registry(omo_dir)
        capabilities_dir.mkdir(parents=True, exist_ok=True)
        write_text_atomic(capabilities_dir / "INDEX.md", index_content)
        registry_refs: list[str] = [".omo/capabilities/INDEX.md"]
        for filename, payload in sorted(registries.items()):
            if not filename.endswith(".yaml"):
                raise ValueError(f"invalid capability registry filename: {filename}")
            write_yaml_atomic(capabilities_dir / filename, payload)
            registry_refs.append(f".omo/capabilities/{filename}")
        artifact = {
            "kind": "capability_registry_bundle_written",
            "capability_registry_id": "bundle",
            "registry_refs": registry_refs,
            "ingress_plane": "projects/omo",
            "actor": actor,
            "source_ref": source_ref,
            "created_at": timestamp,
            "written_at": timestamp,
        }
        artifact_path = (
            _delivery_root(omo_dir)
            / "capabilities"
            / f"bundle-{_timestamp_slug(timestamp)}.yaml"
        )
        write_yaml_atomic(artifact_path, artifact)
        _register_ingress(
            registry,
            kind="capabilities",
            item_id="bundle",
            source_ref=source_ref,
            artifact_ref=artifact_ref,
            fingerprint=fingerprint,
            created_at=timestamp,
        )
        _write_registry(omo_dir, registry)
        parent_step_id = f"ingress:capability-bundle:{timestamp}"
        details = (
            f"actor={actor} source_ref={source_ref or '-'} "
            f"registry_count={len(registry_refs)} "
            f"artifact={artifact_path.relative_to(omo_dir.parent)}"
        )
        record_audit(
            action="ingress_write_capability_registry_bundle",
            debt_id="",
            actor=actor,
            details=details,
            audit_file=_audit_log_path(omo_dir),
        )
        _record_trail(
            omo_dir,
            actor=f"broker:{actor}",
            action="write_capability_registry_bundle",
            target=".omo/capabilities/",
            parent_step_id=parent_step_id,
        )
        _record_mutation(
            omo_dir,
            actor=actor,
            action="write_capability_registry_bundle",
            target=".omo/capabilities/",
            artifact_ref=artifact_ref,
            source_ref=source_ref,
            created_at=timestamp,
            extra={"registry_refs": registry_refs},
        )
        return artifact


def write_manual_capabilities(
    omo_dir: Path,
    *,
    payload: dict[str, Any],
    actor: str,
    source_ref: str = "",
    now: str | None = None,
) -> dict[str, Any]:
    timestamp = now or _utc_now()
    registry_path = omo_dir / "capabilities" / "manual-capabilities.yaml"
    artifact_ref = f".omo/_delivery/ingress/capabilities/manual-capabilities-{_timestamp_slug(timestamp)}.yaml"
    fingerprint = {
        "kind": "manual-capabilities",
        "capability_count": len(payload.get("capabilities", []))
        if isinstance(payload, dict)
        else 0,
        "source_ref": source_ref,
    }

    with fcntl_lock(_lock_path(omo_dir)):
        registry = _load_registry(omo_dir)
        write_yaml_atomic(registry_path, payload)
        artifact = {
            "kind": "manual_capabilities_written",
            "capability_registry_id": "manual-capabilities",
            "registry_ref": ".omo/capabilities/manual-capabilities.yaml",
            "ingress_plane": "projects/omo",
            "actor": actor,
            "source_ref": source_ref,
            "created_at": timestamp,
            "written_at": timestamp,
        }
        artifact_path = (
            _delivery_root(omo_dir)
            / "capabilities"
            / f"manual-capabilities-{_timestamp_slug(timestamp)}.yaml"
        )
        write_yaml_atomic(artifact_path, artifact)
        _register_ingress(
            registry,
            kind="capabilities",
            item_id="manual-capabilities",
            source_ref=source_ref,
            artifact_ref=artifact_ref,
            fingerprint=fingerprint,
            created_at=timestamp,
        )
        _write_registry(omo_dir, registry)
        parent_step_id = f"ingress:manual-capabilities:{timestamp}"
        details = (
            f"actor={actor} source_ref={source_ref or '-'} "
            f"artifact={artifact_path.relative_to(omo_dir.parent)}"
        )
        record_audit(
            action="ingress_write_manual_capabilities",
            debt_id="",
            actor=actor,
            details=details,
            audit_file=_audit_log_path(omo_dir),
        )
        _record_trail(
            omo_dir,
            actor=f"broker:{actor}",
            action="write_manual_capabilities",
            target=".omo/capabilities/manual-capabilities.yaml",
            parent_step_id=parent_step_id,
        )
        _record_mutation(
            omo_dir,
            actor=actor,
            action="write_manual_capabilities",
            target=".omo/capabilities/manual-capabilities.yaml",
            artifact_ref=artifact_ref,
            source_ref=source_ref,
            created_at=timestamp,
            extra={"capability_count": len(payload.get("capabilities", [])) if isinstance(payload, dict) else 0},
        )
        return deepcopy(payload)


def create_skill_manifest(
    omo_dir: Path,
    *,
    manifest: dict[str, Any],
    actor: str,
    source_ref: str = "",
    now: str | None = None,
) -> dict[str, Any]:
    skill_id = str(manifest["id"])
    timestamp = now or _utc_now()
    manifest_path = omo_dir / "_truth" / "task-center" / "skills" / f"{skill_id}.yaml"

    with fcntl_lock(_lock_path(omo_dir)):
        write_yaml_atomic(manifest_path, manifest)
        artifact = {
            "kind": "skill_manifest_written",
            "skill_id": skill_id,
            "manifest_ref": f".omo/_truth/task-center/skills/{skill_id}.yaml",
            "actor": actor,
            "source_ref": source_ref,
            "written_at": timestamp,
        }
        artifact_path = (
            _delivery_root(omo_dir) / "task-center" / "skills" / f"{skill_id}.yaml"
        )
        write_yaml_atomic(artifact_path, artifact)
        parent_step_id = f"ingress:skill-manifest:{skill_id}:{timestamp}"
        details = (
            f"skill_id={skill_id} actor={actor} source_ref={source_ref or '-'} "
            f"artifact={artifact_path.relative_to(omo_dir.parent)}"
        )
        record_audit(
            action="ingress_create_skill_manifest",
            debt_id="",
            actor=actor,
            details=details,
            audit_file=_audit_log_path(omo_dir),
        )
        _record_trail(
            omo_dir,
            actor=f"broker:{actor}",
            action="create_skill_manifest",
            target=f".omo/_truth/task-center/skills/{skill_id}.yaml",
            parent_step_id=parent_step_id,
        )
        _record_mutation(
            omo_dir,
            actor=actor,
            action="create_skill_manifest",
            target=f".omo/_truth/task-center/skills/{skill_id}.yaml",
            artifact_ref=f".omo/_delivery/ingress/task-center/skills/{skill_id}.yaml",
            source_ref=source_ref,
            created_at=timestamp,
            extra={"skill_id": skill_id},
        )
        return deepcopy(manifest)


def write_discovery_registry(
    omo_dir: Path,
    *,
    registry: dict[str, Any],
    actor: str,
    source_ref: str = "",
    now: str | None = None,
) -> dict[str, Any]:
    timestamp = now or _utc_now()
    registry_path = omo_dir / "_truth" / "task-center" / "discovery-registry.yaml"

    with fcntl_lock(_lock_path(omo_dir)):
        write_yaml_atomic(registry_path, registry)
        artifact = {
            "kind": "discovery_registry_written",
            "registry_ref": ".omo/_truth/task-center/discovery-registry.yaml",
            "actor": actor,
            "source_ref": source_ref,
            "written_at": timestamp,
        }
        artifact_path = (
            _delivery_root(omo_dir)
            / "task-center"
            / "discovery"
            / f"discovery-registry-{_timestamp_slug(timestamp)}.yaml"
        )
        write_yaml_atomic(artifact_path, artifact)
        parent_step_id = f"ingress:discovery-registry:{timestamp}"
        details = (
            f"actor={actor} source_ref={source_ref or '-'} "
            f"artifact={artifact_path.relative_to(omo_dir.parent)}"
        )
        record_audit(
            action="ingress_write_discovery_registry",
            debt_id="",
            actor=actor,
            details=details,
            audit_file=_audit_log_path(omo_dir),
        )
        _record_trail(
            omo_dir,
            actor=f"broker:{actor}",
            action="write_discovery_registry",
            target=".omo/_truth/task-center/discovery-registry.yaml",
            parent_step_id=parent_step_id,
        )
        _record_mutation(
            omo_dir,
            actor=actor,
            action="write_discovery_registry",
            target=".omo/_truth/task-center/discovery-registry.yaml",
            artifact_ref=f".omo/_delivery/ingress/task-center/discovery/{artifact_path.name}",
            source_ref=source_ref,
            created_at=timestamp,
        )
        return deepcopy(registry)


def write_system_projection_fields(
    omo_dir: Path,
    *,
    updates: dict[str, Any],
    actor: str,
    source_ref: str = "",
    now: str | None = None,
    allowed_fields: set[str] | frozenset[str] | None = None,
) -> dict[str, Any]:
    timestamp = now or _utc_now()
    system_path = omo_dir / "state" / "system.yaml"
    if not system_path.exists():
        raise FileNotFoundError(f"missing state/system.yaml: {system_path}")
    if not isinstance(updates, dict) or not updates:
        raise ValueError("system projection updates must be a non-empty mapping")

    allowed = set(allowed_fields or updates.keys())
    invalid = sorted(key for key in updates if key not in allowed)
    if invalid:
        raise ValueError(
            f"system projection contains non-whitelisted fields: {invalid}"
        )

    with fcntl_lock(_lock_path(omo_dir)):
        payload = _load_yaml(system_path)
        if not isinstance(payload, dict):
            raise ValueError("state/system.yaml top-level must be a mapping")
        for key, value in updates.items():
            payload[key] = deepcopy(value)
        write_yaml_atomic(system_path, payload)

        artifact = {
            "kind": "system_projection_fields_written",
            "system_ref": ".omo/state/system.yaml",
            "updated_fields": sorted(updates.keys()),
            "actor": actor,
            "source_ref": source_ref,
            "updated_at": timestamp,
        }
        artifact_path = (
            _delivery_root(omo_dir)
            / "state"
            / f"system-projection-{_timestamp_slug(timestamp)}.yaml"
        )
        write_yaml_atomic(artifact_path, artifact)
        parent_step_id = f"ingress:system-projection:{timestamp}"
        details = (
            f"actor={actor} source_ref={source_ref or '-'} "
            f"fields={','.join(sorted(updates.keys()))} "
            f"artifact={artifact_path.relative_to(omo_dir.parent)}"
        )
        record_audit(
            action="ingress_write_system_projection_fields",
            debt_id="",
            actor=actor,
            details=details,
            audit_file=_audit_log_path(omo_dir),
        )
        _record_trail(
            omo_dir,
            actor=f"broker:{actor}",
            action="write_system_projection_fields",
            target=".omo/state/system.yaml",
            parent_step_id=parent_step_id,
        )
        _record_mutation(
            omo_dir,
            actor=actor,
            action="write_system_projection_fields",
            target=".omo/state/system.yaml",
            artifact_ref=f".omo/_delivery/ingress/state/{artifact_path.name}",
            source_ref=source_ref,
            created_at=timestamp,
            extra={"updated_fields": sorted(updates.keys())},
        )
        return deepcopy(payload)


def create_planned_task(
    omo_dir: Path,
    *,
    task_data: dict[str, Any],
    ingress_plane: str,
    source_ref: str = "",
    now: str | None = None,
) -> dict[str, Any]:
    errors = validate_task_data(task_data, group="planned")
    if errors:
        raise ValueError("invalid planned task: " + "; ".join(errors))

    task_id = str(task_data["id"])
    task_path = omo_dir / "tasks" / "planned" / f"{task_id}.yaml"
    timestamp = now or _utc_now()
    payload = _task_payload_with_metadata(
        task_data, ingress_plane=ingress_plane, source_ref=source_ref
    )
    artifact_ref = f".omo/_delivery/ingress/tasks/{task_id}.yaml"

    with fcntl_lock(_lock_path(omo_dir)):
        registry = _load_registry(omo_dir)

        if source_ref:
            mapped_task_id = registry["tasks"]["by_source_ref"].get(source_ref)
            if mapped_task_id and mapped_task_id != task_id:
                raise ValueError(
                    f"source_ref already mapped to different task: {source_ref} -> {mapped_task_id}"
                )

        if task_path.exists():
            existing_payload = _load_yaml(task_path)
            if existing_payload == payload:
                _register_ingress(
                    registry,
                    kind="tasks",
                    item_id=task_id,
                    source_ref=source_ref,
                    artifact_ref=artifact_ref,
                    fingerprint=payload,
                    created_at=str(
                        existing_payload.get("metadata", {}).get(
                            "created_at", timestamp
                        )
                    ),
                )
                _write_registry(omo_dir, registry)
                return existing_payload
            raise ValueError(
                f"planned task already exists with different payload: {task_id}"
            )

        write_yaml_atomic(task_path, payload)

        artifact = {
            "kind": "planned_task_created",
            "task_id": task_id,
            "title": payload.get("title", ""),
            "ingress_plane": ingress_plane,
            "source_ref": source_ref,
            "created_at": timestamp,
            "task_ref": f".omo/tasks/planned/{task_id}.yaml",
            "evidence_required": payload.get("evidence_required", []),
            "source_docs": payload.get("source_docs", []),
            **_artifact_lifecycle_fields(artifact_ref=artifact_ref),
        }
        artifact_path = _delivery_root(omo_dir) / "tasks" / f"{task_id}.yaml"
        write_yaml_atomic(artifact_path, artifact)
        _register_ingress(
            registry,
            kind="tasks",
            item_id=task_id,
            source_ref=source_ref,
            artifact_ref=artifact_ref,
            fingerprint=payload,
            created_at=timestamp,
        )
        _write_registry(omo_dir, registry)

        parent_step_id = f"ingress:task:{task_id}:{timestamp}"
        details = (
            f"task_id={task_id} ingress_plane={ingress_plane} "
            f"source_ref={source_ref or '-'} artifact={artifact_path.relative_to(omo_dir.parent)}"
        )
        record_audit(
            action="ingress_create_planned_task",
            debt_id="",
            actor=ingress_plane,
            details=details,
            audit_file=_audit_log_path(omo_dir),
        )
        _record_trail(
            omo_dir,
            actor=f"broker:{ingress_plane}",
            action="create_planned_task",
            target=f".omo/tasks/planned/{task_id}.yaml",
            parent_step_id=parent_step_id,
        )
        _record_mutation(
            omo_dir,
            actor=ingress_plane,
            action="create_planned_task",
            target=f".omo/tasks/planned/{task_id}.yaml",
            artifact_ref=artifact["artifact_ref"],
            source_ref=source_ref,
            created_at=timestamp,
            extra={"task_id": task_id, "ingress_plane": ingress_plane},
        )
        return payload


def create_blocked_task(
    omo_dir: Path,
    *,
    task_data: dict[str, Any],
    actor: str,
    source_ref: str = "",
    now: str | None = None,
) -> dict[str, Any]:
    errors = validate_task_data(task_data, group="blocked")
    if errors:
        raise ValueError("invalid blocked task: " + "; ".join(errors))

    task_id = str(task_data["id"])
    task_filename = f"{task_id.lower()}.yaml"
    task_path = omo_dir / "tasks" / "blocked" / task_filename
    timestamp = now or _utc_now()

    with fcntl_lock(_lock_path(omo_dir)):
        if task_path.exists():
            existing_payload = _load_yaml(task_path)
            if existing_payload == task_data:
                return existing_payload
            raise ValueError(
                f"blocked task already exists with different payload: {task_id}"
            )

        write_yaml_atomic(task_path, task_data)

        artifact = {
            "kind": "blocked_task_created",
            "task_id": task_id,
            "task_ref": f".omo/tasks/blocked/{task_filename}",
            "actor": actor,
            "source_ref": source_ref,
            "created_at": timestamp,
        }
        artifact_path = (
            _delivery_root(omo_dir)
            / "tasks"
            / f"{task_id}-blocked-{_timestamp_slug(timestamp)}.yaml"
        )
        write_yaml_atomic(artifact_path, artifact)

        parent_step_id = f"ingress:task-blocked:{task_id}:{timestamp}"
        details = (
            f"task_id={task_id} actor={actor} source_ref={source_ref or '-'} "
            f"artifact={artifact_path.relative_to(omo_dir.parent)}"
        )
        record_audit(
            action="ingress_create_blocked_task",
            debt_id="",
            actor=actor,
            details=details,
            audit_file=_audit_log_path(omo_dir),
        )
        _record_trail(
            omo_dir,
            actor=f"broker:{actor}",
            action="create_blocked_task",
            target=f".omo/tasks/blocked/{task_filename}",
            parent_step_id=parent_step_id,
        )
        _record_mutation(
            omo_dir,
            actor=actor,
            action="create_blocked_task",
            target=f".omo/tasks/blocked/{task_filename}",
            artifact_ref=f".omo/_delivery/ingress/tasks/{artifact_path.name}",
            source_ref=source_ref,
            created_at=timestamp,
            extra={"task_id": task_id},
        )
        return deepcopy(task_data)


def record_task_consensus(
    omo_dir: Path,
    *,
    task_id: str,
    actor: str,
    message: str,
    task_status: str | None = None,
    source_ref: str = "",
    now: str | None = None,
) -> dict[str, Any]:
    timestamp = now or _utc_now()
    resolved = _find_task_path(omo_dir, task_id, groups=("active", "blocked", "done"))
    if resolved is None:
        raise ValueError(f"task not found in active/blocked/done: {task_id}")
    group, task_path = resolved
    evidence_filename = f"{task_id.lower()}-{_timestamp_slug(timestamp)}.yaml"
    evidence_path = (
        omo_dir / "_delivery" / "task-center" / "consensus" / evidence_filename
    )

    with fcntl_lock(_lock_path(omo_dir)):
        payload = _load_yaml(task_path)
        evidence = {
            "task_id": task_id,
            "classification": "positive_confirmation",
            "message": message,
            "confirmed_at": timestamp,
            "task_status": task_status or payload.get("status"),
        }
        evidence_ref = f".omo/_delivery/task-center/consensus/{evidence_filename}"
        handoff_refs = payload.setdefault("handoff_refs", [])
        if isinstance(handoff_refs, list) and evidence_ref not in handoff_refs:
            handoff_refs.append(evidence_ref)

        errors = validate_task_data(payload, group=group)
        if errors:
            raise ValueError(
                "invalid task after consensus update: " + "; ".join(errors)
            )

        write_yaml_atomic(evidence_path, evidence)
        write_yaml_atomic(task_path, payload)

        artifact = {
            "kind": "task_consensus_recorded",
            "task_id": task_id,
            "task_ref": f".omo/tasks/{group}/{task_path.name}",
            "evidence_ref": evidence_ref,
            "actor": actor,
            "source_ref": source_ref,
            "recorded_at": timestamp,
        }
        artifact_path = (
            _delivery_root(omo_dir)
            / "tasks"
            / f"{task_id}-consensus-{_timestamp_slug(timestamp)}.yaml"
        )
        write_yaml_atomic(artifact_path, artifact)

        parent_step_id = f"ingress:task-consensus:{task_id}:{timestamp}"
        details = (
            f"task_id={task_id} actor={actor} evidence_ref={evidence_ref} "
            f"source_ref={source_ref or '-'} artifact={artifact_path.relative_to(omo_dir.parent)}"
        )
        record_audit(
            action="ingress_record_task_consensus",
            debt_id="",
            actor=actor,
            details=details,
            audit_file=_audit_log_path(omo_dir),
        )
        _record_trail(
            omo_dir,
            actor=f"broker:{actor}",
            action="record_task_consensus",
            target=evidence_ref,
            parent_step_id=parent_step_id,
        )
        _record_mutation(
            omo_dir,
            actor=actor,
            action="record_task_consensus",
            target=evidence_ref,
            artifact_ref=f".omo/_delivery/ingress/tasks/{artifact_path.name}",
            source_ref=source_ref,
            created_at=timestamp,
            extra={"task_id": task_id, "task_group": group},
        )
        return artifact


def write_usage_accounting(
    omo_dir: Path,
    *,
    registry: dict[str, Any],
    actor: str,
    source_ref: str = "",
    now: str | None = None,
) -> dict[str, Any]:
    timestamp = now or _utc_now()
    registry_path = omo_dir / "_truth" / "task-center" / "usage-accounting.yaml"

    with fcntl_lock(_lock_path(omo_dir)):
        write_yaml_atomic(registry_path, registry)

        artifact = {
            "kind": "task_center_usage_accounting_written",
            "registry_ref": ".omo/_truth/task-center/usage-accounting.yaml",
            "actor": actor,
            "source_ref": source_ref,
            "written_at": timestamp,
        }
        artifact_path = (
            _delivery_root(omo_dir)
            / "task-center"
            / f"usage-accounting-{_timestamp_slug(timestamp)}.yaml"
        )
        write_yaml_atomic(artifact_path, artifact)

        parent_step_id = f"ingress:usage-accounting:{timestamp}"
        details = (
            f"actor={actor} registry_ref=.omo/_truth/task-center/usage-accounting.yaml "
            f"source_ref={source_ref or '-'} artifact={artifact_path.relative_to(omo_dir.parent)}"
        )
        record_audit(
            action="ingress_write_usage_accounting",
            debt_id="",
            actor=actor,
            details=details,
            audit_file=_audit_log_path(omo_dir),
        )
        _record_trail(
            omo_dir,
            actor=f"broker:{actor}",
            action="write_usage_accounting",
            target=".omo/_truth/task-center/usage-accounting.yaml",
            parent_step_id=parent_step_id,
        )
        _record_mutation(
            omo_dir,
            actor=actor,
            action="write_usage_accounting",
            target=".omo/_truth/task-center/usage-accounting.yaml",
            artifact_ref=f".omo/_delivery/ingress/task-center/{artifact_path.name}",
            source_ref=source_ref,
            created_at=timestamp,
        )
        return artifact


def write_task_center_freshness(
    omo_dir: Path,
    *,
    report: dict[str, Any],
    actor: str,
    source_ref: str = "",
    now: str | None = None,
) -> dict[str, Any]:
    timestamp = now or _utc_now()
    report_path = omo_dir / "_delivery" / "task-center" / "freshness" / "current.yaml"

    with fcntl_lock(_lock_path(omo_dir)):
        write_yaml_atomic(report_path, report)

        artifact = {
            "kind": "task_center_freshness_written",
            "report_ref": ".omo/_delivery/task-center/freshness/current.yaml",
            "actor": actor,
            "source_ref": source_ref,
            "written_at": timestamp,
        }
        artifact_path = (
            _delivery_root(omo_dir)
            / "task-center"
            / f"freshness-{_timestamp_slug(timestamp)}.yaml"
        )
        write_yaml_atomic(artifact_path, artifact)

        parent_step_id = f"ingress:freshness:{timestamp}"
        details = (
            f"actor={actor} report_ref=.omo/_delivery/task-center/freshness/current.yaml "
            f"source_ref={source_ref or '-'} artifact={artifact_path.relative_to(omo_dir.parent)}"
        )
        record_audit(
            action="ingress_write_task_center_freshness",
            debt_id="",
            actor=actor,
            details=details,
            audit_file=_audit_log_path(omo_dir),
        )
        _record_trail(
            omo_dir,
            actor=f"broker:{actor}",
            action="write_task_center_freshness",
            target=".omo/_delivery/task-center/freshness/current.yaml",
            parent_step_id=parent_step_id,
        )
        _record_mutation(
            omo_dir,
            actor=actor,
            action="write_task_center_freshness",
            target=".omo/_delivery/task-center/freshness/current.yaml",
            artifact_ref=f".omo/_delivery/ingress/task-center/{artifact_path.name}",
            source_ref=source_ref,
            created_at=timestamp,
        )
        return artifact


def write_task_center_control_decision(
    omo_dir: Path,
    *,
    artifact: dict[str, Any],
    actor: str,
    source_ref: str = "",
    now: str | None = None,
) -> dict[str, Any]:
    timestamp = now or _utc_now()
    artifact_path = omo_dir / "_delivery" / "task-center" / "control" / "current.yaml"

    with fcntl_lock(_lock_path(omo_dir)):
        write_yaml_atomic(artifact_path, artifact)

        delivery_artifact = {
            "kind": "task_center_control_decision_written",
            "decision_ref": ".omo/_delivery/task-center/control/current.yaml",
            "decision": artifact.get("decision"),
            "actor": actor,
            "source_ref": source_ref,
            "written_at": timestamp,
        }
        ingress_artifact_path = (
            _delivery_root(omo_dir)
            / "task-center"
            / f"control-{_timestamp_slug(timestamp)}.yaml"
        )
        write_yaml_atomic(ingress_artifact_path, delivery_artifact)

        parent_step_id = f"ingress:control:{timestamp}"
        details = (
            f"actor={actor} decision={artifact.get('decision')} "
            f"source_ref={source_ref or '-'} artifact={ingress_artifact_path.relative_to(omo_dir.parent)}"
        )
        record_audit(
            action="ingress_write_task_center_control_decision",
            debt_id="",
            actor=actor,
            details=details,
            audit_file=_audit_log_path(omo_dir),
        )
        _record_trail(
            omo_dir,
            actor=f"broker:{actor}",
            action="write_task_center_control_decision",
            target=".omo/_delivery/task-center/control/current.yaml",
            parent_step_id=parent_step_id,
        )
        _record_mutation(
            omo_dir,
            actor=actor,
            action="write_task_center_control_decision",
            target=".omo/_delivery/task-center/control/current.yaml",
            artifact_ref=f".omo/_delivery/ingress/task-center/{ingress_artifact_path.name}",
            source_ref=source_ref,
            created_at=timestamp,
            extra={"decision": artifact.get("decision")},
        )
        return delivery_artifact


def update_governance_overlay_state(
    omo_dir: Path,
    *,
    roadmap: dict[str, Any],
    actor: str,
    control: dict[str, Any] | None = None,
    source_ref: str = "",
    now: str | None = None,
) -> dict[str, Any]:
    timestamp = now or _utc_now()
    roadmap_path = omo_dir / "_truth" / "governance-overlay" / "roadmap.yaml"
    control_path = omo_dir / "_control" / "governance-overlay" / "current.yaml"

    with fcntl_lock(_lock_path(omo_dir)):
        write_yaml_atomic(roadmap_path, roadmap)
        if control is not None:
            write_yaml_atomic(control_path, control)

        artifact = {
            "kind": "governance_overlay_state_updated",
            "roadmap_ref": ".omo/_truth/governance-overlay/roadmap.yaml",
            "control_ref": ".omo/_control/governance-overlay/current.yaml"
            if control is not None
            else None,
            "actor": actor,
            "source_ref": source_ref,
            "updated_at": timestamp,
        }
        artifact_path = (
            _delivery_root(omo_dir)
            / "governance-overlay"
            / f"state-{_timestamp_slug(timestamp)}.yaml"
        )
        write_yaml_atomic(artifact_path, artifact)

        parent_step_id = f"ingress:governance-overlay:{timestamp}"
        details = (
            f"actor={actor} source_ref={source_ref or '-'} "
            f"artifact={artifact_path.relative_to(omo_dir.parent)}"
        )
        record_audit(
            action="ingress_update_governance_overlay_state",
            debt_id="",
            actor=actor,
            details=details,
            audit_file=_audit_log_path(omo_dir),
        )
        _record_trail(
            omo_dir,
            actor=f"broker:{actor}",
            action="update_governance_overlay_state",
            target=".omo/_truth/governance-overlay/roadmap.yaml",
            parent_step_id=parent_step_id,
        )
        _record_mutation(
            omo_dir,
            actor=actor,
            action="update_governance_overlay_state",
            target=".omo/_truth/governance-overlay/roadmap.yaml",
            artifact_ref=f".omo/_delivery/ingress/governance-overlay/{artifact_path.name}",
            source_ref=source_ref,
            created_at=timestamp,
            extra={"control_written": control is not None},
        )
        return artifact


def complete_task(
    omo_dir: Path,
    *,
    task_id: str,
    actor: str,
    source_ref: str = "",
    now: str | None = None,
) -> dict[str, Any]:
    timestamp = now or _utc_now()
    task_roots = {
        "active": omo_dir / "tasks" / "active" / f"{task_id}.yaml",
        "planned": omo_dir / "tasks" / "planned" / f"{task_id}.yaml",
    }
    done_path = omo_dir / "tasks" / "done" / f"{task_id}.yaml"

    with fcntl_lock(_lock_path(omo_dir)):
        src_group: str | None = None
        src_path: Path | None = None
        for group, candidate in task_roots.items():
            if candidate.exists():
                src_group = group
                src_path = candidate
                break

        if src_path is None:
            if done_path.exists():
                existing_payload = _load_yaml(done_path)
                metadata = existing_payload.get("metadata", {})
                metadata_completed_at = (
                    metadata.get("completed_at") if isinstance(metadata, dict) else None
                )
                if not existing_payload.get("completed_at") and metadata_completed_at:
                    existing_payload["completed_at"] = metadata_completed_at
                    write_yaml_atomic(done_path, existing_payload)
                return existing_payload
            raise ValueError(f"task not found in active/planned/done: {task_id}")

        payload = _load_yaml(src_path)
        payload["status"] = "done"
        payload["completed_at"] = timestamp
        metadata = payload.setdefault("metadata", {})
        if isinstance(metadata, dict):
            metadata["completed_at"] = timestamp
            metadata["completed_via"] = "omo task done"
            metadata["completion_actor"] = actor
            if source_ref:
                metadata["completion_source_ref"] = source_ref

        errors = validate_task_data(payload, group="done")
        if errors:
            raise ValueError("invalid completed task: " + "; ".join(errors))

        write_yaml_atomic(done_path, payload)
        src_path.unlink()

        artifact = {
            "kind": "task_completed",
            "task_id": task_id,
            "source_group": src_group,
            "task_ref_before": f".omo/tasks/{src_group}/{task_id}.yaml",
            "task_ref_after": f".omo/tasks/done/{task_id}.yaml",
            "actor": actor,
            "source_ref": source_ref,
            "completed_at": timestamp,
        }
        artifact_path = (
            _delivery_root(omo_dir)
            / "tasks"
            / f"{task_id}-done-{_timestamp_slug(timestamp)}.yaml"
        )
        write_yaml_atomic(artifact_path, artifact)

        parent_step_id = f"ingress:task-done:{task_id}:{timestamp}"
        details = (
            f"task_id={task_id} actor={actor} from={src_group} "
            f"source_ref={source_ref or '-'} artifact={artifact_path.relative_to(omo_dir.parent)}"
        )
        record_audit(
            action="ingress_complete_task",
            debt_id="",
            actor=actor,
            details=details,
            audit_file=_audit_log_path(omo_dir),
        )
        _record_trail(
            omo_dir,
            actor=f"broker:{actor}",
            action="complete_task",
            target=f".omo/tasks/done/{task_id}.yaml",
            parent_step_id=parent_step_id,
        )
        _record_mutation(
            omo_dir,
            actor=actor,
            action="complete_task",
            target=f".omo/tasks/done/{task_id}.yaml",
            artifact_ref=f".omo/_delivery/ingress/tasks/{artifact_path.name}",
            source_ref=source_ref,
            created_at=timestamp,
            extra={"task_id": task_id, "source_group": src_group},
        )
        return payload


def update_done_task_evidence_paths(
    omo_dir: Path,
    *,
    task_id: str,
    evidence_paths: list[str],
    actor: str,
    source_ref: str = "",
    now: str | None = None,
) -> dict[str, Any]:
    timestamp = now or _utc_now()
    task_path = omo_dir / "tasks" / "done" / f"{task_id}.yaml"
    if not task_path.exists():
        raise ValueError(f"done task not found: {task_id}")
    if not isinstance(evidence_paths, list) or not all(
        isinstance(item, str) and item for item in evidence_paths
    ):
        raise ValueError("evidence_paths must be a non-empty list[str]")

    with fcntl_lock(_lock_path(omo_dir)):
        payload = _load_yaml(task_path)
        payload["evidence_paths"] = evidence_paths
        metadata = payload.setdefault("metadata", {})
        metadata["evidence_paths_refreshed_at"] = timestamp
        metadata["evidence_paths_refreshed_by"] = actor
        metadata["evidence_paths_refresh_source_ref"] = source_ref
        write_yaml_atomic(task_path, payload)

        artifact = {
            "kind": "done_task_evidence_paths_updated",
            "task_ref": f".omo/tasks/done/{task_id}.yaml",
            "evidence_paths": evidence_paths,
            "actor": actor,
            "source_ref": source_ref,
            "updated_at": timestamp,
        }
        artifact_path = (
            _delivery_root(omo_dir)
            / "tasks"
            / f"{task_id}-evidence-refresh-{_timestamp_slug(timestamp)}.yaml"
        )
        write_yaml_atomic(artifact_path, artifact)
        parent_step_id = f"ingress:task-evidence-refresh:{task_id}:{timestamp}"
        details = (
            f"task_id={task_id} actor={actor} source_ref={source_ref or '-'} "
            f"artifact={artifact_path.relative_to(omo_dir.parent)}"
        )
        record_audit(
            action="ingress_update_done_task_evidence_paths",
            debt_id="",
            actor=actor,
            details=details,
            audit_file=_audit_log_path(omo_dir),
        )
        _record_trail(
            omo_dir,
            actor=f"broker:{actor}",
            action="update_done_task_evidence_paths",
            target=f".omo/tasks/done/{task_id}.yaml",
            parent_step_id=parent_step_id,
        )
        _record_mutation(
            omo_dir,
            actor=actor,
            action="update_done_task_evidence_paths",
            target=f".omo/tasks/done/{task_id}.yaml",
            artifact_ref=f".omo/_delivery/ingress/tasks/{artifact_path.name}",
            source_ref=source_ref,
            created_at=timestamp,
            extra={"task_id": task_id},
        )
        return deepcopy(payload)


def update_planned_task_evidence_paths(
    omo_dir: Path,
    *,
    task_id: str,
    evidence_paths: list[str],
    actor: str,
    source_ref: str = "",
    now: str | None = None,
) -> dict[str, Any]:
    """Add evidence_paths to a planned/active task (未归档, done 前补 evidence).

    解决归档 gap: done 需 evidence, refresh-evidence 只查 done/, planned 无加 evidence 命令.
    """
    timestamp = now or _utc_now()
    task_path: Path | None = None
    for sub in ("planned", "active"):
        candidate = omo_dir / "tasks" / sub / f"{task_id}.yaml"
        if candidate.exists():
            task_path = candidate
            break
    if task_path is None:
        raise ValueError(f"planned/active task not found: {task_id}")
    if not isinstance(evidence_paths, list) or not all(
        isinstance(item, str) and item for item in evidence_paths
    ):
        raise ValueError("evidence_paths must be a non-empty list[str]")

    with fcntl_lock(_lock_path(omo_dir)):
        payload = _load_yaml(task_path)
        payload["evidence_paths"] = evidence_paths
        metadata = payload.setdefault("metadata", {})
        metadata["evidence_paths_refreshed_at"] = timestamp
        metadata["evidence_paths_refreshed_by"] = actor
        metadata["evidence_paths_refresh_source_ref"] = source_ref
        write_yaml_atomic(task_path, payload)

        artifact = {
            "kind": "planned_task_evidence_paths_added",
            "task_ref": str(task_path.relative_to(omo_dir)),
            "evidence_paths": evidence_paths,
            "actor": actor,
            "source_ref": source_ref,
            "updated_at": timestamp,
        }
        artifact_path = (
            _delivery_root(omo_dir)
            / "tasks"
            / f"{task_id}-evidence-add-{_timestamp_slug(timestamp)}.yaml"
        )
        write_yaml_atomic(artifact_path, artifact)
        parent_step_id = f"ingress:task-evidence-add:{task_id}:{timestamp}"
        details = (
            f"task_id={task_id} actor={actor} source_ref={source_ref or '-'} "
            f"artifact={artifact_path.relative_to(omo_dir.parent)}"
        )
        record_audit(
            action="ingress_update_planned_task_evidence_paths",
            debt_id="",
            actor=actor,
            details=details,
            audit_file=_audit_log_path(omo_dir),
        )
        _record_trail(
            omo_dir,
            actor=f"broker:{actor}",
            action="update_planned_task_evidence_paths",
            target=str(task_path.relative_to(omo_dir)),
            parent_step_id=parent_step_id,
        )
        _record_mutation(
            omo_dir,
            actor=actor,
            action="update_planned_task_evidence_paths",
            target=str(task_path.relative_to(omo_dir.parent)),
            artifact_ref=f".omo/_delivery/ingress/tasks/{artifact_path.name}",
            source_ref=source_ref,
            created_at=timestamp,
            extra={"task_id": task_id},
        )
        return deepcopy(payload)


def promote_task_to_active(
    omo_dir: Path,
    *,
    task_id: str,
    actor: str,
    handoff_ref: str | None = None,
    source_ref: str = "",
    now: str | None = None,
) -> dict[str, Any]:
    timestamp = now or _utc_now()
    planned_path = omo_dir / "tasks" / "planned" / f"{task_id}.yaml"
    active_path = omo_dir / "tasks" / "active" / f"{task_id}.yaml"

    with fcntl_lock(_lock_path(omo_dir)):
        if active_path.exists():
            return _load_yaml(active_path)
        if not planned_path.exists():
            raise ValueError(f"planned task not found: {task_id}")

        payload = _load_yaml(planned_path)
        if handoff_ref:
            handoffs = payload.setdefault("handoff_refs", [])
            if isinstance(handoffs, list) and handoff_ref not in handoffs:
                handoffs.append(handoff_ref)

        errors = validate_task_data(payload, group="active")
        if errors:
            raise ValueError("invalid promoted task: " + "; ".join(errors))

        write_yaml_atomic(active_path, payload)
        planned_path.unlink()

        artifact = {
            "kind": "task_promoted_to_active",
            "task_id": task_id,
            "task_ref_before": f".omo/tasks/planned/{task_id}.yaml",
            "task_ref_after": f".omo/tasks/active/{task_id}.yaml",
            "handoff_ref": handoff_ref,
            "actor": actor,
            "source_ref": source_ref,
            "promoted_at": timestamp,
        }
        artifact_path = (
            _delivery_root(omo_dir)
            / "tasks"
            / f"{task_id}-promote-{_timestamp_slug(timestamp)}.yaml"
        )
        write_yaml_atomic(artifact_path, artifact)

        parent_step_id = f"ingress:task-promote:{task_id}:{timestamp}"
        details = (
            f"task_id={task_id} actor={actor} handoff_ref={handoff_ref or '-'} "
            f"source_ref={source_ref or '-'} artifact={artifact_path.relative_to(omo_dir.parent)}"
        )
        record_audit(
            action="ingress_promote_task",
            debt_id="",
            actor=actor,
            details=details,
            audit_file=_audit_log_path(omo_dir),
        )
        _record_trail(
            omo_dir,
            actor=f"broker:{actor}",
            action="promote_task_to_active",
            target=f".omo/tasks/active/{task_id}.yaml",
            parent_step_id=parent_step_id,
        )
        _record_mutation(
            omo_dir,
            actor=actor,
            action="promote_task_to_active",
            target=f".omo/tasks/active/{task_id}.yaml",
            artifact_ref=f".omo/_delivery/ingress/tasks/{artifact_path.name}",
            source_ref=source_ref,
            created_at=timestamp,
            extra={"task_id": task_id, "handoff_ref": handoff_ref},
        )
        return payload


def repair_task_promotion_approval(
    omo_dir: Path,
    *,
    task_id: str,
    actor: str,
    source_ref: str = "",
    now: str | None = None,
) -> dict[str, Any]:
    timestamp = now or _utc_now()
    located = _find_task_path(
        omo_dir, task_id, groups=("planned", "active", "done", "remediation")
    )
    if located is None:
        raise ValueError(f"task not found: {task_id}")

    group, task_path = located
    approval_path: Path
    with fcntl_lock(_lock_path(omo_dir)):
        payload = _load_yaml(task_path)
        if not payload.get("human_approval_required"):
            raise ValueError("task does not require human approval")

        approval_ref = payload.get("approval_ref")
        if (
            not isinstance(approval_ref, str)
            or not approval_ref.endswith(".yaml")
            or not approval_ref.startswith(".omo/workers/runs/")
        ):
            approval_ref = promotion_approval_ref(task_id, timestamp)
            payload["approval_ref"] = approval_ref

        approval_path = omo_dir.parent / approval_ref
        task_ref = str(task_path.relative_to(omo_dir.parent))
        approval_record = build_promotion_approval_request(
            task_id=task_id,
            task_ref=task_ref,
            requested_operation_level=str(
                payload.get("allowed_operation_level")
                or payload.get("risk_level")
                or "L0"
            ),
            requested_at=str(payload.get("created_at") or timestamp),
            approval_ref=approval_ref,
        )
        if payload.get("approval_state") == "granted" or payload.get("status") in {
            "review",
            "done",
        }:
            approved_at = str(
                payload.get("updated_at") or payload.get("started_at") or timestamp
            )
            approval_record["approval_status"] = "granted"
            approval_record["approved_at"] = approved_at
            approval_record["approver"] = "omo-repair"

        write_yaml_atomic(approval_path, approval_record)
        write_yaml_atomic(task_path, payload)

        artifact = {
            "kind": "task_promotion_approval_repaired",
            "task_id": task_id,
            "task_group": group,
            "task_ref": task_ref,
            "approval_ref": approval_ref,
            "actor": actor,
            "source_ref": source_ref,
            "repaired_at": timestamp,
            **_artifact_lifecycle_fields(
                artifact_ref=f".omo/_delivery/ingress/tasks/{task_id}-approval-repair-{_timestamp_slug(timestamp)}.yaml"
            ),
        }
        artifact_path = (
            _delivery_root(omo_dir)
            / "tasks"
            / f"{task_id}-approval-repair-{_timestamp_slug(timestamp)}.yaml"
        )
        write_yaml_atomic(artifact_path, artifact)

        parent_step_id = f"ingress:task-approval-repair:{task_id}:{timestamp}"
        details = (
            f"task_id={task_id} group={group} actor={actor} approval_ref={approval_ref} "
            f"source_ref={source_ref or '-'} artifact={artifact_path.relative_to(omo_dir.parent)}"
        )
        record_audit(
            action="ingress_repair_task_promotion_approval",
            debt_id="",
            actor=actor,
            details=details,
            audit_file=_audit_log_path(omo_dir),
        )
        _record_trail(
            omo_dir,
            actor=f"broker:{actor}",
            action="repair_task_promotion_approval",
            target=task_ref,
            parent_step_id=parent_step_id,
        )
        _record_mutation(
            omo_dir,
            actor=actor,
            action="repair_task_promotion_approval",
            target=task_ref,
            artifact_ref=artifact["artifact_ref"],
            source_ref=source_ref,
            created_at=timestamp,
            extra={"task_id": task_id, "task_group": group, "approval_ref": approval_ref},
        )
        return payload


def request_task_promotion_approval(
    omo_dir: Path,
    *,
    task_id: str,
    actor: str,
    approval_ref: str,
    approval_record: dict[str, Any],
    proposal_ref: str = "",
    source_ref: str = "",
    now: str | None = None,
) -> dict[str, Any]:
    timestamp = now or _utc_now()
    task_path = omo_dir / "tasks" / "planned" / f"{task_id}.yaml"
    approval_path = omo_dir.parent / approval_ref

    with fcntl_lock(_lock_path(omo_dir)):
        if not task_path.exists():
            raise ValueError(f"planned task not found: {task_id}")

        payload = _load_yaml(task_path)
        existing_ref = payload.get("approval_ref")
        if (
            existing_ref
            and isinstance(existing_ref, str)
            and existing_ref.endswith(".yaml")
            and "-promotion-approval-" in existing_ref
        ):
            raise ValueError(
                "task already points to a task-specific promotion approval"
            )

        payload["approval_ref"] = approval_ref
        errors = validate_task_data(payload, group="planned")
        if errors:
            raise ValueError(
                "invalid planned task after approval request: " + "; ".join(errors)
            )

        write_yaml_atomic(approval_path, approval_record)
        write_yaml_atomic(task_path, payload)

        artifact = {
            "kind": "task_promotion_approval_requested",
            "task_id": task_id,
            "task_ref": f".omo/tasks/planned/{task_id}.yaml",
            "approval_ref": approval_ref,
            "proposal_ref": proposal_ref,
            "actor": actor,
            "source_ref": source_ref,
            "requested_at": timestamp,
        }
        artifact_path = (
            _delivery_root(omo_dir)
            / "tasks"
            / f"{task_id}-promotion-approval-{_timestamp_slug(timestamp)}.yaml"
        )
        write_yaml_atomic(artifact_path, artifact)

        parent_step_id = f"ingress:task-promotion-approval:{task_id}:{timestamp}"
        details = (
            f"task_id={task_id} actor={actor} approval_ref={approval_ref} "
            f"proposal_ref={proposal_ref or '-'} source_ref={source_ref or '-'} "
            f"artifact={artifact_path.relative_to(omo_dir.parent)}"
        )
        record_audit(
            action="ingress_request_task_promotion_approval",
            debt_id="",
            actor=actor,
            details=details,
            audit_file=_audit_log_path(omo_dir),
        )
        _record_trail(
            omo_dir,
            actor=f"broker:{actor}",
            action="request_task_promotion_approval",
            target=f".omo/tasks/planned/{task_id}.yaml",
            parent_step_id=parent_step_id,
        )
        _record_mutation(
            omo_dir,
            actor=actor,
            action="request_task_promotion_approval",
            target=f".omo/tasks/planned/{task_id}.yaml",
            artifact_ref=f".omo/_delivery/ingress/tasks/{artifact_path.name}",
            source_ref=source_ref,
            created_at=timestamp,
            extra={"task_id": task_id, "approval_ref": approval_ref, "proposal_ref": proposal_ref},
        )
        return payload


def revert_task_to_planned(
    omo_dir: Path,
    *,
    task_id: str,
    actor: str,
    source_ref: str = "",
    handoff_refs_override: list[str] | None = None,
    now: str | None = None,
) -> dict[str, Any]:
    timestamp = now or _utc_now()
    active_path = omo_dir / "tasks" / "active" / f"{task_id}.yaml"
    planned_path = omo_dir / "tasks" / "planned" / f"{task_id}.yaml"

    with fcntl_lock(_lock_path(omo_dir)):
        if planned_path.exists():
            return _load_yaml(planned_path)
        if not active_path.exists():
            raise ValueError(f"active task not found: {task_id}")

        payload = _load_yaml(active_path)
        if handoff_refs_override is not None:
            payload["handoff_refs"] = list(handoff_refs_override)
        payload["assigned_to"] = None
        payload["dispatch_id"] = None
        payload["run_ref"] = None
        payload["review_ref"] = None
        payload.pop("started_at", None)
        errors = validate_task_data(payload, group="planned")
        if errors:
            raise ValueError("invalid reverted planned task: " + "; ".join(errors))

        write_yaml_atomic(planned_path, payload)
        active_path.unlink()

        artifact = {
            "kind": "task_reverted_to_planned",
            "task_id": task_id,
            "task_ref_before": f".omo/tasks/active/{task_id}.yaml",
            "task_ref_after": f".omo/tasks/planned/{task_id}.yaml",
            "actor": actor,
            "source_ref": source_ref,
            "reverted_at": timestamp,
        }
        artifact_path = (
            _delivery_root(omo_dir)
            / "tasks"
            / f"{task_id}-revert-{_timestamp_slug(timestamp)}.yaml"
        )
        write_yaml_atomic(artifact_path, artifact)

        parent_step_id = f"ingress:task-revert:{task_id}:{timestamp}"
        details = (
            f"task_id={task_id} actor={actor} source_ref={source_ref or '-'} "
            f"artifact={artifact_path.relative_to(omo_dir.parent)}"
        )
        record_audit(
            action="ingress_revert_task",
            debt_id="",
            actor=actor,
            details=details,
            audit_file=_audit_log_path(omo_dir),
        )
        _record_trail(
            omo_dir,
            actor=f"broker:{actor}",
            action="revert_task_to_planned",
            target=f".omo/tasks/planned/{task_id}.yaml",
            parent_step_id=parent_step_id,
        )
        _record_mutation(
            omo_dir,
            actor=actor,
            action="revert_task_to_planned",
            target=f".omo/tasks/planned/{task_id}.yaml",
            artifact_ref=f".omo/_delivery/ingress/tasks/{artifact_path.name}",
            source_ref=source_ref,
            created_at=timestamp,
            extra={"task_id": task_id},
        )
        return payload


def record_task_contract_request(
    omo_dir: Path,
    *,
    task_id: str,
    actor: str,
    request_ref: str,
    request_record: dict[str, Any],
    proposal_ref: str = "",
    source_ref: str = "",
    now: str | None = None,
) -> dict[str, Any]:
    timestamp = now or _utc_now()
    task_path = omo_dir / "tasks" / "active" / f"{task_id}.yaml"
    request_path = omo_dir.parent / request_ref

    with fcntl_lock(_lock_path(omo_dir)):
        if not task_path.exists():
            raise ValueError(f"active task not found: {task_id}")

        payload = _load_yaml(task_path)
        handoff_refs = payload.setdefault("handoff_refs", [])
        if isinstance(handoff_refs, list) and request_ref not in handoff_refs:
            handoff_refs.append(request_ref)
        request_deliverables = request_record.get("deliverables")
        if (
            isinstance(request_deliverables, list)
            and request_deliverables
            and not payload.get("deliverables")
        ):
            payload["deliverables"] = list(request_deliverables)

        errors = validate_task_data(payload, group="active")
        if errors:
            raise ValueError(
                "invalid active task after contract request: " + "; ".join(errors)
            )

        write_yaml_atomic(request_path, request_record)
        write_yaml_atomic(task_path, payload)

        artifact = {
            "kind": "task_contract_request_recorded",
            "task_id": task_id,
            "task_ref": f".omo/tasks/active/{task_id}.yaml",
            "request_ref": request_ref,
            "proposal_ref": proposal_ref,
            "actor": actor,
            "source_ref": source_ref,
            "recorded_at": timestamp,
        }
        artifact_path = (
            _delivery_root(omo_dir)
            / "tasks"
            / f"{task_id}-contract-request-{_timestamp_slug(timestamp)}.yaml"
        )
        write_yaml_atomic(artifact_path, artifact)

        parent_step_id = f"ingress:task-contract-request:{task_id}:{timestamp}"
        details = (
            f"task_id={task_id} actor={actor} request_ref={request_ref} "
            f"proposal_ref={proposal_ref or '-'} source_ref={source_ref or '-'} "
            f"artifact={artifact_path.relative_to(omo_dir.parent)}"
        )
        record_audit(
            action="ingress_record_task_contract_request",
            debt_id="",
            actor=actor,
            details=details,
            audit_file=_audit_log_path(omo_dir),
        )
        _record_trail(
            omo_dir,
            actor=f"broker:{actor}",
            action="record_task_contract_request",
            target=f".omo/tasks/active/{task_id}.yaml",
            parent_step_id=parent_step_id,
        )
        _record_mutation(
            omo_dir,
            actor=actor,
            action="record_task_contract_request",
            target=f".omo/tasks/active/{task_id}.yaml",
            artifact_ref=f".omo/_delivery/ingress/tasks/{artifact_path.name}",
            source_ref=source_ref,
            created_at=timestamp,
            extra={"task_id": task_id, "request_ref": request_ref, "proposal_ref": proposal_ref},
        )
        return payload


def route_self_evolution_to_remediation(
    omo_dir: Path,
    *,
    task_id: str,
    actor: str,
    review_note_body: str,
    source_ref: str = "",
    now: str | None = None,
) -> dict[str, Any]:
    timestamp = now or _utc_now()
    planned_path = omo_dir / "tasks" / "planned" / f"{task_id}.yaml"
    remediation_path = omo_dir / "tasks" / "remediation" / f"{task_id}.yaml"
    review_note_rel = (
        Path(".omo") / "tasks" / "remediation-notes" / f"{task_id}-review.md"
    )
    review_note_path = omo_dir.parent / review_note_rel
    artifact_rel = (
        Path(".omo")
        / "_delivery"
        / "ingress"
        / "tasks"
        / f"{task_id}-route-self-evolution-{_timestamp_slug(timestamp)}.yaml"
    )
    artifact_path = omo_dir.parent / artifact_rel

    with fcntl_lock(_lock_path(omo_dir)):
        if remediation_path.exists() and not planned_path.exists():
            return _load_yaml(remediation_path)
        if not planned_path.exists():
            raise ValueError(f"planned task not found: {task_id}")
        if not task_id.startswith("OPC-P6-SELF-EVOLUTION-"):
            raise ValueError(f"task is not a self-evolution packet: {task_id}")

        payload = _load_yaml(planned_path)
        payload["status"] = "review"
        payload["assigned_to"] = actor
        payload["dispatch_id"] = (
            f"self-evolution-remediation-{_timestamp_slug(timestamp)}"
        )
        payload["run_ref"] = str(artifact_rel)
        payload["review_ref"] = str(review_note_rel)
        payload["review_note"] = str(review_note_rel)
        payload["started_at"] = timestamp
        payload["approval_state"] = "granted"

        metadata = payload.setdefault("metadata", {})
        if isinstance(metadata, dict):
            metadata["routed_to_remediation_at"] = timestamp
            metadata["routed_to_remediation_by"] = actor
            metadata["routed_to_remediation_via"] = "self-evolution-review-lane"
            if source_ref:
                metadata["routed_to_remediation_source_ref"] = source_ref

        errors = validate_task_data(payload, group="remediation")
        if errors:
            raise ValueError("invalid remediation task: " + "; ".join(errors))

        remediation_path.parent.mkdir(parents=True, exist_ok=True)
        review_note_path.parent.mkdir(parents=True, exist_ok=True)
        write_text_atomic(review_note_path, review_note_body)
        write_yaml_atomic(remediation_path, payload)
        planned_path.unlink()

        artifact = {
            "kind": "self_evolution_routed_to_remediation",
            "task_id": task_id,
            "task_ref_before": f".omo/tasks/planned/{task_id}.yaml",
            "task_ref_after": f".omo/tasks/remediation/{task_id}.yaml",
            "review_note_ref": str(review_note_rel),
            "actor": actor,
            "source_ref": source_ref,
            "routed_at": timestamp,
        }
        write_yaml_atomic(artifact_path, artifact)

        parent_step_id = f"ingress:self-evolution-remediation:{task_id}:{timestamp}"
        details = (
            f"task_id={task_id} actor={actor} review_note={review_note_rel} "
            f"source_ref={source_ref or '-'} artifact={artifact_rel}"
        )
        record_audit(
            action="ingress_route_self_evolution_to_remediation",
            debt_id="",
            actor=actor,
            details=details,
            audit_file=_audit_log_path(omo_dir),
        )
        _record_trail(
            omo_dir,
            actor=f"broker:{actor}",
            action="route_self_evolution_to_remediation",
            target=f".omo/tasks/remediation/{task_id}.yaml",
            parent_step_id=parent_step_id,
        )
        _record_mutation(
            omo_dir,
            actor=actor,
            action="route_self_evolution_to_remediation",
            target=f".omo/tasks/remediation/{task_id}.yaml",
            artifact_ref=str(artifact_rel),
            source_ref=source_ref,
            created_at=timestamp,
            extra={"task_id": task_id, "review_note_ref": str(review_note_rel)},
        )
        return payload


def yield_task_to_planned(
    omo_dir: Path,
    *,
    task_id: str,
    actor: str,
    reason: str,
    source_ref: str = "",
    now: str | None = None,
) -> dict[str, Any]:
    timestamp = now or _utc_now()
    active_path = omo_dir / "tasks" / "active" / f"{task_id}.yaml"
    planned_path = omo_dir / "tasks" / "planned" / f"{task_id}.yaml"

    with fcntl_lock(_lock_path(omo_dir)):
        if planned_path.exists() and not active_path.exists():
            return _load_yaml(planned_path)
        if not active_path.exists():
            raise ValueError(f"active task not found: {task_id}")

        payload = _load_yaml(active_path)
        payload["status"] = "candidate"
        payload["assigned_to"] = None
        payload["dispatch_id"] = None
        payload["run_ref"] = None
        payload["review_ref"] = None
        payload.pop("started_at", None)

        metadata = payload.setdefault("metadata", {})
        if isinstance(metadata, dict):
            metadata["yielded_at"] = timestamp
            metadata["yielded_via"] = "omo worker yield"
            metadata["yield_reason"] = reason
            metadata["yield_actor"] = actor
            if source_ref:
                metadata["yield_source_ref"] = source_ref

        errors = validate_task_data(payload, group="planned")
        if errors:
            raise ValueError("invalid yielded planned task: " + "; ".join(errors))

        write_yaml_atomic(planned_path, payload)
        active_path.unlink()

        artifact = {
            "kind": "task_yielded_to_planned",
            "task_id": task_id,
            "task_ref_before": f".omo/tasks/active/{task_id}.yaml",
            "task_ref_after": f".omo/tasks/planned/{task_id}.yaml",
            "actor": actor,
            "reason": reason,
            "source_ref": source_ref,
            "yielded_at": timestamp,
        }
        artifact_path = (
            _delivery_root(omo_dir)
            / "tasks"
            / f"{task_id}-yield-{_timestamp_slug(timestamp)}.yaml"
        )
        write_yaml_atomic(artifact_path, artifact)

        parent_step_id = f"ingress:task-yield:{task_id}:{timestamp}"
        details = (
            f"task_id={task_id} actor={actor} reason={reason} "
            f"source_ref={source_ref or '-'} artifact={artifact_path.relative_to(omo_dir.parent)}"
        )
        record_audit(
            action="ingress_yield_task",
            debt_id="",
            actor=actor,
            details=details,
            audit_file=_audit_log_path(omo_dir),
        )
        _record_trail(
            omo_dir,
            actor=f"broker:{actor}",
            action="yield_task_to_planned",
            target=f".omo/tasks/planned/{task_id}.yaml",
            parent_step_id=parent_step_id,
        )
        _record_mutation(
            omo_dir,
            actor=actor,
            action="yield_task_to_planned",
            target=f".omo/tasks/planned/{task_id}.yaml",
            artifact_ref=f".omo/_delivery/ingress/tasks/{artifact_path.name}",
            source_ref=source_ref,
            created_at=timestamp,
            extra={"task_id": task_id, "reason": reason},
        )
        return payload


def archive_done_task(
    omo_dir: Path,
    *,
    task_id: str,
    actor: str,
    archive_subdir: str = "",
    source_ref: str = "",
    now: str | None = None,
) -> dict[str, Any]:
    timestamp = now or _utc_now()
    done_path = omo_dir / "tasks" / "done" / f"{task_id}.yaml"
    archive_root = omo_dir / "tasks" / "archived"
    archive_dir = archive_root / archive_subdir if archive_subdir else archive_root
    archive_path = archive_dir / f"{task_id}.yaml"

    with fcntl_lock(_lock_path(omo_dir)):
        if archive_path.exists() and not done_path.exists():
            return _load_yaml(archive_path)
        if not done_path.exists():
            raise ValueError(f"done task not found: {task_id}")

        payload = _load_yaml(done_path)
        payload["status"] = "archived"
        payload["archived_at"] = timestamp
        payload["archived_by"] = actor
        if source_ref:
            payload["archived_source_ref"] = source_ref

        archive_dir.mkdir(parents=True, exist_ok=True)
        write_yaml_atomic(archive_path, payload)
        done_path.unlink()

        archived_ref = f".omo/tasks/archived/{task_id}.yaml"
        if archive_subdir:
            archived_ref = f".omo/tasks/archived/{archive_subdir}/{task_id}.yaml"

        artifact = {
            "kind": "task_archived_from_done",
            "task_id": task_id,
            "task_ref_before": f".omo/tasks/done/{task_id}.yaml",
            "task_ref_after": archived_ref,
            "actor": actor,
            "source_ref": source_ref,
            "archived_at": timestamp,
        }
        artifact_path = (
            _delivery_root(omo_dir)
            / "tasks"
            / f"{task_id}-archive-{_timestamp_slug(timestamp)}.yaml"
        )
        write_yaml_atomic(artifact_path, artifact)

        parent_step_id = f"ingress:task-archive:{task_id}:{timestamp}"
        details = (
            f"task_id={task_id} actor={actor} archived_ref={archived_ref} "
            f"source_ref={source_ref or '-'} artifact={artifact_path.relative_to(omo_dir.parent)}"
        )
        record_audit(
            action="ingress_archive_done_task",
            debt_id="",
            actor=actor,
            details=details,
            audit_file=_audit_log_path(omo_dir),
        )
        _record_trail(
            omo_dir,
            actor=f"broker:{actor}",
            action="archive_done_task",
            target=archived_ref,
            parent_step_id=parent_step_id,
        )
        _record_mutation(
            omo_dir,
            actor=actor,
            action="archive_done_task",
            target=archived_ref,
            artifact_ref=f".omo/_delivery/ingress/tasks/{artifact_path.name}",
            source_ref=source_ref,
            created_at=timestamp,
            extra={"task_id": task_id},
        )
        return payload


def create_audit_report(
    omo_dir: Path,
    *,
    filename: str,
    title: str,
    content: str,
    actor: str,
    source_ref: str = "",
    now: str | None = None,
) -> dict[str, Any]:
    timestamp = now or _utc_now()
    report_path = omo_dir / "_knowledge" / "audits" / f"{filename}.md"

    with fcntl_lock(_lock_path(omo_dir)):
        if report_path.exists():
            raise ValueError(f"{report_path.name} already exists")
        write_text_atomic(report_path, f"# {title}\n\n{content}\n")
        artifact = {
            "kind": "audit_report_created",
            "title": title,
            "report_ref": f".omo/_knowledge/audits/{filename}.md",
            "actor": actor,
            "source_ref": source_ref,
            "created_at": timestamp,
        }
        artifact_path = (
            _delivery_root(omo_dir)
            / "audits"
            / f"{filename}-{_timestamp_slug(timestamp)}.yaml"
        )
        write_yaml_atomic(artifact_path, artifact)
        parent_step_id = f"ingress:audit:{filename}:{timestamp}"
        details = (
            f"filename={filename} actor={actor} source_ref={source_ref or '-'} "
            f"artifact={artifact_path.relative_to(omo_dir.parent)}"
        )
        record_audit(
            action="ingress_create_audit_report",
            debt_id="",
            actor=actor,
            details=details,
            audit_file=_audit_log_path(omo_dir),
        )
        _record_trail(
            omo_dir,
            actor=f"broker:{actor}",
            action="create_audit_report",
            target=f".omo/_knowledge/audits/{filename}.md",
            parent_step_id=parent_step_id,
        )
        _record_mutation(
            omo_dir,
            actor=actor,
            action="create_audit_report",
            target=f".omo/_knowledge/audits/{filename}.md",
            artifact_ref=f".omo/_delivery/ingress/audits/{artifact_path.name}",
            source_ref=source_ref,
            created_at=timestamp,
            extra={"title": title},
        )
        return artifact


def normalize_legacy_planned_task(
    omo_dir: Path,
    *,
    task_id: str,
    actor: str,
    source_ref: str = "",
    now: str | None = None,
) -> dict[str, Any]:
    timestamp = now or _utc_now()
    planned_path = omo_dir / "tasks" / "planned" / f"{task_id}.yaml"
    archived_dir = omo_dir / "tasks" / "archived" / "legacy-normalized"
    archived_path = archived_dir / f"{task_id}.yaml"

    with fcntl_lock(_lock_path(omo_dir)):
        if not planned_path.exists():
            raise ValueError(f"planned task not found: {task_id}")

        payload = _load_yaml(planned_path)
        original_status = str(payload.get("status") or "missing")
        metadata = payload.setdefault("metadata", {})
        if isinstance(metadata, dict):
            metadata.setdefault("legacy_normalized_from", "planned")
            metadata["legacy_status"] = original_status
            metadata["normalized_at"] = timestamp
            metadata["normalized_by"] = actor
            if source_ref:
                metadata["normalization_source_ref"] = source_ref
            if "owner" in payload and payload.get("owner"):
                metadata.setdefault("legacy_owner", payload.get("owner"))
            if "priority" in payload and payload.get("priority"):
                metadata.setdefault("priority", payload.get("priority"))

        if original_status in {"done", "archived", "failed", "blocked"} or payload.get(
            "completed_at"
        ):
            archived_payload = deepcopy(payload)
            archived_payload["status"] = "archived"
            archived_payload["archived_at"] = timestamp
            archived_payload["archived_by"] = actor
            archived_dir.mkdir(parents=True, exist_ok=True)
            write_yaml_atomic(archived_path, archived_payload)
            planned_path.unlink()

            artifact = {
                "kind": "planned_task_legacy_archived",
                "task_id": task_id,
                "legacy_status": original_status,
                "task_ref_before": f".omo/tasks/planned/{task_id}.yaml",
                "task_ref_after": f".omo/tasks/archived/legacy-normalized/{task_id}.yaml",
                "actor": actor,
                "source_ref": source_ref,
                "normalized_at": timestamp,
            }
            artifact_path = (
                _delivery_root(omo_dir)
                / "tasks"
                / f"{task_id}-legacy-archive-{_timestamp_slug(timestamp)}.yaml"
            )
            write_yaml_atomic(artifact_path, artifact)
            record_audit(
                action="ingress_archive_legacy_planned_task",
                debt_id="",
                actor=actor,
                details=(
                    f"task_id={task_id} legacy_status={original_status} source_ref={source_ref or '-'} "
                    f"artifact={artifact_path.relative_to(omo_dir.parent)}"
                ),
                audit_file=_audit_log_path(omo_dir),
            )
            _record_trail(
                omo_dir,
                actor=f"broker:{actor}",
                action="normalize_legacy_planned_task",
                target=f".omo/tasks/archived/legacy-normalized/{task_id}.yaml",
                parent_step_id=f"ingress:legacy-planned-archive:{task_id}:{timestamp}",
            )
            _record_mutation(
                omo_dir,
                actor=actor,
                action="normalize_legacy_planned_task",
                target=f".omo/tasks/archived/legacy-normalized/{task_id}.yaml",
                artifact_ref=f".omo/_delivery/ingress/tasks/{artifact_path.name}",
                source_ref=source_ref,
                created_at=timestamp,
                extra={"task_id": task_id, "legacy_status": original_status, "result": "archived"},
            )
            return {"action": "archived", "task": archived_payload}

        normalized = deepcopy(payload)
        normalized["status"] = (
            "pending" if original_status == "pending" else "candidate"
        )
        normalized.setdefault("task_type", "feature")
        normalized.setdefault("risk_level", normalized.get("risk", "L0") or "L0")
        normalized.setdefault("depends_on", [])
        normalized.setdefault("deliverables", [normalized.get("title", task_id)])
        normalized.setdefault(
            "source_docs", [f".omo/tasks/planned/{task_id}.yaml#legacy-normalized"]
        )
        normalized.setdefault("knowledge_refs", [])
        normalized.setdefault("handoff_refs", [])
        normalized.setdefault("entry_gate", [])
        normalized.setdefault("evidence_required", ["legacy planned packet normalized"])
        normalized.setdefault(
            "test_plan", ["python3 scripts/omo_worker.py task validate --all-planned"]
        )
        normalized["assigned_to"] = None
        normalized["dispatch_id"] = None
        normalized["run_ref"] = None
        normalized["approval_ref"] = None
        normalized["review_ref"] = None
        normalized.pop("started_at", None)
        normalized.pop("completed_at", None)
        normalized.pop("completed_by", None)
        normalized.pop("archived_at", None)
        normalized.pop("archived_by", None)

        risk_level = str(normalized.get("risk_level") or "L0")
        if not normalized.get("allowed_operation_level"):
            normalized["allowed_operation_level"] = (
                risk_level if risk_level in {"L2", "L3"} else "L0"
            )
        if "human_approval_required" not in normalized:
            normalized["human_approval_required"] = normalized.get(
                "allowed_operation_level"
            ) in {"L2", "L3"}

        errors = validate_task_data(normalized, group="planned")
        if errors:
            raise ValueError("invalid normalized planned task: " + "; ".join(errors))

        write_yaml_atomic(planned_path, normalized)
        artifact = {
            "kind": "planned_task_legacy_normalized",
            "task_id": task_id,
            "legacy_status": original_status,
            "task_ref": f".omo/tasks/planned/{task_id}.yaml",
            "actor": actor,
            "source_ref": source_ref,
            "normalized_at": timestamp,
            "normalized_status": normalized["status"],
        }
        artifact_path = (
            _delivery_root(omo_dir)
            / "tasks"
            / f"{task_id}-legacy-normalize-{_timestamp_slug(timestamp)}.yaml"
        )
        write_yaml_atomic(artifact_path, artifact)
        record_audit(
            action="ingress_normalize_legacy_planned_task",
            debt_id="",
            actor=actor,
            details=(
                f"task_id={task_id} legacy_status={original_status} normalized_status={normalized['status']} "
                f"source_ref={source_ref or '-'} artifact={artifact_path.relative_to(omo_dir.parent)}"
            ),
            audit_file=_audit_log_path(omo_dir),
        )
        _record_trail(
            omo_dir,
            actor=f"broker:{actor}",
            action="normalize_legacy_planned_task",
            target=f".omo/tasks/planned/{task_id}.yaml",
            parent_step_id=f"ingress:legacy-planned-normalize:{task_id}:{timestamp}",
        )
        _record_mutation(
            omo_dir,
            actor=actor,
            action="normalize_legacy_planned_task",
            target=f".omo/tasks/planned/{task_id}.yaml",
            artifact_ref=f".omo/_delivery/ingress/tasks/{artifact_path.name}",
            source_ref=source_ref,
            created_at=timestamp,
            extra={"task_id": task_id, "legacy_status": original_status, "normalized_status": normalized["status"]},
        )
        return {"action": "normalized", "task": normalized}


def upsert_debt_item(
    omo_dir: Path,
    *,
    debt_data: dict[str, Any],
    ingress_plane: str,
    source_ref: str = "",
    now: str | None = None,
) -> dict[str, Any]:
    if not isinstance(debt_data, dict):
        raise ValueError("debt_data must be a dict")
    if not debt_data.get("id"):
        raise ValueError("debt item requires id")
    if not debt_data.get("title"):
        raise ValueError("debt item requires title")

    debt_id = str(debt_data["id"])
    debt_path = omo_dir / "debt" / "items" / f"{debt_id}.yaml"
    timestamp = now or _utc_now()
    effective_source_ref = source_ref or str(debt_data.get("source_ref") or "")
    artifact_ref = f".omo/_delivery/ingress/debts/{debt_id}.yaml"

    with fcntl_lock(_lock_path(omo_dir)):
        registry = _load_registry(omo_dir)

        if effective_source_ref:
            mapped_debt_id = registry["debts"]["by_source_ref"].get(
                effective_source_ref
            )
            if mapped_debt_id and mapped_debt_id != debt_id:
                raise ValueError(
                    f"source_ref already mapped to different debt: {effective_source_ref} -> {mapped_debt_id}"
                )

        existing_payload = _load_yaml(debt_path) if debt_path.exists() else {}
        payload = deepcopy(existing_payload)
        payload.update(deepcopy(debt_data))
        payload["id"] = debt_id
        payload["title"] = str(payload["title"])
        payload["source_ref"] = effective_source_ref
        payload.setdefault("description", "")
        payload.setdefault("severity", "medium")
        payload.setdefault("source", ingress_plane)
        payload.setdefault("domain", "workspace")
        payload.setdefault("scope", "governance_kernel")
        payload.setdefault("owner", ingress_plane)
        payload.setdefault("affected_roots", [".omo"])
        payload.setdefault("evidence_refs", [])
        payload.setdefault("mitigation_refs", [])
        payload.setdefault("gate_level", "none")
        payload.setdefault("history", [])

        first_seen_at = str(
            existing_payload.get("first_seen_at")
            or payload.get("first_seen_at")
            or payload.get("registered_at")
            or timestamp
        )
        registered_at = str(
            existing_payload.get("registered_at")
            or payload.get("registered_at")
            or first_seen_at
        )
        opened_at = str(
            existing_payload.get("opened_at")
            or payload.get("opened_at")
            or registered_at
        )
        occurrence_count = int(existing_payload.get("occurrence_count") or 0) + 1

        payload["registered_at"] = registered_at
        payload["opened_at"] = opened_at
        payload["first_seen_at"] = first_seen_at
        payload["last_seen_at"] = timestamp
        payload["occurrence_count"] = occurrence_count
        payload["status"] = str(payload.get("status") or "open")
        payload["lifecycle_state"] = str(
            payload.get("lifecycle_state")
            or existing_payload.get("lifecycle_state")
            or "identified"
        )

        note = (
            f"Observed debt {debt_id} again (occurrence_count={occurrence_count})."
            if existing_payload
            else f"Registered debt item {debt_id}."
        )
        history = payload.get("history")
        if not isinstance(history, list):
            payload["history"] = []
        payload["history"].append(
            {
                "at": timestamp,
                "action": "register" if not existing_payload else "seen_again",
                "note": note,
                "actor": ingress_plane,
            }
        )

        write_yaml_atomic(debt_path, payload)

        debt_registry_path = omo_dir / "_truth" / "registry" / "debt.yaml"
        debt_registry = (
            _load_yaml(debt_registry_path)
            if debt_registry_path.exists()
            else {"version": 1}
        )
        debt_registry.setdefault("items_dir", ".omo/debt/items")
        debt_registry.setdefault("seed_items", [])
        debt_ref = f".omo/debt/items/{debt_id}.yaml"
        if debt_ref not in debt_registry["seed_items"]:
            debt_registry["seed_items"] = [*debt_registry["seed_items"], debt_ref]
        write_yaml_atomic(debt_registry_path, debt_registry)

        artifact = {
            "kind": "debt_upserted",
            "debt_id": debt_id,
            "title": payload["title"],
            "ingress_plane": ingress_plane,
            "source_ref": effective_source_ref,
            "created_at": registered_at,
            "last_seen_at": timestamp,
            "occurrence_count": occurrence_count,
            "debt_ref": debt_ref,
            "lifecycle_state": payload["lifecycle_state"],
            "artifact_ref": artifact_ref,
            "broker_ref": "projects/omo/src/omo/omo_ingress.py",
            "retention_mode": "manual_archive",
        }
        artifact_path = _delivery_root(omo_dir) / "debts" / f"{debt_id}.yaml"
        write_yaml_atomic(artifact_path, artifact)

        _register_ingress(
            registry,
            kind="debts",
            item_id=debt_id,
            source_ref=effective_source_ref,
            artifact_ref=artifact_ref,
            fingerprint=payload,
            created_at=registered_at,
        )
        _write_registry(omo_dir, registry)

        parent_step_id = f"ingress:debt:{debt_id}:{timestamp}"
        details = (
            f"debt_id={debt_id} ingress_plane={ingress_plane} "
            f"source_ref={effective_source_ref or '-'} artifact={artifact_path.relative_to(omo_dir.parent)}"
        )
        record_audit(
            action="ingress_upsert_debt",
            debt_id=debt_id,
            actor=ingress_plane,
            details=details,
            audit_file=_audit_log_path(omo_dir),
        )
        _record_trail(
            omo_dir,
            actor=f"broker:{ingress_plane}",
            action="upsert_debt_item",
            target=debt_ref,
            parent_step_id=parent_step_id,
        )
        _record_mutation(
            omo_dir,
            actor=ingress_plane,
            action="upsert_debt_item",
            target=debt_ref,
            artifact_ref=artifact["artifact_ref"],
            source_ref=effective_source_ref,
            created_at=timestamp,
            extra={"debt_id": debt_id, "occurrence_count": occurrence_count},
        )
        return payload


def remove_debt_item(
    omo_dir: Path,
    *,
    debt_id: str,
    actor: str,
    source_ref: str = "",
    now: str | None = None,
) -> bool:
    debt_path = omo_dir / "debt" / "items" / f"{debt_id}.yaml"
    artifact_path = _delivery_root(omo_dir) / "debts" / f"{debt_id}.yaml"
    debt_registry_path = omo_dir / "_truth" / "registry" / "debt.yaml"
    timestamp = now or _utc_now()

    with fcntl_lock(_lock_path(omo_dir)):
        if not debt_path.exists() and not artifact_path.exists():
            return False

        registry = _load_registry(omo_dir)
        if debt_id in registry["debts"]["by_id"]:
            existing = registry["debts"]["by_id"].pop(debt_id)
            mapped_source_ref = str(existing.get("source_ref") or "")
            if mapped_source_ref:
                registry["debts"]["by_source_ref"].pop(mapped_source_ref, None)
        elif source_ref:
            registry["debts"]["by_source_ref"].pop(source_ref, None)
        _write_registry(omo_dir, registry)

        if debt_registry_path.exists():
            debt_registry = _load_yaml(debt_registry_path) or {"version": 1}
            seed_items = debt_registry.get("seed_items", [])
            debt_ref = f".omo/debt/items/{debt_id}.yaml"
            debt_registry["seed_items"] = [
                item for item in seed_items if item != debt_ref
            ]
            write_yaml_atomic(debt_registry_path, debt_registry)

        if debt_path.exists():
            debt_path.unlink()
        if artifact_path.exists():
            artifact_path.unlink()

        record_audit(
            action="ingress_remove_debt",
            debt_id=debt_id,
            actor=actor,
            details=f"debt_id={debt_id} actor={actor}",
            audit_file=_audit_log_path(omo_dir),
        )
        _record_trail(
            omo_dir,
            actor=f"broker:{actor}",
            action="remove_debt_item",
            target=f".omo/debt/items/{debt_id}.yaml",
            parent_step_id=f"ingress:debt-remove:{debt_id}:{timestamp}",
        )
        return True
