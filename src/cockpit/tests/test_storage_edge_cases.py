"""storage 模块边缘情况测试 — not-found 分支、空值、ALTER TABLE 迁移。"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import cockpit.storage as storage

# ── not-found / 空值分支 ──


def test_set_research_tags_not_found(monkeypatch, tmp_path: Path):
    """set_research_tags 不存在的 ID → 返回空列表。"""
    monkeypatch.setattr(storage, "DB_PATH", tmp_path / "data.db")
    result = storage.set_research_tags(999, ["llm", "agents"])
    assert result == []


def test_rename_research_empty_title(monkeypatch, tmp_path: Path):
    """rename_research 空标题 → 返回 False。"""
    monkeypatch.setattr(storage, "DB_PATH", tmp_path / "data.db")
    rid = storage.save_research("original", "summary", "body", source_count=1)
    result = storage.rename_research(rid, "  ")
    assert result is False
    # Verify title unchanged
    record = storage.get_research(rid)
    assert record is not None
    assert record["topic"] == "original"


def test_rename_research_not_found(monkeypatch, tmp_path: Path):
    """rename_research 不存在的 ID → 返回 False。"""
    monkeypatch.setattr(storage, "DB_PATH", tmp_path / "data.db")
    result = storage.rename_research(999, "new title")
    assert result is False


def test_get_research_timeline_not_found(monkeypatch, tmp_path: Path):
    """get_research_timeline 不存在的 ID → 返回空列表。"""
    monkeypatch.setattr(storage, "DB_PATH", tmp_path / "data.db")
    result = storage.get_research_timeline(999)
    assert result == []


def test_get_research_dossier_not_found(monkeypatch, tmp_path: Path):
    """get_research_dossier 不存在的 ID → 返回 None。"""
    monkeypatch.setattr(storage, "DB_PATH", tmp_path / "data.db")
    result = storage.get_research_dossier(999)
    assert result is None


# ── 批量操作全缺失分支 ──


def test_quarantine_all_missing(monkeypatch, tmp_path: Path):
    """quarantine_research 全部 ID 不存在 → 全在 missing 列表。"""
    monkeypatch.setattr(storage, "DB_PATH", tmp_path / "data.db")
    quarantined, missing = storage.quarantine_research([1, 2], reason="test")
    assert quarantined == []
    assert missing == [1, 2]


def test_restore_all_missing(monkeypatch, tmp_path: Path):
    """restore_research 全部 ID 不存在 → 全在 missing 列表。"""
    monkeypatch.setattr(storage, "DB_PATH", tmp_path / "data.db")
    restored, missing = storage.restore_research([1, 2])
    assert restored == []
    assert missing == [1, 2]


def test_archive_all_missing(monkeypatch, tmp_path: Path):
    """archive_research 全部 ID 不存在 → 全在 missing 列表。"""
    monkeypatch.setattr(storage, "DB_PATH", tmp_path / "data.db")
    archived, missing = storage.archive_research([1, 2], reason="test")
    assert archived == []
    assert missing == [1, 2]


def test_restore_archived_all_missing(monkeypatch, tmp_path: Path):
    """restore_archived_research 全部 ID 不存在 → 全在 missing 列表。"""
    monkeypatch.setattr(storage, "DB_PATH", tmp_path / "data.db")
    restored, missing = storage.restore_archived_research([1, 2])
    assert restored == []
    assert missing == [1, 2]


# ── ALTER TABLE 迁移 ──


def test_ensure_db_alter_table_migration(monkeypatch, tmp_path: Path):
    """_ensure_db 旧表缺少字段 → ALTER TABLE 补充。

    创建一个没有全字段的旧表，调用 _ensure_db 后验证列已补充。
    """
    db_path = tmp_path / "data.db"
    monkeypatch.setattr(storage, "DB_PATH", db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    # 创建旧版 DB — 只有 id/topic/summary/created_at
    conn = sqlite3.connect(str(db_path))
    conn.execute("""
        CREATE TABLE research (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            topic TEXT NOT NULL,
            summary TEXT,
            created_at REAL NOT NULL
        )
    """)
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
    conn.commit()
    conn.close()

    # 验证旧表缺少字段
    conn2 = sqlite3.connect(str(db_path))
    cols = {row[1] for row in conn2.execute("PRAGMA table_info(research)").fetchall()}
    conn2.close()
    assert "full_text" not in cols
    assert "tags" not in cols
    assert "archived_at" not in cols
    assert "archive_reason" not in cols
    assert "quarantined_at" not in cols
    assert "quarantine_reason" not in cols
    assert "agent" not in cols

    # 触发 _ensure_db
    da = storage.get_data_access()
    da._ensure_db()

    # 验证字段已补充
    conn3 = sqlite3.connect(str(db_path))
    new_cols = {row[1] for row in conn3.execute("PRAGMA table_info(research)").fetchall()}
    conn3.close()
    assert "full_text" in new_cols
    assert "tags" in new_cols
    assert "archived_at" in new_cols
    assert "archive_reason" in new_cols
    assert "quarantined_at" in new_cols
    assert "quarantine_reason" in new_cols
    assert "agent" in new_cols


# ── 模块级工具函数 ──


def test_normalize_tags_direct():
    """直接调用 storage._normalize_tags 的覆盖补齐。

    该函数是模块级委托函数，不经过 SQLiteDataAccess，需要直接覆盖测试。
    """
    # Strip whitespace, lowercase, and deduplicate
    result = storage._normalize_tags(["  AI  ", "AI", "ML", "  ML  "])
    assert result == ["ai", "ml"]

    # Empty input
    result2 = storage._normalize_tags([])
    assert result2 == []

    # Single element
    result3 = storage._normalize_tags(["single"])
    assert result3 == ["single"]
