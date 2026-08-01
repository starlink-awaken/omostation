"""omo_ingress goal 入口 (从 God Module 拆出, SRP · P60+ 第四步).

_goal_fingerprint / _goal_existing_fingerprint / _resolve_existing_goal / create_goal.
goal 指纹计算 + 已存在 goal 解析 + goal 创建. 被 omo_ingress / omo_governance 复用.
"""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

import yaml

from omo.omo_audit import record as record_audit
from omo.omo_ingress_paths import (
    _artifact_lifecycle_fields,
    _audit_log_path,
    _delivery_root,
    _load_yaml,
    _lock_path,
    _timestamp_slug,
    _utc_now,
    _workspace_relative,
)
from omo.omo_io import fcntl_lock, write_text_atomic, write_yaml_atomic


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


def _resolve_existing_goal(omo_dir: Path, goal_id: str) -> dict[str, Any] | None:
    goal_file = omo_dir / "goals" / "current.yaml"
    if not goal_file.exists():
        return None
    payload = _load_yaml(goal_file)
    for goal in payload.get("goals", []):
        if goal.get("id") == goal_id:
            return goal
    return None


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
    from omo.omo_ingress import (
        _load_registry,
        _record_mutation,
        _record_trail,
        _register_ingress,
        _write_registry,
    )

    """在 goals/current.yaml 中创建新 goal, 并写 ingress artifact."""
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
    artifact_ref = f"runtime/omo/_delivery/ingress/goals/{goal_id}.yaml"

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
            f"source_ref={source_ref or '-'} artifact={_workspace_relative(artifact_path)}"
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
    from omo.omo_ingress import _record_mutation, _record_trail

    """更新 goals/current.yaml 中指定 goal 的 progress."""
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
            f"source_ref={source_ref or '-'} artifact={_workspace_relative(artifact_path)}"
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
            artifact_ref=f"runtime/omo/_delivery/ingress/goals/{artifact_path.name}",
            source_ref=source_ref,
            created_at=timestamp,
            extra={"goal_id": goal_id, "progress": progress},
        )
        return deepcopy(target_goal)


def _load_goal_documents(goal_file: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    """Load frontmatter and body separately, including a damaged missing opener."""
    documents = [
        document
        for document in yaml.safe_load_all(goal_file.read_text(encoding="utf-8"))
        if isinstance(document, dict)
    ]
    if not documents:
        raise ValueError(f"goals file must contain a mapping: {goal_file}")
    if len(documents) == 1:
        return {}, deepcopy(documents[0])

    frontmatter = deepcopy(documents[0])
    payload: dict[str, Any] = {}
    for document in documents[1:]:
        payload.update(deepcopy(document))
    return frontmatter, payload


def _write_goal_documents(
    goal_file: Path,
    *,
    frontmatter: dict[str, Any],
    payload: dict[str, Any],
) -> None:
    """Write the canonical two-document goals format atomically."""
    frontmatter_yaml = yaml.safe_dump(
        frontmatter, sort_keys=False, allow_unicode=True
    ).rstrip()
    payload_yaml = yaml.safe_dump(payload, sort_keys=False, allow_unicode=True).rstrip()
    content = f"---\n{frontmatter_yaml}\n---\n{payload_yaml}\n"
    write_text_atomic(goal_file, content)


def reconcile_goals(
    omo_dir: Path,
    *,
    phase: int,
    current_wave: str,
    execution_mode: str,
    theme: str = "",
    archive_completed: bool = False,
    actor: str = "projects/omo",
    source_ref: str = "",
    now: str | None = None,
) -> dict[str, Any]:
    """Reconcile current goals through the governed broker and audit the mutation."""
    goal_file = omo_dir / "goals" / "current.yaml"
    if not goal_file.exists():
        raise FileNotFoundError(f"missing goals/current.yaml: {goal_file}")
    if phase < 0 or not current_wave.strip():
        raise ValueError("phase must be non-negative and current_wave must be non-empty")
    if not execution_mode.strip():
        raise ValueError("execution_mode must be non-empty")

    from omo.omo_ingress import _record_mutation, _record_trail

    timestamp = now or _utc_now()
    source_ref = source_ref or f"omo:goal:reconcile:phase-{phase}-{current_wave}"
    with fcntl_lock(_lock_path(omo_dir)):
        frontmatter, payload = _load_goal_documents(goal_file)
        payload["phase"] = phase
        payload["current_wave"] = current_wave
        payload["execution_mode"] = execution_mode
        if theme:
            payload["theme"] = theme

        archived_ids: list[str] = []
        if archive_completed:
            for goal in payload.get("goals", []):
                if not isinstance(goal, dict):
                    continue
                if goal.get("status") not in {"done", "completed"}:
                    continue
                goal["status"] = "archived"
                goal["archived_at"] = timestamp
                goal["archive_reason"] = "governed goal reconciliation"
                if "bet_status" in goal:
                    goal["bet_status"] = "closed"
                if goal.get("id"):
                    archived_ids.append(str(goal["id"]))

        _write_goal_documents(
            goal_file,
            frontmatter=frontmatter,
            payload=payload,
        )

        artifact = {
            "kind": "goals_reconciled",
            "goal_ref": ".omo/goals/current.yaml",
            "phase": phase,
            "current_wave": current_wave,
            "execution_mode": execution_mode,
            "theme": theme,
            "archived_goal_ids": archived_ids,
            "actor": actor,
            "source_ref": source_ref,
            "updated_at": timestamp,
        }
        artifact_path = (
            _delivery_root(omo_dir)
            / "goals"
            / f"reconcile-{_timestamp_slug(timestamp)}.yaml"
        )
        write_yaml_atomic(artifact_path, artifact)

        parent_step_id = f"ingress:goal-reconcile:{timestamp}"
        details = (
            f"phase={phase} current_wave={current_wave} execution_mode={execution_mode} "
            f"archived={','.join(archived_ids) or '-'} artifact={_workspace_relative(artifact_path)}"
        )
        record_audit(
            action="ingress_reconcile_goals",
            debt_id="",
            actor=actor,
            details=details,
            audit_file=_audit_log_path(omo_dir),
        )
        _record_trail(
            omo_dir,
            actor=f"broker:{actor}",
            action="reconcile_goals",
            target=".omo/goals/current.yaml",
            parent_step_id=parent_step_id,
        )
        _record_mutation(
            omo_dir,
            actor=actor,
            action="reconcile_goals",
            target=".omo/goals/current.yaml",
            artifact_ref=f"runtime/omo/_delivery/ingress/goals/{artifact_path.name}",
            source_ref=source_ref,
            created_at=timestamp,
            extra={
                "phase": phase,
                "current_wave": current_wave,
                "execution_mode": execution_mode,
                "archived_goal_ids": archived_ids,
            },
        )
        return deepcopy(payload)
