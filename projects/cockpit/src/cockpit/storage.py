"""SQLite 持久化存储 — 研究结果、用户状态、系统历史。

IDataAccess Protocol 接口层支持 SQLite 和未来 MCP/HTTP 后端切换。
"""

import json
import sqlite3
import time
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

DB_PATH = Path.home() / ".workspace" / "data.db"


# ──────────────────────────────────────────────────────────────────────
# W011: IDataAccess Protocol
# ──────────────────────────────────────────────────────────────────────


@runtime_checkable
class IDataAccess(Protocol):
    """数据访问层接口 — 支持 SQLite 和未来 MCP/HTTP 后端。"""

    def save_research(
        self,
        topic: str,
        summary: str,
        full_text: str = "",
        source_count: int = 0,
        agent: str = "",
    ) -> int: ...

    def add_follow_up(self, research_id: int, question: str, answer: str) -> None: ...

    def list_research(
        self,
        limit: int = 10,
        include_quarantined: bool = False,
        include_archived: bool = False,
    ) -> list[dict[str, Any]]: ...

    def search_research(self, keyword: str, limit: int = 10) -> list[dict[str, Any]]: ...

    def get_research(self, research_id: int) -> dict[str, Any] | None: ...

    def set_research_tags(self, research_id: int, tags: list[str]) -> list[str]: ...

    def rename_research(self, research_id: int, new_topic: str) -> bool: ...

    def quarantine_research(
        self,
        research_ids: list[int],
        reason: str = "manual quarantine",
    ) -> tuple[list[int], list[int]]: ...

    def restore_research(self, research_ids: list[int]) -> tuple[list[int], list[int]]: ...

    def archive_research(
        self,
        research_ids: list[int],
        reason: str = "manual archive",
    ) -> tuple[list[int], list[int]]: ...

    def restore_archived_research(self, research_ids: list[int]) -> tuple[list[int], list[int]]: ...

    def add_research_relations(
        self,
        parent_ids: list[int],
        child_id: int,
        relation_type: str,
    ) -> None: ...

    def save_published_report(self, research_id: int, style: str, output_path: str) -> int: ...

    def get_research_timeline(self, research_id: int) -> list[dict[str, Any]]: ...

    def get_research_dossier(self, research_id: int) -> dict[str, Any] | None: ...

    def set_research_agent(self, research_id: int, agent_name: str) -> bool: ...

    def compute_half_life(self, research_id: int) -> dict[str, Any]: ...

    def export_backup(self) -> dict[str, Any]: ...

    def import_backup(self, data: dict[str, Any]) -> dict[str, int]: ...


# ──────────────────────────────────────────────────────────────────────
# W012: SQLiteDataAccess 实现
# ──────────────────────────────────────────────────────────────────────


