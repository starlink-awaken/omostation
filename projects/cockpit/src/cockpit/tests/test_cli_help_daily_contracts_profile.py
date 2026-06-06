"""测试剩余 8 个零覆盖命令：help/daily/contracts validate|list|export-*/profile。"""

from __future__ import annotations

import argparse
import json
from unittest import mock

from rich.console import Console
from cockpit import cli
from cockpit.tests.conftest import MockDataAccess

# ═══════════════════════════════════════════════════════════════════════════════
# cmd_help — status.py:348
# ═══════════════════════════════════════════════════════════════════════════════


class TestCmdHelp:
    """cmd_help 测试。"""

    def test_help_returns_zero_and_contains_guide(self, monkeypatch):
        """help 命令→return 0 + 包含产品地图关键内容"""
        capture = Console(record=True, force_terminal=True, width=140)
        monkeypatch.setattr(cli, "console", capture)

        code = cli.cmd_help(argparse.Namespace())

        output = capture.export_text()
        assert code == 0
        assert "产品地图" in output
        assert "demo" in output
        assert "research" in output
        assert "contracts" in output


# ═══════════════════════════════════════════════════════════════════════════════
# cmd_daily — status.py:381
# ═══════════════════════════════════════════════════════════════════════════════

# 保存 cmd_daily 引用的模块引用
_status_mod_daily = __import__("cockpit.commands.status", fromlist=[""])


class TestCmdDaily:
    """cmd_daily 测试（空 / 有研究 / 含追问和发布）。"""

    def test_no_recent_research(self, monkeypatch):
        """过去 N 天无新研究→提示"""
        capture = Console(record=True, force_terminal=True, width=140)
        monkeypatch.setattr(cli, "console", capture)
        mock_da = MockDataAccess()
        # list_research 返回空 → recent 为空
        mock_da.list_research = lambda limit=50: []
        monkeypatch.setattr(_status_mod_daily, "_get_data_access", lambda: mock_da)

        code = cli.cmd_daily(argparse.Namespace(days=7))

        output = capture.export_text()
        assert code == 0
        assert "今日站会" in output
        assert "没有新研究" in output

    def test_with_recent_research(self, monkeypatch):
        """有近期研究→渲染统计+行动清单+推荐"""
        import time

        now = time.time()
        capture = Console(record=True, force_terminal=True, width=160)
        monkeypatch.setattr(cli, "console", capture)
        mock_da = MockDataAccess()
        mock_da.list_research = lambda limit=50: [
            {
                "id": 1,
                "topic": "AI Safety",
                "created_at": now - 3600,
                "source_count": 3,
                "summary": "s",
                "follow_ups": [{"q": "q1"}],
                "archived_at": None,
            },
            {
                "id": 2,
                "topic": "LLM Theory",
                "created_at": now - 90000,
                "source_count": 2,
                "summary": "s2",
                "follow_ups": [],
                "archived_at": None,
            },
        ]
        mock_da.get_research_dossier = lambda rid: {"publications": [{"style": "brief"}]} if rid == 1 else {}
        mock_da.get_research_timeline = lambda rid: []
        mock_da.compute_half_life = lambda rid: {"decay": 0.85}
        monkeypatch.setattr(_status_mod_daily, "_get_data_access", lambda: mock_da)

        code = cli.cmd_daily(argparse.Namespace(days=7))

        output = capture.export_text()
        assert code == 0
        assert "今日站会" in output
        assert "AI Safety" in output
        assert "LLM Theory" in output
        assert "2 项" in output  # total count

    def test_archived_research_shown_as_dim(self, monkeypatch):
        """已归档研究→标记为已归档"""
        import time

        now = time.time()
        capture = Console(record=True, force_terminal=True, width=160)
        monkeypatch.setattr(cli, "console", capture)
        mock_da = MockDataAccess()
        mock_da.list_research = lambda limit=50: [
            {
                "id": 1,
                "topic": "Old Topic",
                "created_at": now - 200000,
                "source_count": 1,
                "summary": "s",
                "follow_ups": [],
                "archived_at": now - 100000,
            },
        ]
        mock_da.get_research_dossier = lambda rid: {}
        mock_da.get_research_timeline = lambda rid: []
        mock_da.compute_half_life = lambda rid: {"decay": 0.1}
        monkeypatch.setattr(_status_mod_daily, "_get_data_access", lambda: mock_da)

        code = cli.cmd_daily(argparse.Namespace(days=30))

        output = capture.export_text()
        assert code == 0
        assert "已归档" in output

    def test_non_archived_old_research_shows_decay_mark(self, monkeypatch):
        """未归档且 age_hours >= 72 且 days_since_active >= 3 → 待保鲜标记 (lines 435-456)."""
        import time

        now = time.time()
        capture = Console(record=True, force_terminal=True, width=160)
        monkeypatch.setattr(cli, "console", capture)
        mock_da = MockDataAccess()
        # 创建一条 5 天前的记录，未归档，timeline 中 last_active 也很旧
        old_created = now - 5 * 86400
        mock_da.list_research = lambda limit=50: [
            {
                "id": 1,
                "topic": "Stale Study",
                "created_at": old_created,
                "source_count": 1,
                "summary": "s",
                "follow_ups": [],
                "archived_at": None,
            },
        ]
        mock_da.get_research_dossier = lambda rid: {}
        # timeline 的 last_active 也是 5 天前
        mock_da.get_research_timeline = lambda rid: [{"created_at": str(old_created), "event_type": "created"}]
        mock_da.compute_half_life = lambda rid: {"decay": 0.1}
        monkeypatch.setattr(_status_mod_daily, "_get_data_access", lambda: mock_da)

        code = cli.cmd_daily(argparse.Namespace(days=30))

        output = capture.export_text()
        assert code == 0
        assert "待保鲜" in output

    def test_cmd_daily_subprocess_agora_health_fails(self, monkeypatch):
        """agora health 子进程抛出异常→except Exception 路径 (lines 432-433)."""
        import subprocess as _sp
        import time

        capture = Console(record=True, force_terminal=True, width=140)
        monkeypatch.setattr(cli, "console", capture)
        mock_da = MockDataAccess()
        mock_da.list_research = lambda limit=50: [
            {
                "id": 1,
                "topic": "Test",
                "created_at": time.time() - 3600,
                "source_count": 1,
                "summary": "s",
                "follow_ups": [],
                "archived_at": None,
            },
        ]
        mock_da.get_research_dossier = lambda rid: {}
        mock_da.get_research_timeline = lambda rid: []
        mock_da.compute_half_life = lambda rid: {"decay": 0.85}
        monkeypatch.setattr(_status_mod_daily, "_get_data_access", lambda: mock_da)

        # 让 subprocess.run 对任何调用都抛出 FileNotFoundError
        def _raise_run(*a, **kw):
            raise FileNotFoundError("agora not found")

        monkeypatch.setattr(_sp, "run", _raise_run)

        code = cli.cmd_daily(argparse.Namespace(days=7))
        assert code == 0

    def test_cmd_daily_decay_thresholds(self, monkeypatch):
        """不同衰变值的分支覆盖 (lines 466 [>=0.5], 468 [>=0.25])."""
        import time

        now = time.time()
        capture = Console(record=True, force_terminal=True, width=160)
        monkeypatch.setattr(cli, "console", capture)
        mock_da = MockDataAccess()
        # 用 2 条研究分别触发 decay >= 0.5 和 decay >= 0.25 分支
        mock_da.list_research = lambda limit=50: [
            {
                "id": 1,
                "topic": "Med Decay",
                "created_at": now - 3600,
                "source_count": 1,
                "summary": "s",
                "follow_ups": [],
                "archived_at": None,
            },
            {
                "id": 2,
                "topic": "Low Decay",
                "created_at": now - 3600,
                "source_count": 1,
                "summary": "s",
                "follow_ups": [],
                "archived_at": None,
            },
        ]
        mock_da.get_research_dossier = lambda rid: {}
        mock_da.get_research_timeline = lambda rid: []
        _hl_call = [0]

        def _hl(rid):
            v = [{"decay": 0.6}, {"decay": 0.3}][_hl_call[0]]
            _hl_call[0] += 1
            return v

        mock_da.compute_half_life = _hl
        monkeypatch.setattr(_status_mod_daily, "_get_data_access", lambda: mock_da)

        code = cli.cmd_daily(argparse.Namespace(days=7))
        assert code == 0

    def test_cmd_daily_stale_and_followup_stats(self, monkeypatch):
        """Daily 统计面板中的待追问和待保鲜计数"""
        import time

        now = time.time()
        capture = Console(record=True, force_terminal=True, width=160)
        monkeypatch.setattr(cli, "console", capture)
        mock_da = MockDataAccess()
        mock_da.list_research = lambda limit=50: [
            {
                "id": 1,
                "topic": "New",
                "created_at": now - 1000,
                "source_count": 1,
                "summary": "s",
                "follow_ups": [{"q": "?", "a": "!"}],
                "archived_at": None,
            },
            {
                "id": 2,
                "topic": "Stale No Fup",
                "created_at": now - 999999,
                "source_count": 1,
                "summary": "s",
                "follow_ups": [],
                "archived_at": None,
            },
        ]
        mock_da.get_research_dossier = lambda rid: {}
        mock_da.get_research_timeline = lambda rid: []
        mock_da.compute_half_life = lambda rid: {"decay": 0.85}
        monkeypatch.setattr(_status_mod_daily, "_get_data_access", lambda: mock_da)

        code = cli.cmd_daily(argparse.Namespace(days=7))
        assert code == 0
        output = capture.export_text()
        assert "待追问" in output
        assert "待保鲜" in output


