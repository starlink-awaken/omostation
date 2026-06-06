"""Test cmd_demo — workspace demo 命令全流程场景测试.

覆盖场景:
  - 两次 ollama 均成功（真实研究 + 真实追问）
  - 两次 ollama 均失败（全部演示文本降级）
  - 首次成功 + 追问失败（混合模式）
  - 案卷完整 + 时间线有数据
  - 案卷为 None
  - 时间线为空
  - 已归档的研究对象
"""

from __future__ import annotations

import argparse
from pathlib import Path

from rich.console import Console
from cockpit import cli
from cockpit.tests.conftest import MockDataAccess


def _patch_status_mod(monkeypatch, attrs: dict):
    """Monkeypatch functions in cockpit.commands.status directly.

    cmd_demo 从 .base 通过 from .base import _run_ollama 导入，
    因此需要 patch status 模块的本地引用。
    """
    from cockpit.commands import status as _status_mod

    for name, value in attrs.items():
        monkeypatch.setattr(_status_mod, name, value)


class TestCmdDemo:
    """cmd_demo 完整场景测试。"""

    def _setup(
        self,
        monkeypatch,
        tmp_path,
        data_overrides: dict | None = None,
    ) -> tuple[Console, MockDataAccess]:
        """公共测试基础设施：捕获 console、mock data_access、mock Path.home。"""
        capture = Console(record=True, force_terminal=True, width=140)
        monkeypatch.setattr(cli, "console", capture)
        monkeypatch.setattr(cli, "err", capture)

        # 避免写入真实桌面
        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        mock = MockDataAccess()
        if data_overrides:
            for k, v in data_overrides.items():
                setattr(mock, k, v)
        monkeypatch.setattr(cli, "get_data_access", lambda: mock)

        # 静默进度条
        _patch_status_mod(monkeypatch, {"_research_progress": lambda task: None})

        return capture, mock

    # ── 场景 1: 两次 ollama 均成功 ──────────────────────────────

    def test_ollama_success_both_calls(self, monkeypatch, tmp_path):
        """完整流程：两次 ollama 均成功 → 真实研究 + 真实追问。"""
        ollama_calls: list[str] = []

        def _ollama(prompt, **kw):
            ollama_calls.append(prompt)
            if len(ollama_calls) == 1:
                return (
                    "Transformer 的核心创新是自注意力机制（self-attention），它允许模型在处理序列时关注所有位置的信息。"
                )
            return "因为自注意力机制解决了长距离依赖和并行计算问题。"

        _patch_status_mod(monkeypatch, {"_run_ollama": _ollama})
        capture, _ = self._setup(monkeypatch, tmp_path)

        code = cli.cmd_demo(argparse.Namespace())

        output = capture.export_text()
        assert code == 0
        assert len(ollama_calls) == 2
        assert "ollama（真实）" in output  # demo_mode=False
        assert "（真实）" in output  # demo_ask_degraded=False (not 演示文本)
        assert "（演示文本）" not in output  # 不应该出现演示文本
        assert "✅ 已导入研究对象" in output
        assert "🎮 Workspace 快速演示" in output
        assert "Step 1 / 4" in output
        assert "Step 2 / 4" in output
        assert "Step 3 / 4" in output
        assert "Step 4 / 4" in output
        assert "🎉 演示完成" in output

        # 验证发布文件已在 tmp_path/Desktop/workspace-published/ 创建
        publish_dir = tmp_path / "Desktop" / "workspace-published"
        assert publish_dir.exists()
        files = list(publish_dir.iterdir())
        assert len(files) == 1
        assert "transformer" in files[0].name

    # ── 场景 2: 两次 ollama 均失败 ──────────────────────────────

    def test_ollama_both_fail(self, monkeypatch, tmp_path):
        """全部降级：两次 ollama 均返回 None → 全部使用演示文本。"""
        _patch_status_mod(monkeypatch, {"_run_ollama": lambda prompt, **kw: None})
        capture, _ = self._setup(monkeypatch, tmp_path)

        code = cli.cmd_demo(argparse.Namespace())

        output = capture.export_text()
        assert code == 0
        # 研究来源标记为"演示文本"
        assert "演示文本" in output
        assert "ollama（真实）" not in output
        # 追问回答标记为"（演示文本）"
        assert "（演示文本）" in output
        assert "降级回复" in output
        assert "Step 1 / 4" in output
        assert "✅ 已导入研究对象" in output
        assert "🎉 演示完成" in output

    # ── 场景 3: 首次成功 + 追问失败 ─────────────────────────────

    def test_ollama_success_first_fail_second(self, monkeypatch, tmp_path):
        """混合模式：首次 ollama 成功（真实研究），追问 ollama 再失败（演示追问）。"""
        ollama_calls: list[str] = []

        def _ollama(prompt, **kw):
            ollama_calls.append(prompt)
            if len(ollama_calls) == 1:
                return "真实研究内容：Transformer 的核心创新是自注意力机制。"
            return None  # 追问失败

        _patch_status_mod(monkeypatch, {"_run_ollama": _ollama})
        capture, _ = self._setup(monkeypatch, tmp_path)

        code = cli.cmd_demo(argparse.Namespace())

        output = capture.export_text()
        assert code == 0
        assert len(ollama_calls) == 2
        # 研究来源是真实的
        assert "ollama（真实）" in output
        # 追问是演示文本
        assert "（演示文本）" in output
        assert "降级回复" in output
        assert "✅ 已导入研究对象" in output
        assert "🎉 演示完成" in output

    # ── 场景 4: 案卷完整 + 时间线有数据 ─────────────────────────

    def test_dossier_and_timeline_present(self, monkeypatch, tmp_path):
        """完整案卷和时间线 → 展示摘要和时间线表格。"""
        _patch_status_mod(monkeypatch, {"_run_ollama": lambda prompt, **kw: None})

        dossier = {
            "record": {
                "id": 42,
                "topic": "transformer architecture overview",
                "source_count": 1,
                "archived_at": None,
            },
            "parents": [{"id": 1, "topic": "parent research"}],
            "children": [{"id": 2, "topic": "child research"}],
            "publications": [{"id": 1, "style": "brief", "path": "/tmp/demo.md"}],
        }
        tl_items = [
            {"event_type": "created", "created_at": 1700000000, "description": "研究创建"},
            {"event_type": "follow_up", "created_at": 1700000100, "description": "追问回答"},
        ]

        capture, _ = self._setup(
            monkeypatch,
            tmp_path,
            data_overrides={
                "get_research_dossier": lambda rid: dossier,
                "get_research": lambda rid: {"follow_ups": [{"q": "a"}, {"q": "b"}]},
                "get_research_timeline": lambda rid: tl_items,
                "save_published_report": lambda rid, style, path: 0,
            },
        )

        code = cli.cmd_demo(argparse.Namespace())

        output = capture.export_text()
        assert code == 0
        # 案卷摘要
        assert "📦 研究对象摘要" in output
        assert "42" in output  # ID
        assert "transformer" in output  # topic
        assert "🟢 活跃" in output  # 未归档
        assert "追问: 2 条" in output
        assert "上游研究: 1 条" in output
        assert "派生研究: 1 条" in output
        assert "发布产物: 1 次" in output
        # 时间线表格
        assert "⏱ 研究时间线" in output
        assert "created" in output
        assert "follow_up" in output

    # ── 场景 5: 案卷为 None ─────────────────────────────────────

    def test_dossier_none(self, monkeypatch, tmp_path):
        """无案卷（dossier=None）→ 跳过摘要。"""
        _patch_status_mod(monkeypatch, {"_run_ollama": lambda prompt, **kw: None})
        capture, _ = self._setup(
            monkeypatch,
            tmp_path,
            data_overrides={
                "get_research_dossier": lambda rid: None,
                "get_research_timeline": lambda rid: [],
            },
        )

        code = cli.cmd_demo(argparse.Namespace())

        output = capture.export_text()
        assert code == 0
        assert "📦 研究对象摘要" not in output
        assert "⏱ 研究时间线" not in output
        assert "🎉 演示完成" in output

    # ── 场景 6: 案卷存在但无上下游、无发布 ─────────────────────

    def test_dossier_no_relations(self, monkeypatch, tmp_path):
        """案卷无上下游/无发布 → 摘要仅显示基础信息。"""
        _patch_status_mod(monkeypatch, {"_run_ollama": lambda prompt, **kw: None})

        dossier = {
            "record": {
                "id": 42,
                "topic": "simple topic",
                "source_count": 1,
                "archived_at": None,
            },
            "parents": [],
            "children": [],
            "publications": [],
        }
        capture, _ = self._setup(
            monkeypatch,
            tmp_path,
            data_overrides={
                "get_research_dossier": lambda rid: dossier,
                "get_research": lambda rid: {"follow_ups": [{"q": "only one"}]},
                "get_research_timeline": lambda rid: [],
            },
        )

        code = cli.cmd_demo(argparse.Namespace())

        output = capture.export_text()
        assert code == 0
        assert "📦 研究对象摘要" in output
        assert "追问: 1 条" in output
        assert "上游研究" not in output
        assert "派生研究" not in output
        assert "发布产物" not in output
        # 时间线为空，不显示表格
        assert "⏱ 研究时间线" not in output

    # ── 场景 7: 已归档的研究对象 ───────────────────────────────

    def test_dossier_archived(self, monkeypatch, tmp_path):
        """已归档的对象 → 状态显示红色。"""
        _patch_status_mod(monkeypatch, {"_run_ollama": lambda prompt, **kw: None})

        dossier = {
            "record": {
                "id": 42,
                "topic": "archived topic",
                "source_count": 1,
                "archived_at": 1700000000,
            },
            "parents": [],
            "children": [],
            "publications": [],
        }
        capture, _ = self._setup(
            monkeypatch,
            tmp_path,
            data_overrides={
                "get_research_dossier": lambda rid: dossier,
                "get_research": lambda rid: {"follow_ups": []},
                "get_research_timeline": lambda rid: [],
            },
        )

        code = cli.cmd_demo(argparse.Namespace())

        output = capture.export_text()
        assert code == 0
        assert "🔴 已归档" in output
        assert "🟢" not in output  # 不显示活跃
