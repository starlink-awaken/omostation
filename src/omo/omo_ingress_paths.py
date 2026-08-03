"""omo_ingress 路径/时间/lifecycle 工具 (从 God Module omo_ingress.py 拆出, SRP).

纯函数工具: UTC 时间 / timestamp slug / doc 名 / delivery 路径 / task 查找 / artifact lifecycle.
无业务逻辑, 被 omo_ingress.py (治理 broker 入口) 复用.

2026-07-01: 高 churn 的 ingress/evolution/audit 产物迁移到 <workspace>/runtime/omo/ 镜像,
             稳定 SSOT 保留在 .omo/。本模块封装迁移后的路径, 调用方无感。
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from omo.omo_paths import WORKSPACE_ROOT
from omo.omo_shared import load_yaml


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _timestamp_slug(timestamp: str) -> str:
    return timestamp.replace(":", "-")


def _safe_doc_name(title: str) -> str:
    return title.lower().replace(" ", "-").replace("/", "-").replace(":", "")[:60]


def _load_yaml(path: Path) -> dict[str, Any]:
    return load_yaml(path)


# ── 运行时镜像根 (高 churn, 不入仓) ─────────────────────────────────


def _runtime_omo_root(workspace_root: Path) -> Path:
    return workspace_root / "runtime" / "omo"


# ── 运行时镜像路径 (高 churn, 不入仓) ───────────────────────────────


def _delivery_root(omo_dir: Path) -> Path:
    """Ingress delivery root under <workspace>/runtime/omo (high-churn artifacts)."""
    return _runtime_omo_root(omo_dir.parent) / "_delivery" / "ingress"


def _audit_log_path(omo_dir: Path) -> Path:
    return _delivery_root(omo_dir) / "ingress-audit.jsonl"


def _trail_log_path(omo_dir: Path) -> Path:
    return _delivery_root(omo_dir) / "ingress-trail.jsonl"


def _lock_path(omo_dir: Path) -> Path:
    return _delivery_root(omo_dir) / "ingress.lock"


def _registry_path(omo_dir: Path) -> Path:
    return _delivery_root(omo_dir) / "registry.yaml"


def _mutation_log_path(omo_dir: Path) -> Path:
    return _runtime_omo_root(omo_dir.parent) / "change-log" / "mutations.jsonl"


# ── 治理演化/审计运行时路径 ─────────────────────────────────────────


def _evolution_dir(workspace_root: Path) -> Path:
    return _runtime_omo_root(workspace_root) / "_control" / "evolution"


def _drift_dir(workspace_root: Path) -> Path:
    return _evolution_dir(workspace_root) / "drift"


def _drift_history_dir(workspace_root: Path) -> Path:
    return _evolution_dir(workspace_root) / "drift-history"


def _approval_board_dir(workspace_root: Path) -> Path:
    return _evolution_dir(workspace_root) / "approval-board"


def _loop_dir(workspace_root: Path) -> Path:
    return _evolution_dir(workspace_root) / "loop"


def _self_evolve_dir(workspace_root: Path) -> Path:
    return _evolution_dir(workspace_root) / "self-evolve"


# ── Task / Retrospective 运行时路径 ─────────────────────────────────


def _done_task_group_dir(group: str, workspace_root: Path) -> Path:
    return _runtime_omo_root(workspace_root) / "tasks" / "registry" / "done" / group


def _retrospective_dir(group: str, workspace_root: Path) -> Path:
    return _done_task_group_dir(group, workspace_root)


def _dependency_baseline_path(workspace_root: Path) -> Path:
    """Generated dependency baseline lives in runtime truth dir."""
    return (
        _runtime_omo_root(workspace_root)
        / "_truth"
        / "registry"
        / "dependency-baseline.yaml"
    )


# ── 路径显示辅助 ───────────────────────────────────────────────────


def _workspace_relative(path: Path, workspace_root: Path | None = None) -> str:
    """Return a workspace-relative path string for logging.

    Falls back to absolute path if the file is outside the workspace.
    """
    root = workspace_root or WORKSPACE_ROOT
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


# ── Task 查找 ──────────────────────────────────────────────────────


def _find_task_path(
    omo_dir: Path,
    task_id: str,
    *,
    groups: tuple[str, ...] = ("planned", "active", "blocked", "done", "remediation"),
) -> tuple[str, Path] | None:
    """Find a task file across stable and runtime task directories.

    - planned/active/blocked/remediation remain in .omo/tasks/
    - done tasks (including retrospectives) moved to runtime/omo/tasks/registry/done/
    - archived/done is retained under .omo/tasks/ for post-execution closeout metadata.
    """
    workspace_root = omo_dir.parent
    for group in groups:
        if group == "done":
            group_dirs = (
                _done_task_group_dir(group, workspace_root),
                omo_dir / "tasks" / "done",
            )
        elif group == "archived/done":
            group_dirs = (omo_dir / "tasks" / "archived" / "done",)
        else:
            group_dirs = (omo_dir / "tasks" / group,)
        for group_dir in group_dirs:
            if not group_dir.exists():
                continue
            for task_file in sorted(group_dir.glob("*.yaml")):
                payload = _load_yaml(task_file)
                if payload.get("id") == task_id:
                    return group, task_file
    return None


# ── Artifact lifecycle metadata ────────────────────────────────────


def _artifact_lifecycle_fields(*, artifact_ref: str) -> dict[str, Any]:
    return {
        "artifact_ref": artifact_ref,
        "broker_ref": "projects/omo/src/omo/omo_ingress.py",
        "retention_mode": "manual_archive",
        "lifecycle_state": "active",
    }