class SQLiteDataAccess:
    """基于 SQLite 的完整数据访问实现。方法体从模块级函数移植而来。"""

    # ── helpers ──────────────────────────────────────────────────────

    def _ensure_db(self) -> None:
        """Create database and tables if they don't exist."""
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(DB_PATH))
        conn.execute("""
            CREATE TABLE IF NOT EXISTS research (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                topic TEXT NOT NULL,
                summary TEXT,
                full_text TEXT,
                created_at REAL NOT NULL,
                source_count INTEGER DEFAULT 0,
                follow_ups TEXT DEFAULT '[]',
                tags TEXT DEFAULT '[]',
                archived_at REAL,
                archive_reason TEXT,
                quarantined_at REAL,
                quarantine_reason TEXT
            )
        """)

        existing_columns = {row[1] for row in conn.execute("PRAGMA table_info(research)").fetchall()}
        if "full_text" not in existing_columns:
            conn.execute("ALTER TABLE research ADD COLUMN full_text TEXT DEFAULT ''")
        if "tags" not in existing_columns:
            conn.execute("ALTER TABLE research ADD COLUMN tags TEXT DEFAULT '[]'")
        if "archived_at" not in existing_columns:
            conn.execute("ALTER TABLE research ADD COLUMN archived_at REAL")
        if "archive_reason" not in existing_columns:
            conn.execute("ALTER TABLE research ADD COLUMN archive_reason TEXT")
        if "quarantined_at" not in existing_columns:
            conn.execute("ALTER TABLE research ADD COLUMN quarantined_at REAL")
        if "quarantine_reason" not in existing_columns:
            conn.execute("ALTER TABLE research ADD COLUMN quarantine_reason TEXT")
        if "agent" not in existing_columns:
            conn.execute("ALTER TABLE research ADD COLUMN agent TEXT DEFAULT ''")

        conn.execute("""
            CREATE TABLE IF NOT EXISTS research_relations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                parent_id INTEGER NOT NULL,
                child_id INTEGER NOT NULL,
                relation_type TEXT NOT NULL,
                created_at REAL NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS published_reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                research_id INTEGER NOT NULL,
                style TEXT NOT NULL,
                output_path TEXT NOT NULL,
                published_at REAL NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS research_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                research_id INTEGER NOT NULL,
                event_type TEXT NOT NULL,
                description TEXT NOT NULL,
                created_at REAL NOT NULL
            )
        """)
        conn.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS research_fts USING fts5(
                topic, summary, full_text, content='research', content_rowid='id'
            )
        """)
        conn.execute("""
            CREATE TRIGGER IF NOT EXISTS research_ai AFTER INSERT ON research BEGIN
                INSERT INTO research_fts(rowid, topic, summary, full_text) VALUES (new.id, new.topic, new.summary, new.full_text);
            END;
        """)
        conn.execute("""
            CREATE TRIGGER IF NOT EXISTS research_au AFTER UPDATE ON research BEGIN
                INSERT INTO research_fts(research_fts, rowid, topic, summary, full_text) VALUES('delete', old.id, old.topic, old.summary, old.full_text);
                INSERT INTO research_fts(rowid, topic, summary, full_text) VALUES (new.id, new.topic, new.summary, new.full_text);
            END;
        """)
        conn.commit()
        conn.close()

    @staticmethod
    def _normalize_tags(tags: list[str]) -> list[str]:
        values = sorted({tag.strip().lower() for tag in tags if tag and tag.strip()})
        return values

    # ── public API ───────────────────────────────────────────────────

    def save_research(
        self,
        topic: str,
        summary: str,
        full_text: str = "",
        source_count: int = 0,
        agent: str = "",
    ) -> int:
        self._ensure_db()
        conn = sqlite3.connect(str(DB_PATH))
        conn.execute(
            "INSERT INTO research (topic, summary, full_text, created_at, source_count, agent) VALUES (?, ?, ?, ?, ?, ?)",
            (topic, summary, full_text, time.time(), source_count, agent),
        )
        conn.commit()
        row_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.close()
        return row_id

    def add_follow_up(self, research_id: int, question: str, answer: str) -> None:
        """Store a follow-up question and answer for a research record."""
        self._ensure_db()
        conn = sqlite3.connect(str(DB_PATH))
        row = conn.execute("SELECT follow_ups FROM research WHERE id = ?", (research_id,)).fetchone()
        if row is None:
            conn.close()
            return
        existing = json.loads(row[0]) if row[0] else []
        existing.append({"question": question, "answer": answer, "timestamp": time.time()})
        conn.execute("UPDATE research SET follow_ups = ? WHERE id = ?", (json.dumps(existing), research_id))
        conn.commit()
        conn.close()

    def list_research(
        self,
        limit: int = 10,
        include_quarantined: bool = False,
        include_archived: bool = False,
    ) -> list[dict[str, Any]]:
        self._ensure_db()
        conn = sqlite3.connect(str(DB_PATH))
        conn.row_factory = sqlite3.Row
        query = "SELECT id, topic, summary, created_at, source_count, tags, archived_at, archive_reason, quarantined_at, quarantine_reason, agent FROM research"
        filters: list[str] = []
        if not include_quarantined:
            filters.append("quarantined_at IS NULL")
        if not include_archived:
            filters.append("archived_at IS NULL")
        if filters:
            query += " WHERE " + " AND ".join(filters)
        query += " ORDER BY created_at DESC LIMIT ?"
        params: tuple[Any, ...] = (limit,)
        rows = conn.execute(query, params).fetchall()
        conn.close()
        results = [dict(r) for r in rows]
        for item in results:
            item["tags"] = json.loads(item.get("tags", "[]"))
        return results

    def search_research(self, keyword: str, limit: int = 10) -> list[dict[str, Any]]:
        self._ensure_db()
        conn = sqlite3.connect(str(DB_PATH))
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT r.id, r.topic, r.summary, r.created_at, r.source_count, r.tags, r.archived_at, r.archive_reason, r.quarantined_at, r.quarantine_reason, r.agent, "
            "snippet(research_fts, 1, '<mark>', '</mark>', '...', 40) as snippet "
            "FROM research_fts f JOIN research r ON f.rowid = r.id "
            "WHERE research_fts MATCH ? AND r.quarantined_at IS NULL AND r.archived_at IS NULL ORDER BY bm25(research_fts, 0, 10.0, 5.0) LIMIT ?",
            (keyword, limit),
        ).fetchall()
        conn.close()
        results = [dict(r) for r in rows]
        for item in results:
            item["tags"] = json.loads(item.get("tags", "[]"))
        return results

    def get_research(self, research_id: int) -> dict[str, Any] | None:
        self._ensure_db()
        conn = sqlite3.connect(str(DB_PATH))
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT id, topic, summary, full_text, created_at, source_count, follow_ups, tags, archived_at, archive_reason, quarantined_at, quarantine_reason, agent FROM research WHERE id = ?",
            (research_id,),
        ).fetchone()
        conn.close()
        if row:
            result = dict(row)
            result["follow_ups"] = json.loads(result.get("follow_ups", "[]"))
            result["tags"] = json.loads(result.get("tags", "[]"))
            return result
        return None

    def set_research_tags(self, research_id: int, tags: list[str]) -> list[str]:
        self._ensure_db()
        normalized = self._normalize_tags(tags)
        conn = sqlite3.connect(str(DB_PATH))
        row = conn.execute("SELECT id FROM research WHERE id = ?", (research_id,)).fetchone()
        if row is None:
            conn.close()
            return []
        conn.execute("UPDATE research SET tags = ? WHERE id = ?", (json.dumps(normalized), research_id))
        conn.execute(
            "INSERT INTO research_events (research_id, event_type, description, created_at) VALUES (?, ?, ?, ?)",
            (research_id, "tagged", f"标签更新: {', '.join(normalized)}", time.time()),
        )
        conn.commit()
        conn.close()
        return normalized

    def rename_research(self, research_id: int, new_topic: str) -> bool:
        self._ensure_db()
        new_value = new_topic.strip()
        if not new_value:
            return False
        conn = sqlite3.connect(str(DB_PATH))
        row = conn.execute("SELECT topic FROM research WHERE id = ?", (research_id,)).fetchone()
        if row is None:
            conn.close()
            return False
        old_topic = str(row[0])
        conn.execute("UPDATE research SET topic = ? WHERE id = ?", (new_value, research_id))
        conn.execute(
            "INSERT INTO research_events (research_id, event_type, description, created_at) VALUES (?, ?, ?, ?)",
            (research_id, "renamed", f"标题从 '{old_topic}' 改为 '{new_value}'", time.time()),
        )
        conn.commit()
        conn.close()
        return True

    def quarantine_research(
        self,
        research_ids: list[int],
        reason: str = "manual quarantine",
    ) -> tuple[list[int], list[int]]:
        self._ensure_db()
        conn = sqlite3.connect(str(DB_PATH))
        quarantined: list[int] = []
        missing: list[int] = []

        for research_id in research_ids:
            row = conn.execute("SELECT id FROM research WHERE id = ?", (research_id,)).fetchone()
            if row is None:
                missing.append(research_id)
                continue
            quarantined_at = time.time()
            conn.execute(
                "UPDATE research SET quarantined_at = ?, quarantine_reason = ? WHERE id = ?",
                (quarantined_at, reason, research_id),
            )
            conn.execute(
                "INSERT INTO research_events (research_id, event_type, description, created_at) VALUES (?, ?, ?, ?)",
                (research_id, "quarantined", f"隔离原因: {reason}", quarantined_at),
            )
            quarantined.append(research_id)

        conn.commit()
        conn.close()
        return quarantined, missing

    def restore_research(self, research_ids: list[int]) -> tuple[list[int], list[int]]:
        self._ensure_db()
        conn = sqlite3.connect(str(DB_PATH))
        restored: list[int] = []
        missing: list[int] = []

        for research_id in research_ids:
            row = conn.execute("SELECT id FROM research WHERE id = ?", (research_id,)).fetchone()
            if row is None:
                missing.append(research_id)
                continue
            restored_at = time.time()
            conn.execute(
                "UPDATE research SET quarantined_at = NULL, quarantine_reason = NULL WHERE id = ?",
                (research_id,),
            )
            conn.execute(
                "INSERT INTO research_events (research_id, event_type, description, created_at) VALUES (?, ?, ?, ?)",
                (research_id, "restored", "恢复到默认工作流", restored_at),
            )
            restored.append(research_id)

        conn.commit()
        conn.close()
        return restored, missing

    def archive_research(
        self,
        research_ids: list[int],
        reason: str = "manual archive",
    ) -> tuple[list[int], list[int]]:
        self._ensure_db()
        conn = sqlite3.connect(str(DB_PATH))
        archived: list[int] = []
        missing: list[int] = []
        for research_id in research_ids:
            row = conn.execute("SELECT id FROM research WHERE id = ?", (research_id,)).fetchone()
            if row is None:
                missing.append(research_id)
                continue
            archived_at = time.time()
            conn.execute(
                "UPDATE research SET archived_at = ?, archive_reason = ? WHERE id = ?",
                (archived_at, reason, research_id),
            )
            conn.execute(
                "INSERT INTO research_events (research_id, event_type, description, created_at) VALUES (?, ?, ?, ?)",
                (research_id, "archived", f"归档原因: {reason}", archived_at),
            )
            archived.append(research_id)
        conn.commit()
        conn.close()
        return archived, missing

    def restore_archived_research(self, research_ids: list[int]) -> tuple[list[int], list[int]]:
        self._ensure_db()
        conn = sqlite3.connect(str(DB_PATH))
        restored: list[int] = []
        missing: list[int] = []
        for research_id in research_ids:
            row = conn.execute("SELECT id FROM research WHERE id = ?", (research_id,)).fetchone()
            if row is None:
                missing.append(research_id)
                continue
            restored_at = time.time()
            conn.execute(
                "UPDATE research SET archived_at = NULL, archive_reason = NULL WHERE id = ?",
                (research_id,),
            )
            conn.execute(
                "INSERT INTO research_events (research_id, event_type, description, created_at) VALUES (?, ?, ?, ?)",
                (research_id, "unarchived", "恢复归档研究", restored_at),
            )
            restored.append(research_id)
        conn.commit()
        conn.close()
        return restored, missing

    def add_research_relations(self, parent_ids: list[int], child_id: int, relation_type: str) -> None:
        self._ensure_db()
        conn = sqlite3.connect(str(DB_PATH))
        for parent_id in parent_ids:
            conn.execute(
                "INSERT INTO research_relations (parent_id, child_id, relation_type, created_at) VALUES (?, ?, ?, ?)",
                (parent_id, child_id, relation_type, time.time()),
            )
        conn.commit()
        conn.close()

    def save_published_report(self, research_id: int, style: str, output_path: str) -> int:
        self._ensure_db()
        conn = sqlite3.connect(str(DB_PATH))
        published_at = time.time()
        conn.execute(
            "INSERT INTO published_reports (research_id, style, output_path, published_at) VALUES (?, ?, ?, ?)",
            (research_id, style, output_path, published_at),
        )
        conn.execute(
            "INSERT INTO research_events (research_id, event_type, description, created_at) VALUES (?, ?, ?, ?)",
            (research_id, "published", f"发布为 {style}: {output_path}", published_at),
        )
        conn.commit()
        row_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.close()
        return row_id

    def get_research_timeline(self, research_id: int) -> list[dict[str, Any]]:
        self._ensure_db()
        record = self.get_research(research_id)
        if record is None:
            return []

        conn = sqlite3.connect(str(DB_PATH))
        conn.row_factory = sqlite3.Row
        relations = conn.execute(
            "SELECT parent_id, relation_type, created_at FROM research_relations WHERE child_id = ? ORDER BY created_at ASC",
            (research_id,),
        ).fetchall()
        events = conn.execute(
            "SELECT event_type, description, created_at FROM research_events WHERE research_id = ? ORDER BY created_at ASC",
            (research_id,),
        ).fetchall()
        conn.close()

        timeline: list[dict[str, Any]] = [
            {
                "event_type": "created",
                "created_at": float(record["created_at"]),
                "description": "研究创建",
            }
        ]

        grouped_relations: dict[tuple[float, str], list[int]] = {}
        for rel in relations:
            key = (float(rel["created_at"]), str(rel["relation_type"]))
            grouped_relations.setdefault(key, []).append(int(rel["parent_id"]))
        for (created_at, relation_type), parent_ids in grouped_relations.items():
            timeline.append(
                {
                    "event_type": "derived_from",
                    "created_at": created_at,
                    "description": f"由 {','.join(str(parent_id) for parent_id in parent_ids)} 派生 ({relation_type})",
                }
            )

        timeline.extend(dict(row) for row in events)
        return sorted(timeline, key=lambda item: float(item["created_at"]))

    def get_research_dossier(self, research_id: int) -> dict[str, Any] | None:
        self._ensure_db()
        record = self.get_research(research_id)
        if record is None:
            return None

        conn = sqlite3.connect(str(DB_PATH))
        conn.row_factory = sqlite3.Row
        parents = conn.execute(
            "SELECT r.id, r.topic, rel.relation_type "
            "FROM research_relations rel JOIN research r ON rel.parent_id = r.id "
            "WHERE rel.child_id = ? ORDER BY rel.created_at ASC",
            (research_id,),
        ).fetchall()
        children = conn.execute(
            "SELECT r.id, r.topic, rel.relation_type "
            "FROM research_relations rel JOIN research r ON rel.child_id = r.id "
            "WHERE rel.parent_id = ? ORDER BY rel.created_at ASC",
            (research_id,),
        ).fetchall()
        publications = conn.execute(
            "SELECT style, output_path, published_at FROM published_reports WHERE research_id = ? ORDER BY published_at DESC",
            (research_id,),
        ).fetchall()
        conn.close()

        return {
            "record": record,
            "parents": [dict(row) for row in parents],
            "children": [dict(row) for row in children],
            "publications": [dict(row) for row in publications],
        }

    def set_research_agent(self, research_id: int, agent_name: str) -> bool:
        """标记研究记录的处理 Agent。"""
        self._ensure_db()
        conn = sqlite3.connect(str(DB_PATH))
        row = conn.execute("SELECT id FROM research WHERE id = ?", (research_id,)).fetchone()
        if row is None:
            conn.close()
            return False
        conn.execute("UPDATE research SET agent = ? WHERE id = ?", (agent_name, research_id))
        conn.execute(
            "INSERT INTO research_events (research_id, event_type, description, created_at) VALUES (?, ?, ?, ?)",
            (research_id, "agent_assigned", f"处理 Agent 标记为: {agent_name}", time.time()),
        )
        conn.commit()
        conn.close()
        return True

    def compute_half_life(self, research_id: int) -> dict[str, Any]:
        """计算研究的半衰期衰减值。

        半衰期公式: decay = 2^(-days_since_last_active / half_life_days)
        其中 half_life_days = 14 天（默认），last_active = 最后事件时间
        """
        record = self.get_research(research_id)
        if record is None:
            return {"decay": 0.0, "half_life_days": 14, "days_since_active": 999}

        timeline = self.get_research_timeline(research_id)
        last_active = max((float(item["created_at"]) for item in timeline), default=float(record["created_at"]))

        days_since = (time.time() - last_active) / 86400
        half_life = 14  # 14 天半衰期
        decay = 2 ** (-days_since / half_life)

        # 追问频率调整: 有追问的衰减慢 20%
        fups = record.get("follow_ups", [])
        if isinstance(fups, list) and len(fups) > 0:
            decay = min(1.0, decay * 1.2)

        # 发布记录调高衰减
        published_count = 0
        for item in timeline:
            if item.get("event_type") == "published":
                published_count += 1
        if published_count > 0:
            decay = min(1.0, decay * (1 + 0.1 * min(published_count, 5)))

        return {
            "decay": round(decay, 4),
            "half_life_days": half_life,
            "days_since_active": round(days_since, 1),
            "follow_up_count": len(fups) if isinstance(fups, list) else 0,
            "published_count": published_count,
        }

    def export_backup(self) -> dict[str, Any]:
        """全量导出所有数据为可序列化字典。"""
        self._ensure_db()
        conn = sqlite3.connect(str(DB_PATH))
        conn.row_factory = sqlite3.Row

        # 导出 research（含 follow_ups/tags 反序列化）
        rows = conn.execute("SELECT * FROM research ORDER BY id").fetchall()
        research_list = []
        for r in rows:
            item = dict(r)
            item["follow_ups"] = json.loads(item.get("follow_ups", "[]"))
            item["tags"] = json.loads(item.get("tags", "[]"))
            research_list.append(item)

        relations = [dict(r) for r in conn.execute("SELECT * FROM research_relations ORDER BY id").fetchall()]
        published_reports = [dict(r) for r in conn.execute("SELECT * FROM published_reports ORDER BY id").fetchall()]
        events = [dict(r) for r in conn.execute("SELECT * FROM research_events ORDER BY id").fetchall()]

        conn.close()

        return {
            "version": 1,
            "exported_at": time.time(),
            "research": research_list,
            "relations": relations,
            "published_reports": published_reports,
            "events": events,
        }

    def import_backup(self, data: dict[str, Any]) -> dict[str, int]:
        """从备份字典导入数据。返回导入统计。"""
        self._ensure_db()
        conn = sqlite3.connect(str(DB_PATH))

        id_map: dict[int, int] = {}  # old_id -> new_id
        imported = {"research": 0, "relations": 0, "published_reports": 0, "events": 0}
        skipped = {"research": 0}

        for r in data.get("research", []):
            old_id = r["id"]
            # 检查是否已存在（按 topic + created_at 判断重复）
            existing = conn.execute(
                "SELECT id FROM research WHERE topic = ? AND created_at = ?",
                (r["topic"], r["created_at"]),
            ).fetchone()
            if existing is not None:
                id_map[old_id] = existing[0]
                skipped["research"] += 1
                continue

            follow_ups_str = json.dumps(r.get("follow_ups", []), ensure_ascii=False)
            tags_str = json.dumps(r.get("tags", []), ensure_ascii=False)
            conn.execute(
                "INSERT INTO research (topic, summary, full_text, created_at, source_count, follow_ups, tags, archived_at, archive_reason, quarantined_at, quarantine_reason, agent) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    r["topic"],
                    r.get("summary", ""),
                    r.get("full_text", ""),
                    r["created_at"],
                    r.get("source_count", 0),
                    follow_ups_str,
                    tags_str,
                    r.get("archived_at"),
                    r.get("archive_reason"),
                    r.get("quarantined_at"),
                    r.get("quarantine_reason"),
                    r.get("agent", ""),
                ),
            )
            new_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            id_map[old_id] = new_id
            imported["research"] += 1

        for rel in data.get("relations", []):
            parent_new = id_map.get(rel["parent_id"])
            child_new = id_map.get(rel["child_id"])
            if parent_new is None or child_new is None:
                continue  # 父/子研究未被导入，跳过
            conn.execute(
                "INSERT INTO research_relations (parent_id, child_id, relation_type, created_at) VALUES (?, ?, ?, ?)",
                (parent_new, child_new, rel["relation_type"], rel["created_at"]),
            )
            imported["relations"] += 1

        for pr in data.get("published_reports", []):
            r_new = id_map.get(pr["research_id"])
            if r_new is None:
                continue
            conn.execute(
                "INSERT INTO published_reports (research_id, style, output_path, published_at) VALUES (?, ?, ?, ?)",
                (r_new, pr["style"], pr["output_path"], pr["published_at"]),
            )
            imported["published_reports"] += 1

        for ev in data.get("events", []):
            r_new = id_map.get(ev["research_id"])
            if r_new is None:
                continue
            conn.execute(
                "INSERT INTO research_events (research_id, event_type, description, created_at) VALUES (?, ?, ?, ?)",
                (r_new, ev["event_type"], ev["description"], ev["created_at"]),
            )
            imported["events"] += 1

        conn.commit()
        conn.close()

        imported["skipped"] = skipped["research"]
        return imported


# ──────────────────────────────────────────────────────────────────────
# W013: 全局 accessor
# ──────────────────────────────────────────────────────────────────────

_DATA_ACCESS: IDataAccess | None = None


def get_data_access() -> IDataAccess:
    global _DATA_ACCESS
    if _DATA_ACCESS is None:
        _DATA_ACCESS = SQLiteDataAccess()
    return _DATA_ACCESS


def set_data_access(accessor: IDataAccess) -> None:
    """测试用：注入 mock 实现。"""
    global _DATA_ACCESS
    _DATA_ACCESS = accessor


# ──────────────────────────────────────────────────────────────────────
# 向后兼容 shim：模块级函数委托到全局 accessor
# ──────────────────────────────────────────────────────────────────────


def save_research(topic: str, summary: str, full_text: str = "", source_count: int = 0, agent: str = "") -> int:
    return get_data_access().save_research(topic, summary, full_text, source_count, agent)


def add_follow_up(research_id: int, question: str, answer: str) -> None:
    return get_data_access().add_follow_up(research_id, question, answer)


def list_research(
    limit: int = 10, include_quarantined: bool = False, include_archived: bool = False
) -> list[dict[str, Any]]:
    return get_data_access().list_research(limit, include_quarantined, include_archived)


def search_research(keyword: str, limit: int = 10) -> list[dict[str, Any]]:
    return get_data_access().search_research(keyword, limit)


def get_research(research_id: int) -> dict[str, Any] | None:
    return get_data_access().get_research(research_id)


def _normalize_tags(tags: list[str]) -> list[str]:
    return SQLiteDataAccess._normalize_tags(tags)


def set_research_tags(research_id: int, tags: list[str]) -> list[str]:
    return get_data_access().set_research_tags(research_id, tags)


def rename_research(research_id: int, new_topic: str) -> bool:
    return get_data_access().rename_research(research_id, new_topic)


def quarantine_research(research_ids: list[int], reason: str = "manual quarantine") -> tuple[list[int], list[int]]:
    return get_data_access().quarantine_research(research_ids, reason)


def restore_research(research_ids: list[int]) -> tuple[list[int], list[int]]:
    return get_data_access().restore_research(research_ids)


def archive_research(research_ids: list[int], reason: str = "manual archive") -> tuple[list[int], list[int]]:
    return get_data_access().archive_research(research_ids, reason)


def restore_archived_research(research_ids: list[int]) -> tuple[list[int], list[int]]:
    return get_data_access().restore_archived_research(research_ids)


def add_research_relations(parent_ids: list[int], child_id: int, relation_type: str) -> None:
    return get_data_access().add_research_relations(parent_ids, child_id, relation_type)


def save_published_report(research_id: int, style: str, output_path: str) -> int:
    return get_data_access().save_published_report(research_id, style, output_path)


def get_research_timeline(research_id: int) -> list[dict[str, Any]]:
    return get_data_access().get_research_timeline(research_id)


def get_research_dossier(research_id: int) -> dict[str, Any] | None:
    return get_data_access().get_research_dossier(research_id)


def set_research_agent(research_id: int, agent_name: str) -> bool:
    return get_data_access().set_research_agent(research_id, agent_name)


def compute_half_life(research_id: int) -> dict[str, Any]:
    return get_data_access().compute_half_life(research_id)


def export_backup() -> dict[str, Any]:
    return get_data_access().export_backup()


def import_backup(data: dict[str, Any]) -> dict[str, int]:
    return get_data_access().import_backup(data)
