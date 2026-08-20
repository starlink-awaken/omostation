"""能力全景覆盖新命令单元测试 — knowledge / kems / workflow_mesh / c2g + debt 路由.

这些命令是 PR #784/#791 引入的, 本测试守护其 dispatch + 优雅降级 + 端口冲突诊断.
"""

from __future__ import annotations

import argparse
import os
import sys
from unittest.mock import patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from cockpit.commands import c2g, knowledge, workflow_mesh

# ── knowledge 命令 ─────────────────────────────────────────────


class TestKnowledgeCommand:
    """cockpit knowledge — KOS 知识检索治理."""

    def test_no_subcommand_shows_help(self, capsys):
        """无子命令时显示概览 + 子命令列表, 返回 0."""
        args = argparse.Namespace(knowledge_command=None)
        rc = knowledge.cmd_knowledge(args)
        assert rc == 0
        out = capsys.readouterr().out
        assert "KOS" in out or "知识检索" in out
        assert "search" in out

    def test_search_no_query_returns_error(self, capsys):
        """search 无关键词 → 报错 rc=1."""
        args = argparse.Namespace(knowledge_command="search", query=None, limit=5)
        rc = knowledge.cmd_knowledge(args)
        assert rc == 1

    @patch("cockpit.commands.knowledge._kos_available", return_value=False)
    @patch("cockpit.commands.knowledge._kos_port_conflict", return_value="端口被非 KOS 服务占用")
    def test_search_kos_offline_graceful(self, mock_conflict, mock_avail, capsys):
        """KOS 离线时 search 走本地检索回退并保持可用."""
        args = argparse.Namespace(knowledge_command="search", query="测试", limit=5)
        rc = knowledge.cmd_knowledge(args)
        assert rc == 0
        output = capsys.readouterr().out
        assert "Unified Hybrid" in output or "未找到" in output

    def test_kos_port_conflict_detection(self):
        """端口冲突诊断: 非 KOS 响应应被识别."""
        # 模拟 runtime 抢端口返回的 {"agents":0,"nodes":0}
        with patch("cockpit.commands.knowledge._safe_urlopen") as mock_url:
            import io
            import json

            class _FakeResp:
                def __init__(self, data):
                    self._data = data
                    self.status = 200

                def read(self):
                    return json.dumps(self._data).encode()

            mock_url.return_value.__enter__ = lambda self: _FakeResp({"status": "ok", "agents": 0, "nodes": 0})
            mock_url.return_value.__exit__ = lambda *a: None
            # _kos_available 应返回 False (非 KOS 响应)
            assert knowledge._kos_available() is False


# ── workflow_mesh 命令 ──────────────────────────────────────────


class TestWorkflowMeshCommand:
    """cockpit workflow mesh — 交付事件织网."""

    def test_no_subcommand_shows_help(self, capsys):
        args = argparse.Namespace(mesh_command=None, limit=20)
        rc = workflow_mesh.cmd_workflow_mesh(args)
        assert rc == 0
        out = capsys.readouterr().out
        assert "Workflow Mesh" in out or "delivery" in out

    def test_status_no_events(self, capsys):
        """无事件文件时 status 不崩溃."""
        with patch("cockpit.commands.workflow_mesh._read_events", return_value=[]):
            args = argparse.Namespace(mesh_command="status")
            rc = workflow_mesh.cmd_mesh_status(args)
            assert rc == 0

    def test_delivery_aggregates_tracks(self):
        """delivery 正确统计 track 分布 + 治理占比."""
        fake_events = [
            {"track": "governance"},
            {"track": "governance"},
            {"track": "flex"},
            {"track": "collaboration"},
        ]
        with patch("cockpit.commands.workflow_mesh._read_events", return_value=fake_events):
            args = argparse.Namespace(mesh_command="delivery")
            rc = workflow_mesh.cmd_mesh_delivery(args)
            assert rc == 0  # 50% 治理占比, 应输出但 rc=0

    def test_delivery_low_governance_passes(self, capsys):
        """治理占比 ≤40% 时应输出达标."""
        fake_events = [{"track": "flex"}] * 10  # 0% 治理
        with patch("cockpit.commands.workflow_mesh._read_events", return_value=fake_events):
            args = argparse.Namespace(mesh_command="delivery")
            rc = workflow_mesh.cmd_mesh_delivery(args)
            assert rc == 0
            out = capsys.readouterr().out
            assert "达标" in out


# ── c2g 命令 ────────────────────────────────────────────────────


