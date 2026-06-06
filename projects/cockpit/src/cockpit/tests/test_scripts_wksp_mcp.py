"""cockpit_mcp.py — 13 个 MCP 工具函数测试。"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from cockpit.tests.conftest import MockDataAccess


@pytest.fixture(autouse=True)
def _patch_da(monkeypatch):
    """所有测试使用 MockDataAccess 替换 _da。"""
    mock_da = MockDataAccess()
    monkeypatch.setattr("scripts.cockpit_mcp._da", mock_da)
    return mock_da


# ═══════════════════════════════════════════════════════════════════════════════
# research_list
# ═══════════════════════════════════════════════════════════════════════════════


class TestResearchList:
    def test_empty(self, _patch_da):
        """无研究→空数组"""
        _patch_da.list_research = lambda limit=20, include_archived=False: []
        from scripts.cockpit_mcp import research_list

        result = json.loads(research_list())
        assert result == []

    def test_with_items(self, _patch_da):
        """有研究→正确字段"""
        _patch_da.list_research = lambda limit=20, include_archived=False: [
            {
                "id": 1,
                "topic": "AI Safety",
                "summary": "A summary",
                "agent": "minerva",
                "tags": ["AI"],
                "created_at": 1700000000.0,
                "archived_at": None,
            },
            {
                "id": 2,
                "topic": "Archived",
                "summary": "",
                "agent": "",
                "tags": [],
                "created_at": 1690000000.0,
                "archived_at": 1695000000.0,
            },
        ]
        from scripts.cockpit_mcp import research_list

        result = json.loads(research_list())
        assert len(result) == 2
        assert result[0]["topic"] == "AI Safety"
        assert result[0]["summary"] == "A summary"
        assert result[0]["archived"] is False
        assert result[1]["archived"] is True

    def test_limit_and_archived(self, _patch_da):
        """参数传递正确"""
        captured = {}

        def _list(limit=20, include_archived=False):
            captured["limit"] = limit
            captured["archived"] = include_archived
            return []

        _patch_da.list_research = _list
        from scripts.cockpit_mcp import research_list

        research_list(limit=5, include_archived=True)
        assert captured["limit"] == 5
        assert captured["archived"] is True


# ═══════════════════════════════════════════════════════════════════════════════
# research_search
# ═══════════════════════════════════════════════════════════════════════════════


class TestResearchSearch:
    def test_search_results(self, _patch_da):
        """搜索返回结果"""
        _patch_da.search_research = lambda kw, limit=10: [
            {"id": 1, "topic": "LLM Safety", "summary": "About safety in LLMs"},
        ]
        from scripts.cockpit_mcp import research_search

        result = json.loads(research_search(keyword="safety"))
        assert len(result) == 1
        assert result[0]["topic"] == "LLM Safety"

    def test_empty_search(self, _patch_da):
        """搜索无结果→空数组"""
        _patch_da.search_research = lambda kw, limit=10: []
        from scripts.cockpit_mcp import research_search

        result = json.loads(research_search(keyword="nonexistent"))
        assert result == []

    def test_limit_passed(self, _patch_da):
        """搜索 limit 参数正确传递"""
        captured = {}
        _patch_da.search_research = lambda kw, limit=10: captured.update({"kw": kw, "limit": limit}) or []
        from scripts.cockpit_mcp import research_search

        research_search(keyword="test", limit=3)
        assert captured["kw"] == "test"
        assert captured["limit"] == 3


# ═══════════════════════════════════════════════════════════════════════════════
# research_dossier
# ═══════════════════════════════════════════════════════════════════════════════


class TestResearchDossier:
    def test_not_found(self, _patch_da):
        """研究不存在→错误 JSON"""
        _patch_da.get_research_dossier = lambda rid: None
        from scripts.cockpit_mcp import research_dossier

        result = json.loads(research_dossier(research_id=999))
        assert "error" in result

    def test_with_relations(self, _patch_da):
        """有 parents/children/publications→完整 JSON"""
        _patch_da.get_research_dossier = lambda rid: {
            "record": {
                "id": 1,
                "topic": "Test",
                "summary": "s",
                "agent": "minerva",
                "tags": ["t1"],
                "archived_at": None,
            },
            "parents": [{"id": 10, "topic": "Parent"}],
            "children": [{"id": 20, "topic": "Child"}],
            "publications": [{"style": "brief", "output_path": "/tmp/out.md", "published_at": 1700000000.0}],
        }
        from scripts.cockpit_mcp import research_dossier

        result = json.loads(research_dossier(research_id=1))
        assert result["id"] == 1
        assert result["topic"] == "Test"
        assert len(result["parents"]) == 1
        assert result["parents"][0]["id"] == 10
        assert len(result["children"]) == 1
        assert result["children"][0]["id"] == 20
        assert len(result["publications"]) == 1
        assert result["publications"][0]["style"] == "brief"
        assert result["archived"] is False


# ═══════════════════════════════════════════════════════════════════════════════
# research_half_life
# ═══════════════════════════════════════════════════════════════════════════════


class TestResearchHalfLife:
    def test_returns_hl(self, _patch_da):
        """半衰期返回 JSON"""
        _patch_da.compute_half_life = lambda rid: {"decay": 0.75, "id": 1}
        from scripts.cockpit_mcp import research_half_life

        result = json.loads(research_half_life(research_id=1))
        assert result["decay"] == 0.75
        assert result["id"] == 1


# ═══════════════════════════════════════════════════════════════════════════════
# research_agent_list
# ═══════════════════════════════════════════════════════════════════════════════


class TestResearchAgentList:
    def test_agent_filter(self, _patch_da):
        """按 Agent 名称过滤"""
        _patch_da.list_research = lambda limit=20: [
            {"id": 1, "topic": "A", "summary": "s1", "agent": "minerva", "tags": [], "created_at": 1700000000.0},
            {"id": 2, "topic": "B", "summary": "s2", "agent": "other", "tags": [], "created_at": 1700000000.0},
        ]
        from scripts.cockpit_mcp import research_agent_list

        result = json.loads(research_agent_list(agent_name="minerva"))
        assert len(result) == 1
        assert result[0]["topic"] == "A"

    def test_no_match(self, _patch_da):
        """无匹配 Agent→空数组"""
        _patch_da.list_research = lambda limit=20: [
            {"id": 1, "topic": "A", "summary": "s", "agent": "minerva", "tags": [], "created_at": 1700000000.0},
        ]
        from scripts.cockpit_mcp import research_agent_list

        result = json.loads(research_agent_list(agent_name="nonexistent"))
        assert result == []


# ═══════════════════════════════════════════════════════════════════════════════
# status_summary
# ═══════════════════════════════════════════════════════════════════════════════


class TestStatusSummary:
    def test_empty(self, _patch_da):
        """无研究→idle 状态"""
        _patch_da.list_research = lambda limit=100: []
        from scripts.cockpit_mcp import status_summary

        result = json.loads(status_summary())
        assert result["total"] == 0
        assert result["active"] == 0
        assert result["health"] == "idle"

    def test_with_data(self, _patch_da):
        """有活跃和归档研究"""
        _patch_da.list_research = lambda limit=100: [
            {"id": 1, "created_at": 1700000000.0, "archived_at": None},
            {"id": 2, "created_at": 1680000000.0, "archived_at": 1690000000.0},
        ]
        from scripts.cockpit_mcp import status_summary

        result = json.loads(status_summary())
        assert result["total"] == 2
        assert result["active"] == 1
        assert result["archived"] == 1
        assert result["health"] == "good"

    def test_stale_items(self, _patch_da):
        """有过期研究→stale 计数"""
        import time

        now = time.time()
        _patch_da.list_research = lambda limit=100: [
            {"id": 1, "created_at": now - 999999, "archived_at": None},  # very old, stale
            {"id": 2, "created_at": now - 3600, "archived_at": None},  # recent
        ]
        from scripts.cockpit_mcp import status_summary

        result = json.loads(status_summary())
        assert result["stale"] == 1
        assert result["active"] == 2


# ═══════════════════════════════════════════════════════════════════════════════
# research_open（新增工具）
# ═══════════════════════════════════════════════════════════════════════════════


class TestResearchOpen:
    def test_not_found(self, _patch_da):
        """研究不存在→错误 JSON"""
        _patch_da.get_research = lambda research_id=0: None
        from scripts.cockpit_mcp import research_open

        result = json.loads(research_open(research_id=999))
        assert "error" in result

    def test_found(self, _patch_da):
        """研究存在→完整信息"""
        _patch_da.get_research = lambda research_id=0: {
            "id": 1,
            "topic": "量子计算",
            "summary": "A quantum summary",
            "full_text": "Long text...",
            "agent": "minerva",
            "tags": ["QC"],
            "created_at": 1700000000.0,
            "source_count": 5,
            "archived_at": None,
            "follow_ups": [{"q": "?", "a": "!"}],
        }
        from scripts.cockpit_mcp import research_open

        result = json.loads(research_open(research_id=1))
        assert result["id"] == 1
        assert result["topic"] == "量子计算"
        assert result["summary"] == "A quantum summary"
        assert result["agent"] == "minerva"
        assert result["tags"] == ["QC"]
        assert result["source_count"] == 5
        assert result["archived"] is False
        assert len(result["follow_ups"]) == 1

    def test_archived_flag(self, _patch_da):
        """已归档→archived=True"""
        _patch_da.get_research = lambda research_id=0: {
            "id": 2,
            "topic": "Old",
            "summary": "",
            "full_text": "",
            "agent": "",
            "tags": [],
            "created_at": 1000000.0,
            "source_count": 0,
            "archived_at": 2000000.0,
            "follow_ups": [],
        }
        from scripts.cockpit_mcp import research_open

        result = json.loads(research_open(research_id=2))
        assert result["archived"] is True

    def test_follow_ups_empty(self, _patch_da):
        """无追问→空列表"""
        _patch_da.get_research = lambda research_id=0: {
            "id": 3,
            "topic": "No Fups",
            "summary": "",
            "full_text": "",
            "agent": "",
            "tags": [],
            "created_at": 1000000.0,
            "source_count": 0,
            "archived_at": None,
            "follow_ups": [],
        }
        from scripts.cockpit_mcp import research_open

        result = json.loads(research_open(research_id=3))
        assert result["follow_ups"] == []


# ═══════════════════════════════════════════════════════════════════════════════
# research_ask（新增工具）
# ═══════════════════════════════════════════════════════════════════════════════


class TestResearchAsk:
    def test_not_found(self, _patch_da):
        """研究不存在→错误 JSON"""
        _patch_da.get_research = lambda research_id=0: None
        from scripts.cockpit_mcp import research_ask

        result = json.loads(research_ask(research_id=999, question="why?"))
        assert "error" in result

    def test_ask_adds_follow_up(self, _patch_da):
        """追问添加成功"""
        _patch_da.get_research = lambda research_id=0: {
            "id": 1,
            "topic": "T",
            "summary": "",
            "full_text": "",
            "agent": "",
            "tags": [],
            "created_at": 1000000.0,
            "source_count": 0,
            "archived_at": None,
            "follow_ups": [],
        }
        captured = {}

        def _add_fup(research_id=0, question="", answer=""):
            captured["rid"] = research_id
            captured["q"] = question
            captured["a"] = answer

        _patch_da.add_follow_up = _add_fup
        from scripts.cockpit_mcp import research_ask

        result = json.loads(research_ask(research_id=1, question="测试追问"))
        assert result["status"] == "added"
        assert result["question"] == "测试追问"
        assert captured["rid"] == 1
        assert captured["q"] == "测试追问"
        assert captured["a"] == ""


# ═══════════════════════════════════════════════════════════════════════════════
# research_archive（新增工具）
# ═══════════════════════════════════════════════════════════════════════════════


class TestResearchArchive:
    def test_archive_ok(self, _patch_da):
        """归档成功"""
        _patch_da.archive_research = lambda research_ids=None, reason="": ([1], [])
        from scripts.cockpit_mcp import research_archive

        result = json.loads(research_archive(research_id=1))
        assert result["status"] == "archived"
        assert result["id"] == 1

    def test_archive_fails(self, _patch_da):
        """归档失败"""
        _patch_da.archive_research = lambda research_ids=None, reason="": ([], [1])
        from scripts.cockpit_mcp import research_archive

        result = json.loads(research_archive(research_id=1))
        assert "error" in result


# ═══════════════════════════════════════════════════════════════════════════════
# research_restore（新增工具）
# ═══════════════════════════════════════════════════════════════════════════════


class TestResearchRestore:
    def test_restore_ok(self, _patch_da):
        """恢复成功"""
        _patch_da.restore_archived_research = lambda research_ids=None: ([1], [])
        from scripts.cockpit_mcp import research_restore

        result = json.loads(research_restore(research_id=1))
        assert result["status"] == "restored"
        assert result["id"] == 1

    def test_restore_fails(self, _patch_da):
        """恢复失败"""
        _patch_da.restore_archived_research = lambda research_ids=None: ([], [1])
        from scripts.cockpit_mcp import research_restore

        result = json.loads(research_restore(research_id=1))
        assert "error" in result


# ═══════════════════════════════════════════════════════════════════════════════
# research_tag（新增工具）
# ═══════════════════════════════════════════════════════════════════════════════


class TestResearchTag:
    def test_set_tags(self, _patch_da):
        """设置标签成功"""
        _patch_da.set_research_tags = lambda research_id=0, tags=None: tags
        from scripts.cockpit_mcp import research_tag

        result = json.loads(research_tag(research_id=1, tags="AI,ML,DL"))
        assert result["id"] == 1
        assert result["tags"] == ["AI", "ML", "DL"]

    def test_empty_tags(self, _patch_da):
        """空标签→空列表"""
        _patch_da.set_research_tags = lambda research_id=0, tags=None: []
        from scripts.cockpit_mcp import research_tag

        result = json.loads(research_tag(research_id=1, tags=""))
        assert result["tags"] == []

    def test_whitespace_handling(self, _patch_da):
        """标签两端空格被去除"""
        _patch_da.set_research_tags = lambda research_id=0, tags=None: tags
        from scripts.cockpit_mcp import research_tag

        result = json.loads(research_tag(research_id=1, tags="  AI  ,  ML  "))
        assert result["tags"] == ["AI", "ML"]


# ═══════════════════════════════════════════════════════════════════════════════
# research_rename（新增工具）
# ═══════════════════════════════════════════════════════════════════════════════


class TestResearchRename:
    def test_rename_ok(self, _patch_da):
        """重命名成功"""
        _patch_da.rename_research = lambda research_id=0, new_topic="": True
        from scripts.cockpit_mcp import research_rename

        result = json.loads(research_rename(research_id=1, topic="新名称"))
        assert result["status"] == "renamed"
        assert result["topic"] == "新名称"
        assert result["id"] == 1

    def test_rename_fails(self, _patch_da):
        """重命名失败"""
        _patch_da.rename_research = lambda research_id=0, new_topic="": False
        from scripts.cockpit_mcp import research_rename

        result = json.loads(research_rename(research_id=999, topic="新名称"))
        assert "error" in result


# ═══════════════════════════════════════════════════════════════════════════════
# 模块级防护 (ImportError guard + mcp.run entry point)
# ═══════════════════════════════════════════════════════════════════════════════
# ImportError guard (行 12-14) 通过子进程 + fake mcp 包触发；
# mcp.run() (行 152) 通过属性检查验证。


def test_cockpit_mcp_import_error(tmp_path):
    """当 fastmcp 不可用时, cockpit_mcp 应优雅退出并打印错误信息。"""
    import os
    import subprocess
    import sys

    # 创建伪装的 mcp 包（缺少 fastmcp 模块）
    fake_mcp = tmp_path / "mcp"
    fake_server = fake_mcp / "server"
    fake_server.mkdir(parents=True)
    (fake_mcp / "__init__.py").write_text("")
    (fake_server / "__init__.py").write_text("")

    # cockpit 包即项目根目录 (cockpit/__init__.py), 需其父目录在 sys.path 中
    cockpit_root = Path(__file__).resolve().parent.parent  # .../cockpit/
    pkg_parent = str(cockpit_root.parent)  # .../Workspace/

    env = {**os.environ, "PYTHONPATH": f"{tmp_path}:{pkg_parent}"}

    result = subprocess.run(
        [sys.executable, "-m", "cockpit.scripts.cockpit_mcp"],
        capture_output=True,
        text=True,
        timeout=10,
        cwd=pkg_parent,
        env=env,
    )
    assert result.returncode == 1
    assert "需安装 fastmcp" in result.stderr


def test_mcp_run_is_callable():
    """mcp.run(transport='stdio') 可被调用。"""
    from scripts.cockpit_mcp import mcp

    assert hasattr(mcp, "run")
    assert callable(mcp.run)


# ═══════════════════════════════════════════════════════════════════════════════
# research_create（新增工具）
# ═══════════════════════════════════════════════════════════════════════════════


class TestResearchCreate:
    def test_create_ok(self, _patch_da):
        """创建成功→返回 id/topic/status"""
        _patch_da.save_research = lambda topic, summary="", full_text="", source_count=0, agent="": 99
        from scripts.cockpit_mcp import research_create

        result = json.loads(research_create(topic="量子计算"))
        assert result["id"] == 99
        assert result["topic"] == "量子计算"
        assert result["status"] == "created"

    def test_create_passes_defaults(self, _patch_da):
        """确保 save_research 以空 summary/full_text 调用"""
        captured = {}

        def _save(topic, summary="", full_text="", source_count=0, agent=""):
            captured["topic"] = topic
            captured["summary"] = summary
            captured["full_text"] = full_text
            captured["source_count"] = source_count
            return 42

        _patch_da.save_research = _save
        from scripts.cockpit_mcp import research_create

        research_create(topic="test")
        assert captured["topic"] == "test"
        assert captured["summary"] == ""
        assert captured["full_text"] == ""
        assert captured["source_count"] == 0


# ═══════════════════════════════════════════════════════════════════════════════
# status_json（新增工具）
# ═══════════════════════════════════════════════════════════════════════════════


class TestStatusJson:
    def test_empty(self, _patch_da):
        """无研究→idle, recent 为空数组"""
        _patch_da.list_research = lambda limit=100: []
        from scripts.cockpit_mcp import status_json

        result = json.loads(status_json())
        assert result["status"] == "ok"
        assert result["total"] == 0
        assert result["active"] == 0
        assert result["health"] == "idle"
        assert result["recent"] == []

    def test_with_mixed_data(self, _patch_da):
        """活跃+归档+过期研究→正确统计"""
        import time

        now = time.time()
        _patch_da.list_research = lambda limit=100: [
            {
                "id": 1,
                "topic": "Active",
                "created_at": now - 3600,
                "archived_at": None,
                "follow_ups": [],
                "agent": "minerva",
            },
            {
                "id": 2,
                "topic": "Archived",
                "created_at": now - 99999,
                "archived_at": now - 50000,
                "follow_ups": [],
                "agent": "",
            },
            {
                "id": 3,
                "topic": "Stale",
                "created_at": now - 999999,
                "archived_at": None,
                "follow_ups": [{"q": "?"}],
                "agent": "ollama",
            },
        ]
        from scripts.cockpit_mcp import status_json

        result = json.loads(status_json())
        assert result["total"] == 3
        assert result["active"] == 2  # 1 + 3 (未归档)
        assert result["archived"] == 1
        assert result["stale"] == 1  # id=3 超过 72h
        assert result["health"] == "good"
        assert len(result["recent"]) == 3
        assert result["recent"][0]["topic"] == "Active"
        assert result["recent"][0]["follow_up_count"] == 0
        assert result["recent"][2]["follow_up_count"] == 1
        assert result["recent"][2]["agent"] == "ollama"


# ═══════════════════════════════════════════════════════════════════════════════
# daily_summary（新增工具）
# ═══════════════════════════════════════════════════════════════════════════════


class TestDailySummary:
    def test_no_recent(self, _patch_da):
        """所有研究在 cutoff 之前→空列表"""
        import time

        old = time.time() - 999999
        _patch_da.list_research = lambda limit=50: [
            {"id": 1, "topic": "Old", "created_at": old, "archived_at": None, "follow_ups": []},
        ]
        from scripts.cockpit_mcp import daily_summary

        result = json.loads(daily_summary(days=1))
        assert result["days"] == 1
        assert result["total"] == 0
        assert result["items"] == []

    def test_with_recent(self, _patch_da):
        """部分研究在最近 N 天内→筛选正确"""
        import time

        now = time.time()
        _patch_da.list_research = lambda limit=50: [
            {"id": 1, "topic": "Recent", "created_at": now - 3600, "archived_at": None, "follow_ups": []},
            {"id": 2, "topic": "Old", "created_at": now - 999999, "archived_at": None, "follow_ups": []},
        ]
        from scripts.cockpit_mcp import daily_summary

        result = json.loads(daily_summary(days=1))
        assert result["total"] == 1
        assert result["items"][0]["topic"] == "Recent"
        assert result["items"][0]["follow_up_count"] == 0

    def test_custom_days(self, _patch_da):
        """自定义 days 参数扩大窗口"""
        import time

        now = time.time()
        _patch_da.list_research = lambda limit=50: [
            {"id": 1, "topic": "Three Days Ago", "created_at": now - 3 * 86400, "archived_at": None, "follow_ups": []},
        ]
        from scripts.cockpit_mcp import daily_summary

        # 1 天窗口→不包含
        result1 = json.loads(daily_summary(days=1))
        assert result1["total"] == 0
        # 7 天窗口→包含
        result7 = json.loads(daily_summary(days=7))
        assert result7["total"] == 1
        assert result7["items"][0]["topic"] == "Three Days Ago"
