"""实时协作模块 (Phase 12 / T164 + T165)

T164: TaskObject实时同步 — WebSocket推送状态变更
T165: 联合编辑 — 多人同时编辑知识条目 (乐观锁+冲突检测)
"""

from __future__ import annotations

import hashlib
import json
import threading
from pathlib import Path

REALTIME_DB = Path.home() / ".kos" / "realtime.db"


# ─── T164: WebSocket事件推送 ───


class TaskSync:
    """TaskObject实时同步 — 状态变更时推送到所有订阅者

    架构:
    1. Task变更 → 写入SQLite + 触发WebSocket事件
    2. 订阅者收到事件 → 更新本地缓存
    3. 断线重连 → 拉取增量变更
    """

    def __init__(self):
        self._ensure_schema()
        self._subscribers: dict[str, list[str]] = {}  # task_id → [ws_urls]
        self._lock = threading.Lock()

    def _get_conn(self):
        import sqlite3

        return sqlite3.connect(str(REALTIME_DB))

    def _ensure_schema(self):
        conn = self._get_conn()
        conn.execute("""
            CREATE TABLE IF NOT EXISTS task_events (
                event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id TEXT NOT NULL,
                event_type TEXT NOT NULL,
                payload TEXT DEFAULT '{}',
                version INTEGER DEFAULT 1,
                created_at TEXT DEFAULT (datetime('now'))
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS task_snapshots (
                task_id TEXT PRIMARY KEY,
                version INTEGER DEFAULT 1,
                snapshot TEXT DEFAULT '{}',
                updated_at TEXT DEFAULT (datetime('now'))
            )
        """)
        conn.commit()
        conn.close()

    def on_task_change(self, task_id: str, event_type: str, payload: dict) -> dict:
        """Task变更时调用 - 记录事件+推送订阅者。"""
        conn = self._get_conn()

        # 获取当前版本号
        row = conn.execute(
            "SELECT version FROM task_snapshots WHERE task_id=?",
            (task_id,),
        ).fetchone()
        version = (row[0] + 1) if row else 1

        # 写入事件
        conn.execute(
            "INSERT INTO task_events (task_id, event_type, payload, version) VALUES (?, ?, ?, ?)",
            (task_id, event_type, json.dumps(payload), version),
        )

        # 更新快照
        conn.execute(
            "INSERT OR REPLACE INTO task_snapshots (task_id, version, snapshot) VALUES (?, ?, ?)",
            (task_id, version, json.dumps(payload)),
        )
        event_id = conn.total_changes if hasattr(conn, "total_changes") else 0
        conn.commit()
        conn.close()

        # 推送事件 (WebSocket或HTTP回调)
        pushed = self._notify_subscribers(task_id, event_type, payload)

        return {"event_id": event_id, "version": version, "pushed_to": pushed}

    def subscribe(self, task_id: str, callback_url: str):
        """订阅一个Task的变更通知。"""
        with self._lock:
            if task_id not in self._subscribers:
                self._subscribers[task_id] = []
            if callback_url not in self._subscribers[task_id]:
                self._subscribers[task_id].append(callback_url)

    def get_history(self, task_id: str, since_version: int = 0, limit: int = 50) -> list[dict]:
        """获取Task变更历史(用于断线重连后的增量同步)。"""
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT * FROM task_events WHERE task_id=? AND version>? ORDER BY version ASC LIMIT ?",
            (task_id, since_version, limit),
        ).fetchall()
        conn.close()
        cols = ["event_id", "task_id", "event_type", "payload", "version", "created_at"]
        result = []
        for r in rows:
            d = dict(zip(cols, r, strict=True))
            d["payload"] = json.loads(d["payload"])
            result.append(d)
        return result

    def get_snapshot(self, task_id: str) -> dict | None:
        """获取Task最新快照。"""
        conn = self._get_conn()
        row = conn.execute(
            "SELECT version, snapshot FROM task_snapshots WHERE task_id=?",
            (task_id,),
        ).fetchone()
        conn.close()
        if row:
            return {"version": row[0], "snapshot": json.loads(row[1])}
        return None

    def _notify_subscribers(self, task_id: str, event_type: str, payload: dict) -> int:
        """推送事件到所有订阅者。"""
        from urllib import request

        pushed = 0
        subs = self._subscribers.get(task_id, [])
        for url in subs:
            try:
                data = json.dumps(
                    {
                        "task_id": task_id,
                        "event_type": event_type,
                        "payload": payload,
                    }
                ).encode()
                req = request.Request(url, data=data, headers={"Content-Type": "application/json"})  # noqa: S310
                request.urlopen(req, timeout=5)  # noqa: S310
                pushed += 1
            except Exception:
                pass
        return pushed


