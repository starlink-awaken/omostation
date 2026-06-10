"""测试追问(--ask)、搜索(--search)、打开(--open)命令的场景。

场景覆盖：
1. cmd_research_ask — 6 条路径（研究不存在、minerva 成功、minerva 失败→ollama、
   minerva 失败→ollama 失败→本地缓存、minerva 缺失→ollama、minerva 缺失→ollama 失败→本地缓存）
2. cmd_research_search — 4 条路径（空关键词、无结果、有结果、FTS 异常）
3. cmd_research_open — 3 条路径（不存在、存在无追问、存在有追问）
"""

from __future__ import annotations

import argparse
import subprocess

from rich.console import Console

from cockpit import cli
from cockpit.tests.conftest import MockDataAccess

# ── Mock helpers ──


def _patch_base(monkeypatch, attrs: dict):
    from cockpit.commands import base as _base_mod

    for name, value in attrs.items():
        monkeypatch.setattr(_base_mod, name, value)


def _patch_research_mod(monkeypatch, attrs: dict):
    from cockpit.commands import research as _research_mod

    for name, value in attrs.items():
        monkeypatch.setattr(_research_mod, name, value)


def _make_research(**overrides) -> dict:
    return {
        "id": 42,
        "topic": "test topic",
        "created_at": 1748426400.0,
        "source_count": 3,
        "summary": "研究摘要",
        "full_text": "研究全文内容",
        "follow_ups": [],
        **overrides,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# cmd_research_ask — 追问场景 (6 条路径)
# ═══════════════════════════════════════════════════════════════════════════════


class TestCmdResearchAsk:
    """追问流程的三级降级链测试。"""

    def _setup(self, monkeypatch, research=None, **kwargs):
        capture = Console(record=True, force_terminal=True, width=140)
        monkeypatch.setattr(cli, "console", capture)
        monkeypatch.setattr(cli, "err", capture)
        mock = MockDataAccess()
        if research:
            mock.get_research = lambda rid: research
            mock.add_follow_up = lambda rid, q, a: None
        _patch_base(
            monkeypatch,
            {
                "_research_progress": lambda task: None,
                "_notify_research_complete": lambda topic: None,
                **{k: v for k, v in kwargs.items() if k.startswith("_")},
            },
        )
        # 同时修补 research 模块上的 _find_cli（module-level import 问题）
        if "_find_cli" in kwargs:
            _patch_research_mod(monkeypatch, {"_find_cli": kwargs["_find_cli"]})
        monkeypatch.setattr(cli, "get_data_access", lambda: mock)
        return capture, mock

    # ── 路径 1：研究不存在 ──

    def test_research_not_found(self, monkeypatch):
        """追问不存在的 ID→显示错误"""
        capture, _ = self._setup(monkeypatch)
        code = cli.cmd_research_ask(argparse.Namespace(research_id=999, question=["why?"]))
        output = capture.export_text()
        assert code == 1
        assert "未找到" in output
        assert "999" in output

    def test_research_not_found_with_recent(self, monkeypatch):
        """追问不存在的 ID，但有最近研究→提示含最近记录 (lines 212-213)"""
        capture = Console(record=True, force_terminal=True, width=140)
        monkeypatch.setattr(cli, "console", capture)
        monkeypatch.setattr(cli, "err", capture)
        mock = MockDataAccess()
        mock.get_research = lambda rid: None
        mock.list_research = lambda limit=3: [
            {"id": 1, "topic": "Existing Research"},
            {"id": 2, "topic": "Another Topic"},
        ]
        monkeypatch.setattr(cli, "get_data_access", lambda: mock)

        code = cli.cmd_research_ask(argparse.Namespace(research_id=999, question=["why?"]))
        output = capture.export_text()
        assert code == 1
        assert "未找到" in output
        assert "999" in output
        assert "Existing Research" in output
        assert "Another Topic" in output

    # ── 路径 2：minerva 存在且成功 → "real" ──

    def test_minerva_success(self, monkeypatch):
        """minerva 可用且执行成功→真实回答"""
        research = _make_research()
        capture, mock = self._setup(
            monkeypatch,
            research=research,
            _notify_research_complete=lambda topic: None,
            _find_cli=lambda name: "/usr/local/bin/minerva",
        )
        # Mock minerva subprocess to succeed
        _patch_research_mod(
            monkeypatch,
            {
                "subprocess": type(
                    "_FakeSubprocess",
                    (),
                    {
                        "run": lambda *args, **kwargs: subprocess.CompletedProcess(
                            args=["minerva"],
                            returncode=0,
                            stdout="这是 minerva 的真实研究回答内容。",
                            stderr="",
                        ),
                        "CompletedProcess": subprocess.CompletedProcess,
                    },
                )(),
            },
        )
        code = cli.cmd_research_ask(argparse.Namespace(research_id=42, question=["为什么", "Transformer", "重要？"]))
        output = capture.export_text()
        assert code == 0
        assert "真实研究" in output
        assert "minerva" in output or "为什么" in output

    # ── 路径 3：minerva 存在但失败 → ollama 降级成功 ──

    def test_minerva_fails_ollama_succeeds(self, monkeypatch):
        """minerva 失败后 ollama 降级成功→ollama 回复"""
        research = _make_research()
        capture, mock = self._setup(
            monkeypatch,
            research=research,
            _find_cli=lambda name: "/usr/local/bin/minerva",
        )
        _patch_research_mod(
            monkeypatch,
            {
                "subprocess": type(
                    "_FakeSubprocess",
                    (),
                    {
                        "run": lambda *args, **kwargs: subprocess.CompletedProcess(
                            args=["minerva"],
                            returncode=1,
                            stdout="",
                            stderr="ModuleNotFoundError",
                        ),
                        "CompletedProcess": subprocess.CompletedProcess,
                    },
                )(),
                "_run_ollama": lambda prompt, **kw: "ollama 生成的回答内容。",
            },
        )
        code = cli.cmd_research_ask(argparse.Namespace(research_id=42, question=["test"]))
        output = capture.export_text()
        assert code == 0
        assert "ollama 回复" in output

    # ── 路径 4：minerva 存在但失败 + ollama 失败 → 本地缓存降级 ──

    def test_minerva_and_ollama_both_fail(self, monkeypatch):
        """minerva + ollama 均失败→本地缓存回答"""
        research = _make_research()
        capture, mock = self._setup(
            monkeypatch,
            research=research,
            _find_cli=lambda name: "/usr/local/bin/minerva",
        )
        _patch_research_mod(
            monkeypatch,
            {
                "subprocess": type(
                    "_FakeSubprocess",
                    (),
                    {
                        "run": lambda *args, **kwargs: subprocess.CompletedProcess(
                            args=["minerva"],
                            returncode=1,
                            stdout="",
                            stderr="Error",
                        ),
                        "CompletedProcess": subprocess.CompletedProcess,
                    },
                )(),
                "_run_ollama": lambda prompt, **kw: None,
            },
        )
        code = cli.cmd_research_ask(argparse.Namespace(research_id=42, question=["test"]))
        output = capture.export_text()
        assert code == 0
        assert "降级回复" in output
        assert "本地缓存" in output

    # ── 路径 5：minerva 不存在 → ollama 降级成功 ──

    def test_minerva_missing_ollama_succeeds(self, monkeypatch):
        """minerva 缺失，ollama 降级成功→ollama 回复"""
        research = _make_research()
        capture, mock = self._setup(
            monkeypatch,
            research=research,
            _find_cli=lambda name: None,
        )
        _patch_research_mod(
            monkeypatch,
            {
                "_run_ollama": lambda prompt, **kw: "ollama 生成的回答内容。",
            },
        )
        code = cli.cmd_research_ask(argparse.Namespace(research_id=42, question=["test"]))
        output = capture.export_text()
        assert code == 0
        assert "ollama 回复" in output

    # ── 路径 6：minerva 不存在 + ollama 失败 → 本地缓存降级 ──

    def test_minerva_missing_ollama_fails(self, monkeypatch):
        """minerva 缺失 + ollama 失败→本地缓存回答"""
        research = _make_research()
        capture, mock = self._setup(
            monkeypatch,
            research=research,
            _find_cli=lambda name: None,
        )
        _patch_research_mod(
            monkeypatch,
            {
                "_run_ollama": lambda prompt, **kw: None,
            },
        )
        code = cli.cmd_research_ask(argparse.Namespace(research_id=42, question=["test"]))
        output = capture.export_text()
        assert code == 0
        assert "降级回复" in output
        assert "本地缓存" in output


# ═══════════════════════════════════════════════════════════════════════════════
# cmd_research_search — 搜索场景 (4 条路径)
# ═══════════════════════════════════════════════════════════════════════════════


class TestCmdResearchSearch:
    """研究搜索路径测试。"""

    def test_empty_keyword(self, monkeypatch):
        """空关键词→错误提示"""
        capture = Console(record=True, force_terminal=True, width=140)
        monkeypatch.setattr(cli, "console", capture)
        monkeypatch.setattr(cli, "err", capture)
        monkeypatch.setattr(cli, "get_data_access", lambda: MockDataAccess())
        code = cli.cmd_research_search(argparse.Namespace(search="", limit=10))
        assert code == 1
        assert "请指定搜索关键词" in capture.export_text()

    def test_no_results(self, monkeypatch):
        """无匹配结果→友好提示"""
        capture = Console(record=True, force_terminal=True, width=140)
        monkeypatch.setattr(cli, "console", capture)
        monkeypatch.setattr(cli, "err", capture)
        mock = MockDataAccess()
        mock.search_research = lambda keyword, limit=10: []
        monkeypatch.setattr(cli, "get_data_access", lambda: mock)
        code = cli.cmd_research_search(argparse.Namespace(search="xyz", limit=10))
        assert code == 0
        assert "没有找到匹配" in capture.export_text()

    def test_has_results(self, monkeypatch):
        """有搜索结果→表格渲染"""
        capture = Console(record=True, force_terminal=True, width=140)
        monkeypatch.setattr(cli, "console", capture)
        monkeypatch.setattr(cli, "err", capture)
        mock = MockDataAccess()
        mock.search_research = lambda keyword, limit=10: [
            {
                "id": 1,
                "topic": "AI",
                "created_at": 1748426400.0,
                "source_count": 2,
                "summary": "关于 AI 的研究",
                "snippet": "AI...",
            },
        ]
        monkeypatch.setattr(cli, "get_data_access", lambda: mock)
        code = cli.cmd_research_search(argparse.Namespace(search="AI", limit=10))
        output = capture.export_text()
        assert code == 0
        assert "AI" in output
        assert "研究全文搜索" in output

    def test_fts_error_returns_empty(self, monkeypatch):
        """FTS 搜索引擎异常→返回空列表"""
        import sqlite3

        capture = Console(record=True, force_terminal=True, width=140)
        monkeypatch.setattr(cli, "console", capture)
        monkeypatch.setattr(cli, "err", capture)
        mock = MockDataAccess()
        mock.search_research = lambda keyword, limit=10: (_ for _ in ()).throw(
            sqlite3.OperationalError("FTS table not found")
        )

        monkeypatch.setattr(cli, "get_data_access", lambda: mock)

        code = cli.cmd_research_search(argparse.Namespace(search="broken", limit=10))
        output = capture.export_text()
        assert code == 0
        assert "没有找到匹配" in output


# ═══════════════════════════════════════════════════════════════════════════════
# cmd_research_open — 研究查看场景 (3 条路径)
# ═══════════════════════════════════════════════════════════════════════════════


class TestCmdResearchOpen:
    """研究打开/查看场景测试。"""

    def test_not_found(self, monkeypatch):
        """ID 不存在→错误提示含最近研究"""
        capture = Console(record=True, force_terminal=True, width=140)
        monkeypatch.setattr(cli, "console", capture)
        monkeypatch.setattr(cli, "err", capture)
        mock = MockDataAccess()
        mock.get_research = lambda rid: None
        mock.list_research = lambda **kw: [
            {"id": 1, "topic": "Existing Research"},
        ]
        monkeypatch.setattr(cli, "get_data_access", lambda: mock)
        code = cli.cmd_research_open(argparse.Namespace(research_id=999))
        output = capture.export_text()
        assert code == 1
        assert "未找到" in output
        assert "Existing Research" in output

    def test_found_no_followups(self, monkeypatch):
        """研究存在，无追问→显示全文"""
        capture = Console(record=True, force_terminal=True, width=140)
        monkeypatch.setattr(cli, "console", capture)
        monkeypatch.setattr(cli, "err", capture)
        mock = MockDataAccess()
        mock.get_research = lambda rid: _make_research()
        mock.list_research = lambda **kw: []
        monkeypatch.setattr(cli, "get_data_access", lambda: mock)
        code = cli.cmd_research_open(argparse.Namespace(research_id=42))
        output = capture.export_text()
        assert code == 0
        assert "test topic" in output
        assert "研究全文内容" in output

    def test_found_with_followups(self, monkeypatch):
        """研究存在且有追问→显示追问表格"""
        capture = Console(record=True, force_terminal=True, width=140)
        monkeypatch.setattr(cli, "console", capture)
        monkeypatch.setattr(cli, "err", capture)
        mock = MockDataAccess()
        mock.get_research = lambda rid: _make_research(
            follow_ups=[
                {"timestamp": 1748426400.0, "question": "为什么重要？", "answer": "因为它是基础。"},
                {"timestamp": 1748426500.0, "question": "有什么应用？", "answer": "NLP, CV 等。"},
            ]
        )
        mock.list_research = lambda **kw: []
        monkeypatch.setattr(cli, "get_data_access", lambda: mock)
        code = cli.cmd_research_open(argparse.Namespace(research_id=42))
        output = capture.export_text()
        assert code == 0
        assert "为什么重要" in output
        assert "NLP, CV" in output

    def test_open_json(self, monkeypatch):
        """--open --json 输出 JSON"""
        capture = Console(record=True, force_terminal=True, width=140)
        monkeypatch.setattr(cli, "console", capture)
        mock = MockDataAccess()
        mock.get_research = lambda rid: _make_research()
        monkeypatch.setattr(cli, "get_data_access", lambda: mock)
        code = cli.cmd_research_open(argparse.Namespace(research_id=42, json=True))
        output = capture.export_text()
        assert code == 0
        assert '"id": 42' in output
        assert '"topic": "test topic"' in output
        assert '"full_text": "研究全文内容"' in output