# ═══════════════════════════════════════════════════════════════════════════════
# cmd_contracts_validate — contracts.py:112
# ═══════════════════════════════════════════════════════════════════════════════


class TestCmdContractsValidate:
    """cmd_contracts_validate 测试。"""

    def test_schema_not_found(self, monkeypatch, tmp_path):
        """Schema 文件不存在→错误"""
        capture = Console(record=True, force_terminal=True, width=140)
        err = Console(record=True, force_terminal=True, width=140)
        monkeypatch.setattr(cli, "console", capture)
        monkeypatch.setattr(cli, "err", err)

        # Mock _workspace_root 指向 tmp_path（无 schema 文件）
        monkeypatch.setattr("cockpit.commands.contracts._workspace_root", lambda: tmp_path)

        from cockpit.commands.contracts import cmd_contracts_validate

        code = cmd_contracts_validate(argparse.Namespace(path=None))

        err_output = err.export_text()
        assert code == 2
        assert "schema 无效" in err_output or "无效" in err_output

    def test_schema_valid_no_path(self, monkeypatch, tmp_path):
        """Schema 文件有效 + 无 path 参数→通过"""
        capture = Console(record=True, force_terminal=True, width=140)
        err = Console(record=True, force_terminal=True, width=140)
        monkeypatch.setattr(cli, "console", capture)
        monkeypatch.setattr(cli, "err", err)

        # 创建有效的 schema 文件
        contracts_dir = tmp_path / "docs" / "contracts"
        contracts_dir.mkdir(parents=True)
        schema = {
            "title": "WorkspaceObject",
            "type": "object",
            "required": [
                "id",
                "type",
                "version",
                "title",
                "owner",
                "source",
                "created_at",
                "updated_at",
                "trace_id",
                "schema_ref",
                "capabilities_required",
                "audit_events",
            ],
            "properties": {
                f: {"type": "string"}
                for f in [
                    "id",
                    "type",
                    "version",
                    "title",
                    "owner",
                    "source",
                    "created_at",
                    "updated_at",
                    "trace_id",
                    "schema_ref",
                    "capabilities_required",
                    "audit_events",
                ]
            },
        }
        (contracts_dir / "workspace-object.schema.json").write_text(json.dumps(schema))

        monkeypatch.setattr("cockpit.commands.contracts._workspace_root", lambda: tmp_path)

        from cockpit.commands.contracts import cmd_contracts_validate

        code = cmd_contracts_validate(argparse.Namespace(path=None))

        output = capture.export_text()
        assert code == 0
        assert "contracts validate 通过" in output

    def test_validate_specific_object_fails(self, monkeypatch, tmp_path):
        """Path 参数指定无效对象→错误"""
        capture = Console(record=True, force_terminal=True, width=140)
        err = Console(record=True, force_terminal=True, width=140)
        monkeypatch.setattr(cli, "console", capture)
        monkeypatch.setattr(cli, "err", err)

        contracts_dir = tmp_path / "docs" / "contracts"
        contracts_dir.mkdir(parents=True)
        schema = {
            "title": "WorkspaceObject",
            "type": "object",
            "required": [
                "id",
                "type",
                "version",
                "title",
                "owner",
                "source",
                "created_at",
                "updated_at",
                "trace_id",
                "schema_ref",
                "capabilities_required",
                "audit_events",
            ],
            "properties": {
                f: {"type": "string"}
                for f in [
                    "id",
                    "type",
                    "version",
                    "title",
                    "owner",
                    "source",
                    "created_at",
                    "updated_at",
                    "trace_id",
                    "schema_ref",
                    "capabilities_required",
                    "audit_events",
                ]
            },
        }
        (contracts_dir / "workspace-object.schema.json").write_text(json.dumps(schema))

        monkeypatch.setattr("cockpit.commands.contracts._workspace_root", lambda: tmp_path)

        # 创建一个缺失字段的对象文件
        bad_obj = tmp_path / "bad_object.json"
        bad_obj.write_text(json.dumps({"id": "test"}))  # 缺很多字段

        from cockpit.commands.contracts import cmd_contracts_validate

        code = cmd_contracts_validate(argparse.Namespace(path=str(bad_obj)))

        err_output = err.export_text()
        assert code == 2
        assert "未满足" in err_output


