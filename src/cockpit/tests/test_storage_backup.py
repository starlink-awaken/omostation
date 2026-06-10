"""Storage 层备份/恢复 (export_backup / import_backup) 单元测试。"""

from __future__ import annotations

import time

import pytest

from cockpit.storage import SQLiteDataAccess


@pytest.fixture
def da(tmp_path, monkeypatch):
    """使用 tmp_path 的 SQLiteDataAccess 实例。"""
    db_path = tmp_path / ".workspace" / "data.db"
    monkeypatch.setattr("cockpit.storage.DB_PATH", db_path)
    sda = SQLiteDataAccess()
    sda._ensure_db()
    yield sda


# ═══════════════════════════════════════════════════════════════════════════════
# export_backup — 4 条路径
# ═══════════════════════════════════════════════════════════════════════════════


class TestExportBackup:
    def test_empty_db(self, da):
        """空数据库 → 返回包含空列表的 dict"""
        result = da.export_backup()
        assert isinstance(result, dict)
        assert result["version"] == 1
        assert result["research"] == []
        assert result["relations"] == []
        assert result["published_reports"] == []
        assert result["events"] == []
        assert "exported_at" in result

    def test_with_research(self, da):
        """有研究记录 → research 列表包含反序列化后的数据"""
        rid = da.save_research("测试主题", "摘要内容", "完整内容", source_count=3)
        result = da.export_backup()
        assert len(result["research"]) == 1
        r = result["research"][0]
        assert r["id"] == rid
        assert r["topic"] == "测试主题"
        assert r["summary"] == "摘要内容"
        assert r["full_text"] == "完整内容"
        assert r["source_count"] == 3
        assert r["follow_ups"] == []  # 已反序列化
        assert r["tags"] == []  # 已反序列化

    def test_with_follow_ups_and_tags(self, da):
        """含追问和标签 → follow_ups/tags 是反序列化后的列表"""
        rid = da.save_research("标签测试", "summary")
        da.add_follow_up(rid, "问题?", "回答!")
        da.set_research_tags(rid, ["tag1", "tag2"])
        result = da.export_backup()
        r = result["research"][0]
        assert isinstance(r["follow_ups"], list)
        assert len(r["follow_ups"]) == 1
        assert r["follow_ups"][0]["question"] == "问题?"
        assert isinstance(r["tags"], list)
        assert "tag1" in r["tags"]

    def test_with_relations_reports_events(self, da):
        """含关系/发布/事件 → 所有表数据正确导出"""
        r1 = da.save_research("源研究", "src")
        r2 = da.save_research("派生研究", "derived")
        da.add_research_relations([r1], r2, "derived_from")
        da.save_published_report(r2, "brief", "/tmp/test.md")
        # set_tags 和 save 都会产生事件

        result = da.export_backup()
        assert len(result["relations"]) == 1
        assert len(result["published_reports"]) == 1
        assert len(result["events"]) >= 1  # 至少创建事件（publish）


# ═══════════════════════════════════════════════════════════════════════════════
# import_backup — 5 条路径
# ═══════════════════════════════════════════════════════════════════════════════


