"""omo_ingress goal 辅助函数 (从 God Module 拆出, SRP · P60+ 第四步).

_goal_fingerprint / _goal_existing_fingerprint / _resolve_existing_goal.
goal 指纹计算 + 已存在 goal 解析. 被 omo_ingress.create_goal/update_goal_progress 复用.
(public create_goal/update_goal_progress 体大, 暂留 omo_ingress, 后续可移此.)
"""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

from omo.omo_ingress_paths import _load_yaml


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