# ═══════════════════════════════════════════════════════════════════════════════
# cmd_contracts_list — contracts.py:160
# ═══════════════════════════════════════════════════════════════════════════════


class TestCmdContractsList:
    """cmd_contracts_list 测试。"""

    def test_list_renders_registry(self, monkeypatch, tmp_path):
        """列出契约注册表→渲染表格"""
        capture = Console(record=True, force_terminal=True, width=140)
        monkeypatch.setattr(cli, "console", capture)

        # 创建 schema 文件和 eidos registry
        docs_dir = tmp_path / "docs" / "contracts"
        docs_dir.mkdir(parents=True)
        (docs_dir / "workspace-object.schema.json").write_text(
            json.dumps(
                {
                    "title": "WorkspaceObject",
                    "description": "Standard object",
                }
            )
        )

        eidos_dir = tmp_path / "eidos" / "schemas"
        eidos_dir.mkdir(parents=True)
        (eidos_dir / "registry.json").write_text(
            json.dumps(
                {
                    "schemas": [
                        {"name": "test-schema", "version": "1.0.0", "file": "test.json", "description": "Test schema"}
                    ],
                }
            )
        )

        monkeypatch.setattr("cockpit.commands.contracts._workspace_root", lambda: tmp_path)

        from cockpit.commands.contracts import cmd_contracts_list

        code = cmd_contracts_list(argparse.Namespace())

        output = capture.export_text()
        assert code == 0
        assert "Contracts Registry" in output
        assert "workspace-object" in output
        assert "test-schema" in output

    def test_list_fallback_no_registry(self, monkeypatch, tmp_path):
        """无 registry.json→回退到逐个扫描 eidos schemas"""
        capture = Console(record=True, force_terminal=True, width=140)
        monkeypatch.setattr(cli, "console", capture)

        docs_dir = tmp_path / "docs" / "contracts"
        docs_dir.mkdir(parents=True)
        (docs_dir / "workspace-object.schema.json").write_text(
            json.dumps(
                {
                    "title": "WorkspaceObject",
                    "description": "Standard object",
                }
            )
        )

        eidos_dir = tmp_path / "eidos" / "schemas"
        eidos_dir.mkdir(parents=True)
        (eidos_dir / "custom_schema.json").write_text(
            json.dumps(
                {
                    "title": "CustomSchema",
                    "description": "A custom schema",
                }
            )
        )

        monkeypatch.setattr("cockpit.commands.contracts._workspace_root", lambda: tmp_path)

        from cockpit.commands.contracts import cmd_contracts_list

        code = cmd_contracts_list(argparse.Namespace())

        output = capture.export_text()
        assert code == 0
        assert "workspace-object" in output
        assert "custom_schema" in output


# ═══════════════════════════════════════════════════════════════════════════════
# cmd_contracts_export_research — contracts.py:192
# ═══════════════════════════════════════════════════════════════════════════════


class TestCmdContractsExportResearch:
    """cmd_contracts_export_research 测试。"""

    def test_research_not_found(self, monkeypatch):
        """研究对象不存在→错误"""
        err = Console(record=True, force_terminal=True, width=140)
        monkeypatch.setattr(cli, "err", err)
        mock_da = MockDataAccess()
        mock_da.get_research = lambda rid: None
        monkeypatch.setattr(cli, "get_data_access", lambda: mock_da)

        from cockpit.commands.contracts import cmd_contracts_export_research

        code = cmd_contracts_export_research(argparse.Namespace(research_id="999", output=None))

        output = err.export_text()
        assert code == 1
        assert "未找到" in output

    def test_export_research_to_stdout(self, monkeypatch):
        """导出到 stdout→打印 JSON"""
        mock_da = MockDataAccess()
        mock_da.get_research = lambda rid: {
            "id": 1,
            "topic": "test topic",
            "created_at": 1700000000.0,
            "source_count": 2,
            "summary": "s",
            "full_text": "body",
            "follow_ups": [{"question": "q", "answer": "a", "timestamp": 1700000100.0}],
            "tags": [],
            "archived_at": None,
            "quarantined_at": None,
        }
        mock_da.get_research_timeline = lambda rid: []
        mock_da.get_research_dossier = lambda rid: {}
        monkeypatch.setattr(cli, "get_data_access", lambda: mock_da)

        from cockpit.commands.contracts import cmd_contracts_export_research

        code = cmd_contracts_export_research(argparse.Namespace(research_id="1", output=None))

        assert code == 0
        # stdout 被 Rich console 打印，此处验证返回码即可

    def test_export_research_to_file(self, monkeypatch, tmp_path):
        """导出到文件→写入 JSON 文件"""
        capture = Console(record=True, force_terminal=True, width=140)
        monkeypatch.setattr(cli, "console", capture)
        mock_da = MockDataAccess()
        mock_da.get_research = lambda rid: {
            "id": 1,
            "topic": "test topic",
            "created_at": 1700000000.0,
            "source_count": 2,
            "summary": "s",
            "full_text": "body",
            "follow_ups": [],
            "tags": [],
            "archived_at": None,
            "quarantined_at": None,
        }
        mock_da.get_research_timeline = lambda rid: []
        mock_da.get_research_dossier = lambda rid: {}
        monkeypatch.setattr(cli, "get_data_access", lambda: mock_da)

        output_path = tmp_path / "exported.json"
        from cockpit.commands.contracts import cmd_contracts_export_research

        code = cmd_contracts_export_research(argparse.Namespace(research_id="1", output=str(output_path)))

        output = capture.export_text()
        assert code == 0
        assert "已导出" in output
        assert output_path.exists()
        data = json.loads(output_path.read_text())
        assert data["type"] == "research_object"
        assert data["id"] == "research:1"


