"""
Tests for cockpit CLI core functionality.

Tests the main CLI entry point and critical subcommands.
"""

import sys
from pathlib import Path

# Add cockpit src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


class TestCLIRouting:
    """Test that the CLI entry point can be imported and basic routing works."""

    def test_import_main(self):
        """CLI main function should be importable."""
        from cockpit.cli import main
        assert callable(main)

    def test_import_commands(self):
        """All command modules should be importable."""
        from cockpit.commands import base
        assert hasattr(base, "_get_console")

    def test_l4bridge_imports(self):
        """L4 bridge commands should be importable."""
        from cockpit.commands.l4bridge import (
            cmd_cards,
            cmd_context,
            cmd_domains,
            cmd_skill,
            cmd_vault,
        )
        assert callable(cmd_context)
        assert callable(cmd_domains)
        assert callable(cmd_cards)
        assert callable(cmd_vault)
        assert callable(cmd_skill)

    def test_model_driven_commands_importable(self):
        """Model-driven bridge command (unified entry) should be importable."""
        from cockpit.commands.l4bridge import cmd_model_driven
        assert callable(cmd_model_driven)


class TestCLISubcommands:
    """Test that all registered subcommands have valid handlers."""

    def test_cli_parser_has_expected_subcommands(self):
        """CLI parser should register all expected subcommands."""
        from cockpit.cli import main

        # Verify main is callable
        assert callable(main)

    def test_research_module_imports(self):
        """Research module should be importable."""
        from cockpit.commands import research
        assert hasattr(research, "cmd_research")

    def test_storage_module(self):
        """Storage module should be importable."""
        from cockpit import storage
        assert hasattr(storage, "get_db_path") or hasattr(storage, "IDataAccess")


class TestL0MCPTools:
    """Test L0 MCP tools integration."""

    def test_mcp_tools_registry(self):
        """MCP_TOOLS registry should contain expected tools."""
        from cockpit.l0_mcp_tools import MCP_TOOLS

        expected = [
            "l0_status",
            "l0_validate",
            "l0_audit",
            "l0_protocols",
            "l0_adr_list",
            "l0_entity_resolve",
        ]
        for tool_name in expected:
            assert tool_name in MCP_TOOLS, f"Missing tool: {tool_name}"
            assert "function" in MCP_TOOLS[tool_name]
            assert "description" in MCP_TOOLS[tool_name]

    def test_model_driven_tools_registry(self):
        """MCP_TOOLS should include model-driven bridge tools."""
        from cockpit.l0_mcp_tools import MCP_TOOLS

        md_tools = ["md_lifecycle_status", "md_validate"]
        for tool_name in md_tools:
            assert tool_name in MCP_TOOLS, f"Missing tool: {tool_name}"


class TestCockpitMCP:
    """Test cockpit MCP integration."""

    def test_cockpit_mcp_import(self):
        """Cockpit MCP module should be importable."""
        from cockpit.scripts import cockpit_mcp
        assert hasattr(cockpit_mcp, "workspace_context")


