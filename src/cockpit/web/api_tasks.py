"""Tasks API endpoints.

提供任务管理功能。

Routes:
    GET    /api/tasks              → 任务列表
    GET    /api/tasks/:id          → 任务详情
    POST   /api/tasks/:id/pause    → 暂停任务
    POST   /api/tasks/:id/resume   → 恢复任务
    POST   /api/tasks/:id/cancel   → 取消任务
"""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query

router = APIRouter()

# L4-kernel 项目路径
WORKSPACE_DIR = Path("/Users/xiamingxing/Workspace")
L4_KERNEL_DIR = WORKSPACE_DIR / "projects" / "l4-kernel"


def run_l4_script(script_name: str, args: list[str] | None = None) -> dict | None:
    """运行 L4-kernel 脚本并返回 JSON 结果。"""
    script_path = L4_KERNEL_DIR / "scripts" / script_name
    if not script_path.exists():
        return None

    cmd = [sys.executable, str(script_path)]
    if args:
        cmd.extend(args)

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0:
            return json.loads(result.stdout)
        else:
            print(f"Script {script_name} failed: {result.stderr}")
            return None
    except (subprocess.TimeoutExpired, json.JSONDecodeError, Exception) as e:
        print(f"Error running {script_name}: {e}")
        return None


def get_tasks_from_omo() -> list[dict]:
    """从 OMO 获取任务列表。"""
    tasks_dir = WORKSPACE_DIR / ".omo" / "tasks"
    tasks = []

    # 读取活跃任务
    active_dir = tasks_dir / "active"
    if active_dir.exists():
        for task_file in active_dir.glob("*.yaml"):
            try:
                import yaml

                with open(task_file) as f:
                    task_data = yaml.safe_load(f) or {}
                tasks.append(
                    {
                        "id": task_data.get("id", task_file.stem),
                        "title": task_data.get("title", task_file.stem),
                        "description": task_data.get("description", ""),
                        "status": "in_progress",
                        "progress": task_data.get("progress", 0),
                        "created_at": task_data.get("created_at", datetime.now(UTC).isoformat()),
                        "updated_at": task_data.get("updated_at", datetime.now(UTC).isoformat()),
                        "assignee": task_data.get("assignee", None),
                        "priority": task_data.get("priority", "medium"),
                        "tags": task_data.get("tags", []),
                    }
                )
            except Exception:  # noqa: S112
                continue

    # 读取计划任务
    planned_dir = tasks_dir / "planned"
    if planned_dir.exists():
        for task_file in planned_dir.glob("*.yaml"):
            try:
                import yaml

                with open(task_file) as f:
                    task_data = yaml.safe_load(f) or {}
                tasks.append(
                    {
                        "id": task_data.get("id", task_file.stem),
                        "title": task_data.get("title", task_file.stem),
                        "description": task_data.get("description", ""),
                        "status": "pending",
                        "progress": 0,
                        "created_at": task_data.get("created_at", datetime.now(UTC).isoformat()),
                        "updated_at": task_data.get("updated_at", datetime.now(UTC).isoformat()),
                        "assignee": task_data.get("assignee", None),
                        "priority": task_data.get("priority", "medium"),
                        "tags": task_data.get("tags", []),
                    }
                )
            except Exception:  # noqa: S112
                continue

    # 读取完成任务
    done_dir = tasks_dir / "done"
    if done_dir.exists():
        for task_file in list(done_dir.glob("*.yaml"))[:10]:  # 只取最近 10 个
            try:
                import yaml

                with open(task_file) as f:
                    task_data = yaml.safe_load(f) or {}
                tasks.append(
                    {
                        "id": task_data.get("id", task_file.stem),
                        "title": task_data.get("title", task_file.stem),
                        "description": task_data.get("description", ""),
                        "status": "completed",
                        "progress": 100,
                        "created_at": task_data.get("created_at", datetime.now(UTC).isoformat()),
                        "updated_at": task_data.get("updated_at", datetime.now(UTC).isoformat()),
                        "assignee": task_data.get("assignee", None),
                        "priority": task_data.get("priority", "medium"),
                        "tags": task_data.get("tags", []),
                    }
                )
            except Exception:  # noqa: S112
                continue

    return tasks


@router.get("/api/tasks")
async def get_tasks(
    status: str | None = Query(None, description="任务状态过滤"),
    limit: int = Query(100, description="返回数量限制"),
    sort: str = Query("updated", description="排序方式"),
):
    """获取任务列表。"""
    tasks = get_tasks_from_omo()

    # 过滤
    if status:
        tasks = [t for t in tasks if t["status"] == status]

    # 排序
    if sort == "updated":
        tasks.sort(key=lambda t: t.get("updated_at", ""), reverse=True)
    elif sort == "created":
        tasks.sort(key=lambda t: t.get("created_at", ""), reverse=True)

    # 限制数量
    tasks = tasks[:limit]

    return {
        "items": tasks,
        "total": len(tasks),
    }


@router.get("/api/tasks/{task_id}")
async def get_task(task_id: str):
    """获取任务详情。"""
    tasks = get_tasks_from_omo()
    for task in tasks:
        if task["id"] == task_id:
            return task
    raise HTTPException(status_code=404, detail="Task not found")


@router.post("/api/tasks/{task_id}/pause")
async def pause_task(task_id: str):
    """暂停任务。"""
    return {
        "id": task_id,
        "status": "pending",
        "updated_at": datetime.now(UTC).isoformat(),
    }


@router.post("/api/tasks/{task_id}/resume")
async def resume_task(task_id: str):
    """恢复任务。"""
    return {
        "id": task_id,
        "status": "in_progress",
        "updated_at": datetime.now(UTC).isoformat(),
    }


@router.post("/api/tasks/{task_id}/cancel")
async def cancel_task(task_id: str):
    """取消任务。"""
    return {
        "id": task_id,
        "status": "cancelled",
        "updated_at": datetime.now(UTC).isoformat(),
    }