# ═══════════════════════════════════════════════════════════════════════════════
# cmd_contracts_export_identity — contracts.py:222
# ═══════════════════════════════════════════════════════════════════════════════


class TestCmdContractsExportIdentity:
    """cmd_contracts_export_identity 测试。"""

    def test_export_identity_to_stdout(self, monkeypatch, tmp_path):
        """导出 identity 到 stdout→打印 JSON"""
        monkeypatch.setattr("cockpit.commands.base._PROFILE_PATH", tmp_path / "persona.yaml")

        from cockpit.commands.contracts import cmd_contracts_export_identity

        code = cmd_contracts_export_identity(argparse.Namespace(output=None))

        assert code == 0

    def test_export_identity_to_file(self, monkeypatch, tmp_path):
        """导出 identity 到文件→写入 JSON"""
        capture = Console(record=True, force_terminal=True, width=140)
        monkeypatch.setattr(cli, "console", capture)
        monkeypatch.setattr("cockpit.commands.base._PROFILE_PATH", tmp_path / "persona.yaml")

        output_path = tmp_path / "identity.json"
        from cockpit.commands.contracts import cmd_contracts_export_identity

        code = cmd_contracts_export_identity(argparse.Namespace(output=str(output_path)))

        output = capture.export_text()
        assert code == 0
        assert "已导出" in output
        assert output_path.exists()
        data = json.loads(output_path.read_text())
        assert data["type"] == "identity_envelope"


# ═══════════════════════════════════════════════════════════════════════════════
# cmd_contracts_export_event — contracts.py:247
# ═══════════════════════════════════════════════════════════════════════════════


class TestCmdContractsExportEvent:
    """cmd_contracts_export_event 测试。"""

    def test_missing_id(self, monkeypatch):
        """缺少 --id→错误"""
        err = Console(record=True, force_terminal=True, width=140)
        monkeypatch.setattr(cli, "err", err)

        from cockpit.commands.contracts import cmd_contracts_export_event

        code = cmd_contracts_export_event(argparse.Namespace(id=None, output=None))

        output = err.export_text()
        assert code == 1
        assert "请使用 --id" in output

    def test_no_timeline(self, monkeypatch):
        """研究无事件→错误"""
        err = Console(record=True, force_terminal=True, width=140)
        monkeypatch.setattr(cli, "err", err)
        mock_da = MockDataAccess()
        mock_da.get_research_timeline = lambda rid: []
        monkeypatch.setattr(cli, "get_data_access", lambda: mock_da)

        from cockpit.commands.contracts import cmd_contracts_export_event

        code = cmd_contracts_export_event(argparse.Namespace(id=999, output=None))

        output = err.export_text()
        assert code == 1
        assert "未找到" in output

    def test_export_event_to_file(self, monkeypatch, tmp_path):
        """导出事件到文件→写入 JSON"""
        capture = Console(record=True, force_terminal=True, width=140)
        monkeypatch.setattr(cli, "console", capture)
        mock_da = MockDataAccess()
        mock_da.get_research_timeline = lambda rid: [
            {"created_at": 1700000000, "event_type": "created"},
        ]
        monkeypatch.setattr(cli, "get_data_access", lambda: mock_da)

        output_path = tmp_path / "events.json"
        from cockpit.commands.contracts import cmd_contracts_export_event

        code = cmd_contracts_export_event(argparse.Namespace(id=1, output=str(output_path)))

        output = capture.export_text()
        assert code == 0
        assert "已导出" in output
        assert output_path.exists()
        data = json.loads(output_path.read_text())
        assert data["type"] == "event_envelope"
        assert len(data["events"]) == 1

    def test_export_event_to_stdout(self, monkeypatch):
        """导出事件到 stdout→打印 JSON"""
        mock_da = MockDataAccess()
        mock_da.get_research_timeline = lambda rid: [
            {"created_at": 1700000000, "event_type": "created"},
        ]
        monkeypatch.setattr(cli, "get_data_access", lambda: mock_da)

        from cockpit.commands.contracts import cmd_contracts_export_event

        code = cmd_contracts_export_event(argparse.Namespace(id=1, output=None))

        assert code == 0


# ═══════════════════════════════════════════════════════════════════════════════
# cmd_profile — profile.py:15
# ═══════════════════════════════════════════════════════════════════════════════