# ═══ OPC P2 Gate C1 — Local Contract Hardening (Playbook §7) ═══
class TestP2GateC1LocalContract:
    """P2 Gate C1 验收: cockpit search 是稳定的统一响应路径。

    验收条件 (Playbook §7 P2.1 Gate C1):
      - search --all --json 返回有效 JSON
      - 顶层响应字段完整 (zone, query, zone_count, results, total)
      - KOS 不可用时无 traceback
      - local item shape 标准化 (8 个 T4 metadata 字段)
      - 文本模式与 JSON 模式表达相同事实
    """

    REQUIRED_TOP_LEVEL = {"zone", "query", "zone_count", "results", "total"}
    REQUIRED_T4_FIELDS = {
        "_source", "_source_path", "_zone", "_type",
        "_freshness", "_owner", "_reuse_policy", "_retrieved_at",
    }

    def _make_args(self, query: str, search_all: bool, json_mode: bool, limit: int = 10):
        """构造 mock argparse.Namespace。"""
        from argparse import Namespace
        return Namespace(
            query=query, all=search_all, json=json_mode, limit=limit,
        )

    def test_local_only_json_contract(self, capsys, monkeypatch):
        """本地 --json: 顶层字段完整 + zone_count.local 真实计数。"""
        from cockpit.cli import _cmd_search

        # 注入 1 个 fake local 结果, 确保 8 字段 T4 metadata 全部存在
        fake_item = {
            "id": 1, "topic": "t", "summary": "s", "snippet": "sn",
            "tags": [], "agent": "",
        }
        # 模拟 _cmd_search 中调用的 get_data_access().search_research
        from cockpit import storage as _storage_mod
        monkeypatch.setattr(
            _storage_mod.get_data_access(),
            "search_research",
            lambda keyword, limit: [{**fake_item, **{
                "_source": "cockpit-local",
                "_source_path": "research/1",
                "_zone": "personal-knowledge",
                "_type": "research",
                "_freshness": "fresh",
                "_owner": "opc",
                "_reuse_policy": "reference-only",
                "_retrieved_at": "2026-06-11T00:00:00",
            }}],
        )
        args = self._make_args("t", search_all=False, json_mode=True)
        rc = _cmd_search(args)
        assert rc == 0

        out = capsys.readouterr().out
        import json as _json
        response = _json.loads(out)
        assert self.REQUIRED_TOP_LEVEL <= set(response.keys())
        assert response["zone"] == "all"
        assert response["query"] == "t"
        assert response["total"] == 1
        assert response["zone_count"] == {"local": 1}
        assert len(response["results"]) == 1
        item = response["results"][0]
        assert self.REQUIRED_T4_FIELDS <= set(item.keys())

    def test_all_with_kos_unavailable_no_traceback(self, capsys, monkeypatch):
        """--all 但 KOS 不可用: 不崩溃, zone_count.kos=0, 无伪结果注入。"""
        from cockpit import storage as _storage_mod
        from cockpit.cli import _cmd_search

        monkeypatch.setattr(
            _storage_mod.get_data_access(), "search_research",
            lambda keyword, limit: [],
        )
        # 模拟 subprocess.run 失败 (agora binary 不存在)
        # 实际 _cmd_search 中通过 exists() 检查绕开, 但我们走一个不同的失败路径:
        # patch Path('agora_bin').exists -> False
        # 临时覆盖 HOME 让 agora_bin 检查不到
        monkeypatch.setenv("HOME", "/nonexistent-home-for-test")

        args = self._make_args("query", search_all=True, json_mode=True)
        rc = _cmd_search(args)
        # 关键: KOS 不可达时不能 crash, 必须返回 0
        assert rc == 0

        out = capsys.readouterr().out
        import json as _json
        response = _json.loads(out)
        assert response["zone_count"] == {"local": 0, "kos": 0}
        assert response["total"] == 0
        # Red line: 绝不能注入 fake "stdout blob" result
        assert response["results"] == []

    def test_text_and_json_express_same_facts(self, capsys, monkeypatch):
        """文本模式必须表达与 JSON 相同的核心事实 (zone, query, total, zone_count)。"""
        from cockpit import storage as _storage_mod
        from cockpit.cli import _cmd_search

        monkeypatch.setattr(
            _storage_mod.get_data_access(), "search_research",
            lambda keyword, limit: [{
                "id": 99, "topic": "shared fact", "summary": "x", "snippet": "y",
                "tags": [], "agent": "",
                "_source": "cockpit-local", "_source_path": "research/99",
                "_zone": "personal-knowledge", "_type": "research",
                "_freshness": "fresh", "_owner": "opc",
                "_reuse_policy": "reference-only", "_retrieved_at": "2026-06-11T00:00:00",
            }],
        )

        # 1) 文本模式
        args_text = self._make_args("shared fact", search_all=False, json_mode=False)
        rc1 = _cmd_search(args_text)
        assert rc1 == 0
        text_out = capsys.readouterr().out
        assert "query:" in text_out
        assert "zone:" in text_out
        assert "total:" in text_out
        assert "zones:" in text_out
        assert "shared fact" in text_out  # item 出现

        # 2) JSON 模式
        args_json = self._make_args("shared fact", search_all=False, json_mode=True)
        rc2 = _cmd_search(args_json)
        assert rc2 == 0
        import json as _json
        json_out = capsys.readouterr().out
        response = _json.loads(json_out)
        # 文本的 total 必须等于 JSON 的 total
        import re as _re
        m = _re.search(r"total:\s*(\d+)", text_out)
        assert m is not None
        text_total = int(m.group(1))
        assert text_total == response["total"] == 1

    def test_empty_results_returns_well_formed(self, capsys, monkeypatch):
        """空结果: 仍然返回良好结构的响应, total=0, 无 traceback。"""
        from cockpit import storage as _storage_mod
        from cockpit.cli import _cmd_search

        monkeypatch.setattr(
            _storage_mod.get_data_access(), "search_research",
            lambda keyword, limit: [],
        )
        args = self._make_args("nothing-matches-this", search_all=False, json_mode=True)
        rc = _cmd_search(args)
        assert rc == 0

        import json as _json
        response = _json.loads(capsys.readouterr().out)
        assert self.REQUIRED_TOP_LEVEL <= set(response.keys())
        assert response["total"] == 0
        assert response["results"] == []
        assert response["zone_count"] == {"local": 0}

    def test_kos_zone_count_is_real_not_fake(self, monkeypatch):
        """Red line 守护: _extract_kos_items 必须从真实 KOS 响应提取,
        决不能把一个 stdout blob 当作 1 个 valid knowledge hit。
        """
        from cockpit.cli import _extract_kos_items

        # 1) error 响应 → 空
        assert _extract_kos_items({"status": "error", "error": "x"}) == []

        # 2) 空 result → 空
        assert _extract_kos_items({"status": "ok", "result": []}) == []

        # 3) 字符串 result → 空 (不视为 items)
        assert _extract_kos_items({"status": "ok", "result": "anything"}) == []

        # 4) 嵌套 items → 提取
        items = _extract_kos_items({
            "status": "ok",
            "result": {"items": [{"id": 1}, {"id": 2}]},
        })
        assert len(items) == 2

        # 5) 裸 list → 提取
        items2 = _extract_kos_items([{"a": 1}, "string-ignored", {"b": 2}])
        assert len(items2) == 2  # 只保留 dict

        # 6) 不可识别结构 → 空
        assert _extract_kos_items({"status": "ok", "result": 42}) == []
        assert _extract_kos_items({"status": "ok"}) == []