class TestImportBackup:
    def test_import_empty(self, da):
        """空备份 → 全部 0"""
        stats = da.import_backup({"version": 1, "research": [], "relations": [], "published_reports": [], "events": []})
        assert stats["research"] == 0
        assert stats["relations"] == 0
        assert stats["published_reports"] == 0
        assert stats["events"] == 0
        assert stats["skipped"] == 0

    def test_import_single_research(self, da):
        """单条研究导入 → 成功导入"""
        data = {
            "version": 1,
            "exported_at": time.time(),
            "research": [
                {
                    "id": 1,
                    "topic": "导入研究",
                    "summary": "导入摘要",
                    "full_text": "导入全文",
                    "created_at": time.time(),
                    "source_count": 2,
                    "follow_ups": [],
                    "tags": ["imported"],
                    "archived_at": None,
                    "archive_reason": None,
                    "quarantined_at": None,
                    "quarantine_reason": None,
                    "agent": "test",
                }
            ],
            "relations": [],
            "published_reports": [],
            "events": [],
        }
        stats = da.import_backup(data)
        assert stats["research"] == 1
        assert stats["skipped"] == 0

        # 验证数据正确写入
        from cockpit.storage import get_data_access

        record = get_data_access().list_research(limit=10, include_archived=True)
        assert len(record) == 1
        assert record[0]["topic"] == "导入研究"

    def test_import_skips_duplicate(self, da, tmp_path, monkeypatch):
        """重复数据（同 topic+created_at）→ 跳过"""
        now = time.time()
        da.save_research("已有研究", "已有摘要")
        # 通过 SQL 设置 created_at 为固定值
        import sqlite3

        db_path = tmp_path / ".workspace" / "data.db"
        monkeypatch.setattr("cockpit.storage.DB_PATH", db_path)
        conn = sqlite3.connect(str(db_path))
        conn.execute("UPDATE research SET created_at = ? WHERE topic = ?", (now, "已有研究"))
        conn.commit()
        conn.close()

        data = {
            "version": 1,
            "exported_at": time.time(),
            "research": [
                {
                    "id": 1,
                    "topic": "已有研究",
                    "summary": "已有摘要",
                    "full_text": "",
                    "created_at": now,
                    "source_count": 0,
                    "follow_ups": [],
                    "tags": [],
                    "archived_at": None,
                    "archive_reason": None,
                    "quarantined_at": None,
                    "quarantine_reason": None,
                    "agent": "",
                },
                {
                    "id": 2,
                    "topic": "新研究",
                    "summary": "新摘要",
                    "full_text": "",
                    "created_at": time.time(),
                    "source_count": 0,
                    "follow_ups": [],
                    "tags": [],
                    "archived_at": None,
                    "archive_reason": None,
                    "quarantined_at": None,
                    "quarantine_reason": None,
                    "agent": "",
                },
            ],
            "relations": [],
            "published_reports": [],
            "events": [],
        }
        stats = da.import_backup(data)
        assert stats["research"] == 1  # 只导入新记录
        assert stats["skipped"] == 1  # 跳过已有记录

    def test_import_with_relations(self, da):
        """含关系的数据导入 → 关系正确映射"""
        ts = time.time()
        data = {
            "version": 1,
            "exported_at": ts,
            "research": [
                {
                    "id": 10,
                    "topic": "父研究",
                    "summary": "",
                    "full_text": "",
                    "created_at": ts,
                    "source_count": 0,
                    "follow_ups": [],
                    "tags": [],
                    "archived_at": None,
                    "archive_reason": None,
                    "quarantined_at": None,
                    "quarantine_reason": None,
                    "agent": "",
                },
                {
                    "id": 20,
                    "topic": "子研究",
                    "summary": "",
                    "full_text": "",
                    "created_at": ts + 1,
                    "source_count": 0,
                    "follow_ups": [],
                    "tags": [],
                    "archived_at": None,
                    "archive_reason": None,
                    "quarantined_at": None,
                    "quarantine_reason": None,
                    "agent": "",
                },
            ],
            "relations": [
                {"id": 1, "parent_id": 10, "child_id": 20, "relation_type": "derived_from", "created_at": ts},
            ],
            "published_reports": [],
            "events": [],
        }
        stats = da.import_backup(data)
        assert stats["research"] == 2
        assert stats["relations"] == 1

    def test_import_with_events_and_reports(self, da):
        """含事件和发布的数据 → 全部正确导入"""
        ts = time.time()
        data = {
            "version": 1,
            "exported_at": ts,
            "research": [
                {
                    "id": 30,
                    "topic": "测试研究",
                    "summary": "摘要",
                    "full_text": "",
                    "created_at": ts,
                    "source_count": 1,
                    "follow_ups": [],
                    "tags": [],
                    "archived_at": None,
                    "archive_reason": None,
                    "quarantined_at": None,
                    "quarantine_reason": None,
                    "agent": "",
                },
            ],
            "relations": [],
            "published_reports": [
                {"id": 1, "research_id": 30, "style": "brief", "output_path": "/tmp/test.md", "published_at": ts},
            ],
            "events": [
                {"id": 1, "research_id": 30, "event_type": "created", "description": "研究创建", "created_at": ts},
            ],
        }
        stats = da.import_backup(data)
        assert stats["research"] == 1
        assert stats["published_reports"] == 1
        assert stats["events"] == 1
