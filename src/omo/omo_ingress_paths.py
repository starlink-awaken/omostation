"""omo_ingress 路径/时间/lifecycle 工具 (从 God Module omo_ingress.py 拆出, SRP).

纯函数工具: UTC 时间 / timestamp slug / doc 名 / delivery 路径 / task 查找 / artifact lifecycle.
无业务逻辑, 被 omo_ingress.py (治理 broker 入口) 复用.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from omo.omo_shared import load_yaml


def _utc_now() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _timestamp_slug(timestamp: str) -> str:
    return timestamp.replace(":", "-")


def _safe_doc_name(title: str) -> str:
    return title.lower().replace(" ", "-").replace("/", "-").replace(":", "")[:60]


def _load_yaml(path: Path) -> dict[str, Any]:
    return load_yaml(path)


def _delivery_root(omo_dir: Path) -> Path:
    return omo_dir / "_delivery" / "ingress"


def _audit_log_path(omo_dir: Path) -> Path:
    return _delivery_root(omo_dir) / "ingress-audit.jsonl"


def _trail_log_path(omo_dir: Path) -> Path:
    return _delivery_root(omo_dir) / "ingress-trail.jsonl"


def _lock_path(omo_dir: Path) -> Path:
    return _delivery_root(omo_dir) / "ingress.lock"


def _registry_path(omo_dir: Path) -> Path:
    return _delivery_root(omo_dir) / "registry.yaml"


def _mutation_log_path(omo_dir: Path) -> Path:
    return omo_dir / "change-log" / "mutations.jsonl"


def _find_task_path(
    omo_dir: Path,
    task_id: str,
    *,
    groups: tuple[str, ...] = ("planned", "active", "blocked", "done", "remediation"),
) -> tuple[str, Path] | None:
    for group in groups:
        group_dir = omo_dir / "tasks" / group
        if not group_dir.exists():
            continue
        for task_file in sorted(group_dir.glob("*.yaml")):
            payload = _load_yaml(task_file)
            if payload.get("id") == task_id:
                return group, task_file
    return None


def _artifact_lifecycle_fields(*, artifact_ref: str) -> dict[str, Any]:
    return {
        "artifact_ref": artifact_ref,
        "broker_ref": "projects/omo/src/omo/omo_ingress.py",
        "retention_mode": "manual_archive",
        "lifecycle_state": "active",
    }