class TestC2GCommand:
    """cockpit c2g — C2G 战略罗盘全局状态."""

    def test_no_subcommand_shows_help(self, capsys):
        args = argparse.Namespace(c2g_command=None)
        rc = c2g.cmd_c2g(args)
        assert rc == 0
        out = capsys.readouterr().out
        assert "C2G" in out

    def test_pipeline_shows_all_stages(self, capsys):
        """pipeline 应展示 V2P/C2G/AGC/Wave2 四阶段."""
        args = argparse.Namespace(c2g_command="pipeline")
        rc = c2g.cmd_c2g_pipeline(args)
        assert rc == 0
        out = capsys.readouterr().out
        assert "V2P" in out
        assert "AGC" in out
        assert "compass" in out

    @patch("cockpit.commands.c2g.subprocess.run")
    def test_status_delegates_to_c2g_radar(self, mock_run):
        """status 委派到 c2g radar 子命令."""
        mock_run.return_value = argparse.Namespace(returncode=0)
        args = argparse.Namespace(c2g_command="status")
        rc = c2g.cmd_c2g_status(args)
        assert rc == 0
        # 确认调了 subprocess
        assert mock_run.called


# ── debt 路由 (PR #784 修复) ────────────────────────────────────


class TestDebtDispatch:
    """cockpit debt 子命令路由 — score → 评分, 其他 → omo debt."""

    def test_debt_score_routes_to_scoring(self):
        """debt score 路由目标 cmd_debt_score 可正常执行."""
        from cockpit.commands import debt_scoring

        # _dispatch_debt 是 cli.py main() 内的闭包, 这里直接验证路由目标可调
        args = argparse.Namespace(
            debt_subcommand="score", impact=5, frequency=5, cost=5, stage="stable_growth", list_stages=False
        )
        rc = debt_scoring.cmd_debt_score(args)
        assert rc == 0


# ── kems 命令 ───────────────────────────────────────────────────


class TestKemsCommand:
    """cockpit kems — KEMS 域治理."""

    def test_no_subcommand_shows_help(self, capsys):
        from cockpit.commands import kems

        args = argparse.Namespace(kems_command=None)
        rc = kems.cmd_kems(args)
        assert rc == 0
        out = capsys.readouterr().out
        assert "KEMS" in out
        assert "domains" in out

    def test_domains_uses_governance_adapter(self, monkeypatch, capsys):
        """domains 从治理适配器读取正式 L4 registry 投影。"""
        from cockpit.commands import kems

        called = []
        monkeypatch.setattr(
            kems.governance_context,
            "domains_list",
            lambda: (
                called.append(True)
                or {
                    "status": "ok",
                    "available": True,
                    "total": 1,
                    "domains": [
                        {
                            "id": "vault",
                            "name": "@学习进化",
                            "type": "document",
                            "path": "/tmp/vault",
                            "bos_uri": "bos://vault/**",
                            "capabilities": ["knowledge.read"],
                            "exists": True,
                        }
                    ],
                }
            ),
        )

        rc = kems.cmd_kems_domains(argparse.Namespace(kems_command="domains"))

        assert rc == 0
        assert called == [True]
        output = capsys.readouterr().out
        assert "@学习进化" in output
        assert "bos://vault/**" in output

    def test_status_uses_governance_adapter_and_reports_degraded(self, monkeypatch, capsys):
        from cockpit.commands import kems

        monkeypatch.setattr(
            kems.governance_context,
            "kems_status",
            lambda: {
                "status": "degraded",
                "available": True,
                "documents_root": "/tmp/Documents",
                "domains": {"status": "ok", "total": 12},
                "content_audit": {
                    "status": "not_run",
                    "reason": "full Documents content audit is on-demand; run cockpit kems scan",
                },
                "owners": {"omo": {"status": "ok"}, "kairon": {"status": "unavailable"}},
            },
        )

        rc = kems.cmd_kems_status(argparse.Namespace(kems_command="status"))

        assert rc == 1
        output = capsys.readouterr().out
        assert "degraded" in output
        assert "cockpit kems scan" in output


class TestHealthCommand:
    """cockpit health --full — 人类输出必须与退出码一致。"""

    def test_full_health_degraded_does_not_print_green_success(self, monkeypatch, tmp_path, capsys):
        from cockpit.commands import health, l4bridge

        monkeypatch.setenv("WORKSPACE_ROOT", str(tmp_path))
        monkeypatch.setattr(l4bridge, "cmd_context", lambda _args: 0)
        monkeypatch.setattr(health, "_get_l4_registry", lambda: None)
        monkeypatch.setattr(
            health.governance_context,
            "workspace_context",
            lambda: {
                "status": "ok",
                "phase": 49,
                "theme": "Documents 内容主权收敛",
                "cards_summary": {"active": 0, "p0_open": 0},
            },
        )
        monkeypatch.setattr(
            health.governance_context,
            "kems_status",
            lambda: {
                "status": "degraded",
                "domains": {"status": "ok", "total": 12},
                "content_audit": {"status": "degraded", "violations": [{"code": "L4-CONTENT-001"}]},
            },
        )

        rc = health._cmd_health(argparse.Namespace(full=True, json=False))

        assert rc == 1
        output = capsys.readouterr().out
        assert "✅ 全栈健康检查完成" not in output
        assert "存在异常" in output