class TestCmdProfile:
    """cmd_profile 测试（无 profile / 有 profile / --edit 模式）。"""

    def test_no_profile(self, monkeypatch, tmp_path):
        """无 profile 文件→显示引导"""
        capture = Console(record=True, force_terminal=True, width=140)
        monkeypatch.setattr(cli, "console", capture)

        # 设置 _PROFILE_PATH 指向不存在的文件
        fake_profile = tmp_path / "nonexistent.yaml"
        monkeypatch.setattr("cockpit.commands.profile._PROFILE_PATH", fake_profile)
        # _load_profile 内部也读 _PROFILE_PATH
        monkeypatch.setattr("cockpit.commands.base._PROFILE_PATH", fake_profile)

        code = cli.cmd_profile(argparse.Namespace(edit=False))

        output = capture.export_text()
        assert code == 0
        assert "未设置身份档案" in output

    def test_profile_exists(self, monkeypatch, tmp_path):
        """存在 profile→显示档案内容"""
        import yaml

        capture = Console(record=True, force_terminal=True, width=140)
        monkeypatch.setattr(cli, "console", capture)

        profile_file = tmp_path / "persona.yaml"
        profile_data = {
            "name": "Test User",
            "role": "researcher",
            "timezone": "Asia/Shanghai",
            "active_domain": "AI Safety",
            "principles": ["Be rigorous", "Stay curious"],
            "created_at": "2026-05-01 00:00:00",
        }
        with open(profile_file, "w") as f:
            yaml.dump(profile_data, f, allow_unicode=True, default_flow_style=False, sort_keys=False)

        monkeypatch.setattr("cockpit.commands.profile._PROFILE_PATH", profile_file)
        monkeypatch.setattr("cockpit.commands.base._PROFILE_PATH", profile_file)

        code = cli.cmd_profile(argparse.Namespace(edit=False))

        output = capture.export_text()
        assert code == 0
        assert "Test User" in output
        assert "researcher" in output
        assert "AI Safety" in output
        assert "Be rigorous" in output

    def test_profile_edit_mode_creates_default(self, monkeypatch, tmp_path):
        """--edit + 无已有文件→创建默认 + 打开编辑器"""
        capture = Console(record=True, force_terminal=True, width=140)
        monkeypatch.setattr(cli, "console", capture)
        monkeypatch.setattr(cli, "err", capture)

        profile_file = tmp_path / "new_persona.yaml"
        monkeypatch.setattr("cockpit.commands.profile._PROFILE_PATH", profile_file)
        monkeypatch.setattr("cockpit.commands.base._PROFILE_PATH", profile_file)

        # Mock subprocess.run and editor
        with mock.patch("cockpit.commands.profile.subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0

            code = cli.cmd_profile(argparse.Namespace(edit=True))

        output = capture.export_text()
        assert code == 0
        assert "已创建默认档案" in output
        assert profile_file.exists()

        # 验证默认 YAML 内容
        import yaml

        content = yaml.safe_load(profile_file.read_text())
        assert content["name"] == "你的名字"
        assert content["role"] == "你的角色"

        # 验证 subprocess.run 被调用（打开编辑器）
        mock_run.assert_called_once()

    def test_profile_edit_existing(self, monkeypatch, tmp_path):
        """--edit + 已有文件→直接打开编辑器，不创建默认模板"""
        capture = Console(record=True, force_terminal=True, width=140)
        monkeypatch.setattr(cli, "console", capture)
        monkeypatch.setattr(cli, "err", capture)

        profile_file = tmp_path / "existing_persona.yaml"
        profile_file.write_text(
            "name: Existing User\nrole: dev\ntimezone: UTC\n"
            "active_domain: Testing\nprinciples: []\ncreated_at: '2026-01-01'\n",
            encoding="utf-8",
        )
        monkeypatch.setattr("cockpit.commands.profile._PROFILE_PATH", profile_file)
        monkeypatch.setattr("cockpit.commands.base._PROFILE_PATH", profile_file)

        with mock.patch("cockpit.commands.profile.subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0

            code = cli.cmd_profile(argparse.Namespace(edit=True))

        output = capture.export_text()
        assert code == 0
        # 不应出现"创建默认档案"提示
        assert "已创建默认档案" not in output
        # 应显示更新后的档案内容
        assert "Existing User" in output
        mock_run.assert_called_once()

    def test_profile_edit_yaml_invalid(self, monkeypatch, tmp_path):
        """--edit 后 YAML 无效→警告"""
        capture = Console(record=True, force_terminal=True, width=140)
        monkeypatch.setattr(cli, "console", capture)
        monkeypatch.setattr(cli, "err", capture)

        profile_file = tmp_path / "invalid.yaml"
        monkeypatch.setattr("cockpit.commands.profile._PROFILE_PATH", profile_file)
        monkeypatch.setattr("cockpit.commands.base._PROFILE_PATH", profile_file)

        with (
            mock.patch("cockpit.commands.profile.subprocess.run") as mock_run,
            mock.patch("cockpit.commands.profile._load_profile", return_value={}),
        ):
            mock_run.return_value.returncode = 0

            code = cli.cmd_profile(argparse.Namespace(edit=True))

        output = capture.export_text()
        assert code == 0
        assert "档案内容为空或格式错误" in output


# ═══════════════════════════════════════════════════════════════════════════════
# _validate_workspace_object_envelope 补充 — 类型校验 (lines 64-70)
# ═══════════════════════════════════════════════════════════════════════════════


class TestValidateEnvelopeTypeChecks:
    """_validate_workspace_object_envelope 类型校验覆盖。"""

    def test_invalid_types_detected(self):
        """非 dict/list 类型→正确标记 (lines 64-70)"""
        from cockpit.commands.contracts import _validate_workspace_object_envelope

        data = {
            "id": "test",
            "type": "test",
            "version": "1.0",
            "title": "t",
            "owner": "string_not_dict",
            "source": "string_not_dict",
            "capabilities_required": "not_a_list",
            "audit_events": "not_a_list",
            "created_at": "now",
            "updated_at": "now",
            "trace_id": "t",
            "schema_ref": "s",
        }
        issues = _validate_workspace_object_envelope(data)
        assert "owner 必须是 object" in issues
        assert "source 必须是 object" in issues
        assert "capabilities_required 必须是 array" in issues
        assert "audit_events 必须是 array" in issues


# ═══════════════════════════════════════════════════════════════════════════════
# _validate_workspace_object_envelope_schema 补充 (lines 78-87)
# ═══════════════════════════════════════════════════════════════════════════════


class TestValidateEnvelopeSchema:
    """_validate_workspace_object_envelope_schema 覆盖。"""

    def test_required_not_list(self):
        """schema.required 不是 array→直接返回错误 (line 78)"""
        from cockpit.commands.contracts import _validate_workspace_object_envelope_schema

        issues = _validate_workspace_object_envelope_schema({"required": "bad", "properties": {}})
        assert issues == ["schema.required 必须是 array"]

    def test_properties_not_dict(self):
        """schema.properties 不是 object→直接返回错误 (line 80)"""
        from cockpit.commands.contracts import _validate_workspace_object_envelope_schema

        issues = _validate_workspace_object_envelope_schema({"required": [], "properties": "bad"})
        assert issues == ["schema.properties 必须是 object"]

    def test_missing_required_fields(self):
        """schema 缺字段→每个缺失都报告 (lines 85, 87)"""
        from cockpit.commands.contracts import _validate_workspace_object_envelope_schema

        issues = _validate_workspace_object_envelope_schema({"required": ["id"], "properties": {"id": {}}})
        assert "schema.required 缺少 type" in issues
        assert "schema.properties 缺少 type" in issues
        # 11 个 missing × 2 checks = 22 issues（只有 id 是完整的）
        assert len(issues) == 22


# ═══════════════════════════════════════════════════════════════════════════════
# _validate_eidos_schemas — lines 94-109
# ═══════════════════════════════════════════════════════════════════════════════


class TestValidateEidosSchemas:
    """_validate_eidos_schemas 覆盖。"""

    def test_validate_with_eidos_errors(self, monkeypatch, tmp_path):
        """Eidos schemas 目录含多种错误→每条路径进入 (lines 94-109)"""
        capture = Console(record=True, force_terminal=True, width=140)
        err = Console(record=True, force_terminal=True, width=140)
        monkeypatch.setattr(cli, "console", capture)
        monkeypatch.setattr(cli, "err", err)

        contracts_dir = tmp_path / "docs" / "contracts"
        contracts_dir.mkdir(parents=True)
        schema = {
            "title": "WorkspaceObject",
            "type": "object",
            "required": [
                "id",
                "type",
                "version",
                "title",
                "owner",
                "source",
                "created_at",
                "updated_at",
                "trace_id",
                "schema_ref",
                "capabilities_required",
                "audit_events",
            ],
            "properties": {
                f: {"type": "string"}
                for f in [
                    "id",
                    "type",
                    "version",
                    "title",
                    "owner",
                    "source",
                    "created_at",
                    "updated_at",
                    "trace_id",
                    "schema_ref",
                    "capabilities_required",
                    "audit_events",
                ]
            },
        }
        (contracts_dir / "workspace-object.schema.json").write_text(json.dumps(schema))

        eidos_dir = tmp_path / "eidos" / "schemas"
        eidos_dir.mkdir(parents=True)
        (eidos_dir / "invalid.json").write_text("{not valid json}")  # line 98-99
        (eidos_dir / "array.json").write_text(json.dumps(["a", "b"]))  # line 102-103
        (eidos_dir / "bare.json").write_text(json.dumps({"foo": 1}))  # line 105-106
        (eidos_dir / "valid.json").write_text(
            json.dumps(
                {  # line 108
                    "$schema": "http://example.com/schema",
                    "title": "OkSchema",
                }
            )
        )

        monkeypatch.setattr("cockpit.commands.contracts._workspace_root", lambda: tmp_path)

        from cockpit.commands.contracts import cmd_contracts_validate

        code = cmd_contracts_validate(argparse.Namespace(path=None))

        err_output = err.export_text()
        assert code == 2
        assert "invalid.json" in err_output
        assert "顶层必须是 object" in err_output
        assert "缺少 $schema 或 title" in err_output

        output = capture.export_text()
        assert "valid.json" in output


# ═══════════════════════════════════════════════════════════════════════════════
# cmd_contracts_validate 补充 — 残余分支 (lines 124-127, 145, 148-149, 156-157)
# ═══════════════════════════════════════════════════════════════════════════════


class TestCmdContractsValidateResidual:
    """cmd_contracts_validate 残余分支覆盖。"""

    def test_schema_issues_reported(self, monkeypatch, tmp_path):
        """Schema 缺必需字段→报告 issues (lines 124-127)"""
        capture = Console(record=True, force_terminal=True, width=140)
        err = Console(record=True, force_terminal=True, width=140)
        monkeypatch.setattr(cli, "console", capture)
        monkeypatch.setattr(cli, "err", err)

        contracts_dir = tmp_path / "docs" / "contracts"
        contracts_dir.mkdir(parents=True)
        # Schema with empty required — triggers missing-field issues
        (contracts_dir / "workspace-object.schema.json").write_text(
            json.dumps(
                {
                    "title": "WS",
                    "required": [],
                    "properties": {},
                }
            )
        )

        monkeypatch.setattr("cockpit.commands.contracts._workspace_root", lambda: tmp_path)

        from cockpit.commands.contracts import cmd_contracts_validate

        code = cmd_contracts_validate(argparse.Namespace(path=None))

        err_output = err.export_text()
        assert code == 2
        assert "缺少最小契约" in err_output

    def test_target_invalid_json(self, monkeypatch, tmp_path):
        """目标文件 JSON 无效→data_error 路径 (lines 148-149)"""
        capture = Console(record=True, force_terminal=True, width=140)
        err = Console(record=True, force_terminal=True, width=140)
        monkeypatch.setattr(cli, "console", capture)
        monkeypatch.setattr(cli, "err", err)

        contracts_dir = tmp_path / "docs" / "contracts"
        contracts_dir.mkdir(parents=True)
        (contracts_dir / "workspace-object.schema.json").write_text(
            json.dumps(
                {
                    "title": "WS",
                    "type": "object",
                    "required": [
                        "id",
                        "type",
                        "version",
                        "title",
                        "owner",
                        "source",
                        "created_at",
                        "updated_at",
                        "trace_id",
                        "schema_ref",
                        "capabilities_required",
                        "audit_events",
                    ],
                    "properties": {
                        f: {"type": "string"}
                        for f in [
                            "id",
                            "type",
                            "version",
                            "title",
                            "owner",
                            "source",
                            "created_at",
                            "updated_at",
                            "trace_id",
                            "schema_ref",
                            "capabilities_required",
                            "audit_events",
                        ]
                    },
                }
            )
        )

        monkeypatch.setattr("cockpit.commands.contracts._workspace_root", lambda: tmp_path)

        invalid_file = tmp_path / "invalid.json"
        invalid_file.write_text("{bad json")  # triggers data_error

        from cockpit.commands.contracts import cmd_contracts_validate

        code = cmd_contracts_validate(argparse.Namespace(path=str(invalid_file)))

        err_output = err.export_text()
        assert code == 2
        assert "contract object 无效" in err_output

    def test_target_relative_path(self, monkeypatch, tmp_path):
        """相对路径→is_absolute 分支 (line 145)"""
        capture = Console(record=True, force_terminal=True, width=140)
        err = Console(record=True, force_terminal=True, width=140)
        monkeypatch.setattr(cli, "console", capture)
        monkeypatch.setattr(cli, "err", err)

        contracts_dir = tmp_path / "docs" / "contracts"
        contracts_dir.mkdir(parents=True)
        (contracts_dir / "workspace-object.schema.json").write_text(
            json.dumps(
                {
                    "title": "WS",
                    "type": "object",
                    "required": [
                        "id",
                        "type",
                        "version",
                        "title",
                        "owner",
                        "source",
                        "created_at",
                        "updated_at",
                        "trace_id",
                        "schema_ref",
                        "capabilities_required",
                        "audit_events",
                    ],
                    "properties": {
                        f: {"type": "string"}
                        for f in [
                            "id",
                            "type",
                            "version",
                            "title",
                            "owner",
                            "source",
                            "created_at",
                            "updated_at",
                            "trace_id",
                            "schema_ref",
                            "capabilities_required",
                            "audit_events",
                        ]
                    },
                }
            )
        )
        monkeypatch.setattr("cockpit.commands.contracts._workspace_root", lambda: tmp_path)

        valid_file = tmp_path / "valid_object.json"
        valid_file.write_text(
            json.dumps(
                {
                    "id": "test",
                    "type": "test",
                    "version": "1.0",
                    "title": "t",
                    "owner": {"id": "me"},
                    "source": {"name": "cli"},
                    "capabilities_required": [],
                    "audit_events": [],
                    "created_at": "now",
                    "updated_at": "now",
                    "trace_id": "t",
                    "schema_ref": "s",
                }
            )
        )

        monkeypatch.chdir(tmp_path)
        from cockpit.commands.contracts import cmd_contracts_validate

        code = cmd_contracts_validate(argparse.Namespace(path="valid_object.json"))

        output = capture.export_text()
        assert code == 0
        assert "contract object validate 通过" in output

    def test_target_valid_object(self, monkeypatch, tmp_path):
        """目标文件 valid→验证通过 (lines 156-157)"""
        capture = Console(record=True, force_terminal=True, width=140)
        err = Console(record=True, force_terminal=True, width=140)
        monkeypatch.setattr(cli, "console", capture)
        monkeypatch.setattr(cli, "err", err)

        contracts_dir = tmp_path / "docs" / "contracts"
        contracts_dir.mkdir(parents=True)
        (contracts_dir / "workspace-object.schema.json").write_text(
            json.dumps(
                {
                    "title": "WS",
                    "type": "object",
                    "required": [
                        "id",
                        "type",
                        "version",
                        "title",
                        "owner",
                        "source",
                        "created_at",
                        "updated_at",
                        "trace_id",
                        "schema_ref",
                        "capabilities_required",
                        "audit_events",
                    ],
                    "properties": {
                        f: {"type": "string"}
                        for f in [
                            "id",
                            "type",
                            "version",
                            "title",
                            "owner",
                            "source",
                            "created_at",
                            "updated_at",
                            "trace_id",
                            "schema_ref",
                            "capabilities_required",
                            "audit_events",
                        ]
                    },
                }
            )
        )

        monkeypatch.setattr("cockpit.commands.contracts._workspace_root", lambda: tmp_path)

        valid_file = tmp_path / "valid.json"
        valid_file.write_text(
            json.dumps(
                {
                    "id": "test",
                    "type": "test",
                    "version": "1.0",
                    "title": "t",
                    "owner": {"id": "me"},
                    "source": {"name": "cli"},
                    "capabilities_required": [],
                    "audit_events": [],
                    "created_at": "now",
                    "updated_at": "now",
                    "trace_id": "t",
                    "schema_ref": "s",
                }
            )
        )

        from cockpit.commands.contracts import cmd_contracts_validate

        code = cmd_contracts_validate(argparse.Namespace(path=str(valid_file)))

        output = capture.export_text()
        assert code == 0
        assert "contract object validate 通过" in output


# ═══════════════════════════════════════════════════════════════════════════════
# cmd_contracts_list 补充 — 跳过 registry.json 目录 (line 183)
# ═══════════════════════════════════════════════════════════════════════════════


class TestCmdContractsListResidual:
    """cmd_contracts_list 残余分支覆盖。"""

    def test_fallback_skip_registry_dir(self, monkeypatch, tmp_path):
        """registry.json 为目录→fallback 循环跳过 (line 183)"""
        capture = Console(record=True, force_terminal=True, width=140)
        monkeypatch.setattr(cli, "console", capture)

        docs_dir = tmp_path / "docs" / "contracts"
        docs_dir.mkdir(parents=True)
        (docs_dir / "workspace-object.schema.json").write_text(
            json.dumps(
                {
                    "title": "WS",
                    "description": "Standard object",
                }
            )
        )

        eidos_dir = tmp_path / "eidos" / "schemas"
        eidos_dir.mkdir(parents=True)
        # registry.json AS a directory → is_file() returns False → fallback path
        (eidos_dir / "registry.json").mkdir()
        (eidos_dir / "custom.json").write_text(
            json.dumps(
                {
                    "title": "Custom",
                    "description": "A custom schema",
                }
            )
        )

        monkeypatch.setattr("cockpit.commands.contracts._workspace_root", lambda: tmp_path)

        from cockpit.commands.contracts import cmd_contracts_list

        code = cmd_contracts_list(argparse.Namespace())

        output = capture.export_text()
        assert code == 0
        assert "workspace-object" in output
        assert "custom" in output
        # No error — registry.json directory was skipped


# ═══════════════════════════════════════════════════════════════════════════════
# cmd_contracts_export_research 补充 — parent/child + envelope 失败 + OSError
# ═══════════════════════════════════════════════════════════════════════════════


class TestCmdContractsExportResearchResidual:
    """cmd_contracts_export_research 残余分支覆盖。"""

    def test_with_relations(self, monkeypatch, tmp_path):
        """研究中含 parent/child 关系→relations 正确生成 (lines 40, 42)"""
        capture = Console(record=True, force_terminal=True, width=140)
        monkeypatch.setattr(cli, "console", capture)
        mock_da = MockDataAccess()
        mock_da.get_research = lambda rid: {
            "id": 1,
            "topic": "related",
            "created_at": 1700000000.0,
            "source_count": 2,
            "summary": "s",
            "full_text": "body",
            "follow_ups": [],
            "tags": [],
            "archived_at": None,
            "quarantined_at": None,
        }
        mock_da.get_research_timeline = lambda rid: []
        mock_da.get_research_dossier = lambda rid: {
            "parents": [{"id": 10, "relation_type": "derived_from"}],
            "children": [{"id": 20, "relation_type": "derived_to"}],
        }
        monkeypatch.setattr(cli, "get_data_access", lambda: mock_da)

        output_path = tmp_path / "exported.json"
        from cockpit.commands.contracts import cmd_contracts_export_research

        code = cmd_contracts_export_research(argparse.Namespace(research_id="1", output=str(output_path)))

        assert code == 0
        data = json.loads(output_path.read_text())
        assert len(data["relations"]) == 2
        assert data["relations"][0] == {
            "type": "derived_from",
            "target_id": "research:10",
            "target_type": "research_object",
        }
        assert data["relations"][1] == {
            "type": "derived_to",
            "target_id": "research:20",
            "target_type": "research_object",
        }

    def test_envelope_validation_fails(self, monkeypatch):
        """导出的对象不满足 envelope→报错 (lines 201-204)"""
        err = Console(record=True, force_terminal=True, width=140)
        monkeypatch.setattr(cli, "err", err)
        mock_da = MockDataAccess()
        mock_da.get_research = lambda rid: {
            "id": 1,
            "topic": "test",
            "created_at": 1700000000.0,
            "source_count": 2,
            "summary": "s",
            "full_text": "body",
            "follow_ups": [],
            "tags": [],
            "archived_at": None,
            "quarantined_at": None,
        }
        mock_da.get_research_timeline = lambda rid: []
        mock_da.get_research_dossier = lambda rid: {}
        monkeypatch.setattr(cli, "get_data_access", lambda: mock_da)

        # Force envelope validation to fail
        monkeypatch.setattr("cockpit.commands.contracts._validate_workspace_object_envelope", lambda data: ["fake issue"])

        from cockpit.commands.contracts import cmd_contracts_export_research

        code = cmd_contracts_export_research(argparse.Namespace(research_id="1", output=None))

        output = err.export_text()
        assert code == 2
        assert "未满足 envelope" in output

    def test_os_error_on_write(self, monkeypatch, tmp_path):
        """写入时 OSError→捕获 (lines 213-215)"""
        err = Console(record=True, force_terminal=True, width=140)
        monkeypatch.setattr(cli, "err", err)
        mock_da = MockDataAccess()
        mock_da.get_research = lambda rid: {
            "id": 1,
            "topic": "test",
            "created_at": 1700000000.0,
            "source_count": 2,
            "summary": "s",
            "full_text": "body",
            "follow_ups": [],
            "tags": [],
            "archived_at": None,
            "quarantined_at": None,
        }
        mock_da.get_research_timeline = lambda rid: []
        mock_da.get_research_dossier = lambda rid: {}
        monkeypatch.setattr(cli, "get_data_access", lambda: mock_da)

        # Parent path is a file → mkdir fails
        output_path = tmp_path / "subdir" / "export.json"
        (tmp_path / "subdir").write_text("blocking file")

        from cockpit.commands.contracts import cmd_contracts_export_research

        code = cmd_contracts_export_research(argparse.Namespace(research_id="1", output=str(output_path)))

        output = err.export_text()
        assert code == 1
        assert "写入失败" in output

    def test_relative_output_path(self, monkeypatch, tmp_path):
        """相对路径→正确解析 (line 209)"""
        capture = Console(record=True, force_terminal=True, width=140)
        monkeypatch.setattr(cli, "console", capture)
        mock_da = MockDataAccess()
        mock_da.get_research = lambda rid: {
            "id": 1,
            "topic": "rel-path",
            "created_at": 1700000000.0,
            "source_count": 2,
            "summary": "s",
            "full_text": "body",
            "follow_ups": [],
            "tags": [],
            "archived_at": None,
            "quarantined_at": None,
        }
        mock_da.get_research_timeline = lambda rid: []
        mock_da.get_research_dossier = lambda rid: {}
        monkeypatch.setattr(cli, "get_data_access", lambda: mock_da)

        monkeypatch.chdir(tmp_path)
        from cockpit.commands.contracts import cmd_contracts_export_research

        code = cmd_contracts_export_research(argparse.Namespace(research_id="1", output="rel_out.json"))

        assert code == 0
        assert (tmp_path / "rel_out.json").exists()


# ═══════════════════════════════════════════════════════════════════════════════
# cmd_contracts_export_identity 补充 — 相对路径 + OSError (234, 238-240)
# ═══════════════════════════════════════════════════════════════════════════════


class TestCmdContractsExportIdentityResidual:
    """cmd_contracts_export_identity 残余分支覆盖。"""

    def test_os_error_on_write(self, monkeypatch, tmp_path):
        """写入时 OSError→捕获 (lines 238-240)"""
        err = Console(record=True, force_terminal=True, width=140)
        monkeypatch.setattr(cli, "err", err)
        monkeypatch.setattr("cockpit.commands.base._PROFILE_PATH", tmp_path / "persona.yaml")

        output_path = tmp_path / "subdir" / "ident.json"
        (tmp_path / "subdir").write_text("blocking file")

        from cockpit.commands.contracts import cmd_contracts_export_identity

        code = cmd_contracts_export_identity(argparse.Namespace(output=str(output_path)))

        output = err.export_text()
        assert code == 1
        assert "写入失败" in output

    def test_relative_output_path(self, monkeypatch, tmp_path):
        """相对路径→正确解析 (line 234)"""
        capture = Console(record=True, force_terminal=True, width=140)
        monkeypatch.setattr(cli, "console", capture)
        monkeypatch.setattr("cockpit.commands.base._PROFILE_PATH", tmp_path / "persona.yaml")

        monkeypatch.chdir(tmp_path)
        from cockpit.commands.contracts import cmd_contracts_export_identity

        code = cmd_contracts_export_identity(argparse.Namespace(output="rel_ident.json"))

        assert code == 0
        assert (tmp_path / "rel_ident.json").exists()


# ═══════════════════════════════════════════════════════════════════════════════
# cmd_contracts_export_event 补充 — 相对路径 + OSError (267, 271-273)
# ═══════════════════════════════════════════════════════════════════════════════


class TestCmdContractsExportEventResidual:
    """cmd_contracts_export_event 残余分支覆盖。"""

    def test_os_error_on_write(self, monkeypatch, tmp_path):
        """写入时 OSError→捕获 (lines 271-273)"""
        err = Console(record=True, force_terminal=True, width=140)
        monkeypatch.setattr(cli, "err", err)
        mock_da = MockDataAccess()
        mock_da.get_research_timeline = lambda rid: [{"created_at": 1700000000, "event_type": "created"}]
        monkeypatch.setattr(cli, "get_data_access", lambda: mock_da)

        output_path = tmp_path / "subdir" / "events.json"
        (tmp_path / "subdir").write_text("blocking file")

        from cockpit.commands.contracts import cmd_contracts_export_event

        code = cmd_contracts_export_event(argparse.Namespace(id=1, output=str(output_path)))

        output = err.export_text()
        assert code == 1
        assert "写入失败" in output

    def test_relative_output_path(self, monkeypatch, tmp_path):
        """相对路径→正确解析 (line 267)"""
        capture = Console(record=True, force_terminal=True, width=140)
        monkeypatch.setattr(cli, "console", capture)
        mock_da = MockDataAccess()
        mock_da.get_research_timeline = lambda rid: [{"created_at": 1700000000, "event_type": "created"}]
        monkeypatch.setattr(cli, "get_data_access", lambda: mock_da)

        monkeypatch.chdir(tmp_path)
        from cockpit.commands.contracts import cmd_contracts_export_event

        code = cmd_contracts_export_event(argparse.Namespace(id=1, output="rel_events.json"))

        assert code == 0
        assert (tmp_path / "rel_events.json").exists()