# ─── T165: 联合编辑 ───


class CollaborativeEdit:
    """联合编辑 — 多人同时编辑知识条目

    使用乐观锁+版本号检测冲突:
    - 每次编辑带version
    - 提交时检查version是否匹配
    - 版本冲突 → 返回冲突详情, 客户端解决
    """

    def __init__(self):
        self._ensure_schema()

    def _get_conn(self):
        import sqlite3

        return sqlite3.connect(str(REALTIME_DB))

    def _ensure_schema(self):
        conn = self._get_conn()
        conn.execute("""
            CREATE TABLE IF NOT EXISTS collab_edits (
                entity_id TEXT NOT NULL,
                editor TEXT NOT NULL,
                version INTEGER DEFAULT 1,
                content TEXT DEFAULT '',
                checksum TEXT DEFAULT '',
                edited_at TEXT DEFAULT (datetime('now')),
                PRIMARY KEY (entity_id, editor)
            )
        """)
        conn.commit()
        conn.close()

    def begin_edit(self, entity_id: str, editor: str) -> dict:
        """开始编辑: 获取当前内容+版本。"""
        conn = self._get_conn()
        row = conn.execute(
            "SELECT content, checksum FROM collab_edits WHERE entity_id=?",
            (entity_id,),
        ).fetchone()
        conn.close()

        if row:
            return {
                "entity_id": entity_id,
                "content": row[0],
                "checksum": row[1],
                "version": self._get_version(entity_id),
            }
        return {"entity_id": entity_id, "content": "", "checksum": "", "version": 0}

    def submit_edit(self, entity_id: str, editor: str, content: str, expected_version: int) -> dict:
        """提交编辑 (乐观锁: 版本号不匹配=冲突)。"""
        current_version = self._get_version(entity_id)
        if current_version != expected_version:
            return {
                "status": "conflict",
                "entity_id": entity_id,
                "expected_version": expected_version,
                "current_version": current_version,
                "message": f"Conflict: expected v{expected_version}, current v{current_version}",
            }

        new_version = current_version + 1
        checksum = hashlib.md5(content.encode()).hexdigest()[:12]  # noqa: S324

        conn = self._get_conn()
        conn.execute(
            "INSERT OR REPLACE INTO collab_edits (entity_id, editor, version, content, checksum) VALUES (?, ?, ?, ?, ?)",
            (entity_id, editor, new_version, content, checksum),
        )
        conn.commit()
        conn.close()

        return {
            "status": "saved",
            "entity_id": entity_id,
            "editor": editor,
            "version": new_version,
            "checksum": checksum,
        }

    def get_history(self, entity_id: str) -> list[dict]:
        """获取编辑历史。"""
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT * FROM collab_edits WHERE entity_id=? ORDER BY version DESC LIMIT 20",
            (entity_id,),
        ).fetchall()
        conn.close()
        cols = ["entity_id", "editor", "version", "content", "checksum", "edited_at"]
        return [dict(zip(cols, r, strict=True)) for r in rows]

    def _get_version(self, entity_id: str) -> int:
        conn = self._get_conn()
        row = conn.execute(
            "SELECT MAX(version) FROM collab_edits WHERE entity_id=?",
            (entity_id,),
        ).fetchone()
        conn.close()
        return row[0] if row and row[0] else 0


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "sync":
        ts = TaskSync()
        if sys.argv[2] == "change":
            r = ts.on_task_change(sys.argv[3], sys.argv[4], {"status": sys.argv[4]})
            print(f"Event recorded: v{r['version']}")
        elif sys.argv[2] == "history":
            for e in ts.get_history(sys.argv[3]):
                print(f"  v{e['version']} {e['event_type']}: {json.dumps(e['payload'])[:60]}")
        elif sys.argv[2] == "snapshot":
            s = ts.get_snapshot(sys.argv[3])
            print(f"Snapshot: v{s['version']}" if s else "No snapshot")
    elif len(sys.argv) > 1 and sys.argv[1] == "edit":
        ce = CollaborativeEdit()
        if sys.argv[2] == "begin":
            r = ce.begin_edit(sys.argv[3], sys.argv[4])
            print(f"Editing: v{r['version']}, content_len={len(r['content'])}")
        elif sys.argv[2] == "submit":
            r = ce.submit_edit(sys.argv[3], sys.argv[4], sys.argv[5], int(sys.argv[6]))
            print(f"Submit: {r['status']}")
    else:
        print("Usage: realtime.py [sync|edit] ...")
