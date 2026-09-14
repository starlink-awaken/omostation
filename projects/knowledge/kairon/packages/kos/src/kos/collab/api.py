"""KOS Collab API — L3协作层CRUD。

数据存储: KOS retrieval DB 中的 kos_collab_tasks 表。
"""

import json
import sqlite3
import threading
from datetime import UTC, datetime
from typing import Any

from kos.config import get_artifact_path  # type: ignore[import-untyped, import-not-found]

from .agentmesh import dispatch_to_agentmesh

_lock = threading.Lock()


def _get_db() -> sqlite3.Connection:
    db_path = get_artifact_path("retrievalDatabase")
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def _ensure_table(conn: sqlite3.Connection) -> None:
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS kos_collab_tasks (
            task_id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            goal TEXT DEFAULT '',
            creator TEXT NOT NULL,
            visibility_scope TEXT DEFAULT 'private',
            subtasks TEXT DEFAULT '[]',
            artifacts TEXT DEFAULT '[]',
            progress INTEGER DEFAULT 0,
            status TEXT DEFAULT 'active',
            timeline TEXT DEFAULT '[]',
            resource_usage TEXT DEFAULT '{}',
            created_at TEXT DEFAULT '',
            updated_at TEXT DEFAULT ''
        );
    """)
    conn.commit()


def create_task(
    title: str, goal: str, creator: str, visibility_scope: str = "private", subtasks: list[dict] | None = None
) -> dict[str, Any] | None:
    conn = _get_db()
    _ensure_table(conn)
    now = datetime.now(UTC).isoformat()
    task_id = f"task:{now[:10]}:{hash(title + creator) & 0xFFFF:04x}"
    subtasks_json = json.dumps(subtasks or [], ensure_ascii=False)
    conn.execute(
        """INSERT INTO kos_collab_tasks
           (task_id, title, goal, creator, visibility_scope, subtasks, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (task_id, title, goal, creator, visibility_scope, subtasks_json, now, now),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM kos_collab_tasks WHERE task_id=?", (task_id,)).fetchone()
    conn.close()

    result = _row_to_dict(row)

    # Dispatch to agentmesh for execution (non-blocking failure)
    agentmesh_id = dispatch_to_agentmesh(
        {
            "type": "collab",
            "name": title,
            "goal": goal,
            "visibility": visibility_scope,
            "subtasks": subtasks or [],
        }
    )
    if agentmesh_id:
        updated = add_artifact(task_id, {"agentmesh_task_id": agentmesh_id})
        if updated:
            result = updated

    return result


def get_task(task_id: str) -> dict[str, Any] | None:
    conn = _get_db()
    _ensure_table(conn)
    row = conn.execute("SELECT * FROM kos_collab_tasks WHERE task_id=?", (task_id,)).fetchone()
    conn.close()
    if row is None:
        return None
    return _row_to_dict(row)


def list_tasks(
    status: str = "", creator: str = "", visibility_scope: str = "", viewer_subject_id: str = "", limit: int = 20
) -> list[dict[str, Any]]:
    conn = _get_db()
    _ensure_table(conn)
    query = "SELECT * FROM kos_collab_tasks WHERE 1=1"
    params: list[Any] = []
    if status:
        query += " AND status=?"
        params.append(status)
    if creator:
        query += " AND creator=?"
        params.append(creator)
    if visibility_scope:
        query += " AND visibility_scope=?"
        params.append(visibility_scope)
    elif viewer_subject_id:
        query += " AND (creator=? OR visibility_scope IN ('public', 'org'))"
        params.extend([viewer_subject_id])
    query += " ORDER BY updated_at DESC LIMIT ?"
    params.append(limit)
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [r for r in (_row_to_dict(r) for r in rows) if r is not None]


def update_task(task_id: str, data: dict[str, Any]) -> dict[str, Any] | None:
    conn = _get_db()
    _ensure_table(conn)
    row = conn.execute("SELECT * FROM kos_collab_tasks WHERE task_id=?", (task_id,)).fetchone()
    if row is None:
        conn.close()
        return None
    now = datetime.now(UTC).isoformat()
    allowed = {"title", "goal", "visibility_scope", "status", "resource_usage"}
    updates = {}
    for k, v in data.items():
        if k in allowed:
            updates[k] = v
    if not updates:
        conn.close()
        return _row_to_dict(row)
    updates["updated_at"] = now
    set_clause = ", ".join(f"{k}=?" for k in updates)
    values = list(updates.values()) + [task_id]
    conn.execute(f"UPDATE kos_collab_tasks SET {set_clause} WHERE task_id=?", values)
    conn.commit()
    row = conn.execute("SELECT * FROM kos_collab_tasks WHERE task_id=?", (task_id,)).fetchone()
    conn.close()
    return _row_to_dict(row)


def claim_subtask(
    task_id: str, subtask_index: int = 0, subtask_id: str | None = None, assignee: str = ""
) -> dict[str, Any]:
    """认领子任务。支持整数下标(subtask_index)或字符串ID(subtask_id)。使用BEGIN IMMEDIATE行锁 + 依赖检查。"""
    conn = _get_db()
    _ensure_table(conn)
    try:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute("SELECT * FROM kos_collab_tasks WHERE task_id=?", (task_id,)).fetchone()
        if row is None:
            conn.rollback()
            conn.close()
            return {"error": f"Task not found: {task_id}", "code": "NOT_FOUND"}

        subtasks = json.loads(row["subtasks"] or "[]")

        # 如果传了 subtask_id，按 id 匹配找到下标
        if subtask_id is not None:
            matched_idx = None
            for idx, st_item in enumerate(subtasks):
                if st_item.get("id") == subtask_id:
                    matched_idx = idx
                    break
            if matched_idx is None:
                conn.rollback()
                conn.close()
                return {"error": f"Subtask not found: {subtask_id}", "code": "SUBTASK_NOT_FOUND"}
            subtask_index = matched_idx

        if subtask_index < 0 or subtask_index >= len(subtasks):
            conn.rollback()
            conn.close()
            return {"error": f"Subtask index {subtask_index} out of range", "code": "INVALID_INDEX"}

        st = subtasks[subtask_index]
        if st.get("status") not in ("pending", None):
            conn.rollback()
            conn.close()
            return {"error": f"Subtask already claimed: status={st.get('status')}", "code": "ALREADY_CLAIMED"}

        # 依赖检查
        deps = st.get("depends_on", [])
        for dep_idx in deps:
            if dep_idx < 0 or dep_idx >= len(subtasks):
                continue
            dep_st = subtasks[dep_idx]
            if dep_st.get("status") != "done":
                conn.rollback()
                conn.close()
                return {
                    "error": f"Dependency not met: subtask {dep_idx} is {dep_st.get('status', 'unknown')}",
                    "code": "DEPENDENCY_NOT_MET",
                    "blocked_by": dep_idx,
                }

        st["status"] = "in_progress"
        st["assignee"] = assignee
        now = datetime.now(UTC).isoformat()
        subtasks_json = json.dumps(subtasks, ensure_ascii=False)
        timeline_entry = json.dumps(
            {"time": now, "event": "subtask_claimed", "detail": f"Subtask {subtask_index} claimed by {assignee}"}
        )
        conn.execute(
            """UPDATE kos_collab_tasks SET subtasks=?, updated_at=?,
               timeline=json_insert(timeline, '$[#]', json(?)) WHERE task_id=?""",
            (subtasks_json, now, timeline_entry, task_id),
        )
        conn.execute("COMMIT")
        row = conn.execute("SELECT * FROM kos_collab_tasks WHERE task_id=?", (task_id,)).fetchone()
        conn.close()
        return {"status": "claimed", "subtask": st, "task": _row_to_dict(row)}
    except Exception as e:
        try:
            conn.rollback()
        except Exception:
            pass
        conn.close()
        return {"error": str(e), "code": "INTERNAL_ERROR"}


def complete_subtask(task_id: str, subtask_index: int, assignee: str) -> dict[str, Any]:
    """完成子任务。验证assignee → 计算progress% → 满100自动complete。"""
    conn = _get_db()
    _ensure_table(conn)
    try:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute("SELECT * FROM kos_collab_tasks WHERE task_id=?", (task_id,)).fetchone()
        if row is None:
            conn.rollback()
            conn.close()
            return {"error": f"Task not found: {task_id}", "code": "NOT_FOUND"}

        subtasks = json.loads(row["subtasks"] or "[]")
        if subtask_index < 0 or subtask_index >= len(subtasks):
            conn.rollback()
            conn.close()
            return {"error": f"Subtask index {subtask_index} out of range", "code": "INVALID_INDEX"}

        st = subtasks[subtask_index]
        if st.get("assignee") != assignee:
            conn.rollback()
            conn.close()
            return {
                "error": f"Assignee mismatch: expected {st.get('assignee')}, got {assignee}",
                "code": "ASSIGNEE_MISMATCH",
            }

        st["status"] = "done"
        now = datetime.now(UTC).isoformat()
        subtasks_json = json.dumps(subtasks, ensure_ascii=False)

        # 自动计算进度
        total = len(subtasks)
        done = sum(1 for s in subtasks if s.get("status") == "done")
        progress = int(done / total * 100) if total > 0 else 0
        new_status: str | None = None
        if progress >= 100:
            new_status = "done"
            progress = 100

        timeline_entry = json.dumps(
            {"time": now, "event": "subtask_completed", "detail": f"Subtask {subtask_index} completed by {assignee}"}
        )

        if new_status:
            conn.execute(
                """UPDATE kos_collab_tasks SET subtasks=?, progress=?, status=?, updated_at=?,
                   timeline=json_insert(timeline, '$[#]', json(?)) WHERE task_id=?""",
                (subtasks_json, progress, new_status, now, timeline_entry, task_id),
            )
        else:
            conn.execute(
                """UPDATE kos_collab_tasks SET subtasks=?, progress=?, updated_at=?,
                   timeline=json_insert(timeline, '$[#]', json(?)) WHERE task_id=?""",
                (subtasks_json, progress, now, timeline_entry, task_id),
            )
        conn.execute("COMMIT")
        row = conn.execute("SELECT * FROM kos_collab_tasks WHERE task_id=?", (task_id,)).fetchone()
        conn.close()
        return {
            "status": "completed",
            "subtask": st,
            "progress": progress,
            "task_status": new_status or row["status"],
            "task": _row_to_dict(row),
        }
    except Exception as e:
        try:
            conn.rollback()
        except Exception:
            pass
        conn.close()
        return {"error": str(e), "code": "INTERNAL_ERROR"}


def find_task_by_agentmesh_id(agentmesh_task_id: str) -> dict[str, Any] | None:
    """Search kos_collab_tasks for a task whose artifacts contain the given agentmesh_task_id.

    Returns the task dict or None if not found.
    """
    conn = _get_db()
    _ensure_table(conn)
    rows = conn.execute("SELECT * FROM kos_collab_tasks").fetchall()
    for row in rows:
        artifacts = json.loads(row["artifacts"] or "[]")
        for art in artifacts:
            if isinstance(art, dict) and art.get("agentmesh_task_id") == agentmesh_task_id:
                conn.close()
                return _row_to_dict(row)
    conn.close()
    return None


def update_task_by_agentmesh_id(agentmesh_task_id: str, data: dict[str, Any]) -> dict[str, Any] | None:
    """Update a KOS collab task by its agentmesh task ID (found in artifacts).

    Allowed fields are the same as update_task(): title, goal, visibility_scope, status, resource_usage.
    Returns the updated task dict, or None if not found.
    """
    conn = _get_db()
    _ensure_table(conn)
    rows = conn.execute("SELECT * FROM kos_collab_tasks").fetchall()
    target_task_id: str | None = None
    for row in rows:
        artifacts = json.loads(row["artifacts"] or "[]")
        for art in artifacts:
            if isinstance(art, dict) and art.get("agentmesh_task_id") == agentmesh_task_id:
                target_task_id = row["task_id"]
                break
        if target_task_id:
            break
    conn.close()

    if target_task_id is None:
        return None
    return update_task(target_task_id, data)


def add_artifact(task_id: str, artifact: dict[str, Any]) -> dict[str, Any] | None:
    """给任务添加产出物。"""
    conn = _get_db()
    _ensure_table(conn)
    row = conn.execute("SELECT * FROM kos_collab_tasks WHERE task_id=?", (task_id,)).fetchone()
    if row is None:
        conn.close()
        return None
    artifacts = json.loads(row["artifacts"] or "[]")
    artifact.setdefault("id", f"artifact:{len(artifacts) + 1}")
    artifacts.append(artifact)
    now = datetime.now(UTC).isoformat()
    artifacts_json = json.dumps(artifacts, ensure_ascii=False)
    conn.execute(
        "UPDATE kos_collab_tasks SET artifacts=?, updated_at=? WHERE task_id=?",
        (artifacts_json, now, task_id),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM kos_collab_tasks WHERE task_id=?", (task_id,)).fetchone()
    conn.close()
    return _row_to_dict(row)


def _row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    d = dict(row)
    for key in ("subtasks", "artifacts", "timeline"):
        try:
            d[key] = json.loads(d.get(key, "[]") or "[]")
        except (json.JSONDecodeError, TypeError):
            d[key] = []
    try:
        d["resource_usage"] = json.loads(d.get("resource_usage", "{}") or "{}")
    except (json.JSONDecodeError, TypeError):
        d["resource_usage"] = {}
    return d
