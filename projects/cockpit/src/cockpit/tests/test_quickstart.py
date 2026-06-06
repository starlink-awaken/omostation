"""快速开始向导 (quickstart.py) 完整单元测试。"""

from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path
from unittest.mock import Mock

from rich.console import Console
from cockpit.commands.quickstart import (
    _auto_fix,
    _check_cli_tools,
    _check_ollama_running,
    _check_python,
    _check_workspace_db,
    _ensure_workspace_db,
    cmd_quickstart,
)

# ═══════════════════════════════════════════════════════════════════════════════
# _check_python — 2 条路径
# ═══════════════════════════════════════════════════════════════════════════════


class TestCheckPython:
    def test_ok(self):
        """Python 3.10+ → 返回 None"""
        assert _check_python() is None

    def test_too_old(self, monkeypatch):
        """Python 3.9 → 返回错误信息"""
        monkeypatch.setattr(sys, "version_info", Mock(major=3, minor=9, micro=0))
        msg = _check_python()
        assert msg is not None
        assert "3.9" in msg


# ═══════════════════════════════════════════════════════════════════════════════
# _check_cli_tools — 2 条路径
# ═══════════════════════════════════════════════════════════════════════════════


class TestCheckCliTools:
    def test_all_found(self, monkeypatch):
        """所有工具均在 PATH 中 → 全部 True"""
        monkeypatch.setattr("shutil.which", lambda name: f"/usr/bin/{name}")
        result = _check_cli_tools()
        assert isinstance(result, dict)
        assert all(result.values())

    def test_none_found(self, monkeypatch):
        """无工具在 PATH 中 → 全部 False"""
        monkeypatch.setattr("shutil.which", lambda name: None)
        result = _check_cli_tools()
        assert isinstance(result, dict)
        assert not any(result.values())


# ═══════════════════════════════════════════════════════════════════════════════
# _check_ollama_running — 2 条路径
# ═══════════════════════════════════════════════════════════════════════════════


class TestCheckOllamaRunning:
    def test_running(self, monkeypatch):
        """Ollama 服务正常响应 → True"""

        class _FakeResponse:
            status = 200

        monkeypatch.setattr(
            "cockpit.commands.quickstart.urlrequest.urlopen",
            lambda req, timeout: _FakeResponse(),
        )
        assert _check_ollama_running() is True

    def test_not_running(self, monkeypatch):
        """Ollama 服务不可用 → False"""
        monkeypatch.setattr(
            "cockpit.commands.quickstart.urlrequest.urlopen",
            lambda req, timeout: (_ for _ in ()).throw(OSError("connection refused")),
        )
        assert _check_ollama_running() is False


# ═══════════════════════════════════════════════════════════════════════════════
# _check_workspace_db — 4 条路径
# ═══════════════════════════════════════════════════════════════════════════════


class TestCheckWorkspaceDb:
    def test_db_not_exists(self, monkeypatch, tmp_path):
        """数据库文件不存在 → exists=False, count=0"""
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        result = _check_workspace_db()
        assert result == {"exists": False, "research_count": 0}

    def test_db_exists_with_records(self, monkeypatch, tmp_path):
        """数据库存在且有记录 → exists=True, count=N"""
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        db_dir = tmp_path / ".workspace"
        db_dir.mkdir()
        conn = sqlite3.connect(str(db_dir / "data.db"))
        conn.execute("CREATE TABLE research (id INTEGER PRIMARY KEY, topic TEXT)")
        conn.execute("INSERT INTO research (topic) VALUES ('t1')")
        conn.execute("INSERT INTO research (topic) VALUES ('t2')")
        conn.execute("INSERT INTO research (topic) VALUES ('t3')")
        conn.commit()
        conn.close()
        result = _check_workspace_db()
        assert result == {"exists": True, "research_count": 3}

    def test_db_exists_empty(self, monkeypatch, tmp_path):
        """数据库存在但无记录 → exists=True, count=0"""
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        db_dir = tmp_path / ".workspace"
        db_dir.mkdir()
        conn = sqlite3.connect(str(db_dir / "data.db"))
        conn.execute("CREATE TABLE research (id INTEGER PRIMARY KEY, topic TEXT)")
        conn.commit()
        conn.close()
        result = _check_workspace_db()
        assert result["exists"] is True
        assert result["research_count"] == 0

    def test_db_corrupted(self, monkeypatch, tmp_path):
        """数据库损坏 → exists=True, count=-1"""
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        db_dir = tmp_path / ".workspace"
        db_dir.mkdir()
        (db_dir / "data.db").write_text("not a valid sqlite file")
        result = _check_workspace_db()
        assert result == {"exists": True, "research_count": -1}


# ═══════════════════════════════════════════════════════════════════════════════
# cmd_quickstart — 集成测试
# ═══════════════════════════════════════════════════════════════════════════════


class TestCmdQuickstart:
    def test_happy_path(self, monkeypatch):
        """所有检测通过 → 显示完整 4 步向导"""
        capture = Console(record=True, force_terminal=True, width=140)
        monkeypatch.setattr("cockpit.commands.quickstart._get_console", lambda: capture)
        monkeypatch.setattr("cockpit.commands.quickstart._check_python", lambda: None)
        monkeypatch.setattr(
            "cockpit.commands.quickstart._check_cli_tools",
            lambda: {"minerva": True, "git": True, "ollama": True, "pip3": True, "uvicorn": True, "agora": True},
        )
        monkeypatch.setattr("cockpit.commands.quickstart._check_ollama_running", lambda: True)
        monkeypatch.setattr(
            "cockpit.commands.quickstart._check_workspace_db", lambda: {"exists": True, "research_count": 5}
        )

        code = cmd_quickstart(argparse.Namespace())

        output = capture.export_text()
        assert code == 0
        assert "Step 1/4" in output
        assert "Step 2/4" in output
        assert "Step 3/4" in output
        assert "Step 4/4" in output
        assert "Python" in output
        assert "minerva" in output
        assert "workspace research" in output

    def test_no_tools_and_empty_db(self, monkeypatch):
        """无工具 + 空数据库 → 显示缺失提示和推荐配置"""
        capture = Console(record=True, force_terminal=True, width=140)
        monkeypatch.setattr("cockpit.commands.quickstart._get_console", lambda: capture)
        monkeypatch.setattr("cockpit.commands.quickstart._check_python", lambda: None)
        monkeypatch.setattr(
            "cockpit.commands.quickstart._check_cli_tools",
            lambda: {"minerva": False, "git": False, "ollama": False, "pip3": False, "uvicorn": False, "agora": False},
        )
        monkeypatch.setattr("cockpit.commands.quickstart._check_ollama_running", lambda: False)
        monkeypatch.setattr(
            "cockpit.commands.quickstart._check_workspace_db", lambda: {"exists": False, "research_count": 0}
        )

        code = cmd_quickstart(argparse.Namespace())

        output = capture.export_text()
        assert code == 0
        assert "Step 1/4" in output
        assert "未安装" in output or "⭕" in output

    def test_fix_dispatch_via_flag(self, monkeypatch):
        """cmd_quickstart 带 --fix 标志 → 转发到 _auto_fix，不显示 4 步向导"""
        capture = Console(record=True, force_terminal=True, width=140)
        monkeypatch.setattr("cockpit.commands.quickstart._get_console", lambda: capture)
        monkeypatch.setattr("cockpit.commands.quickstart._check_ollama_running", lambda: True)
        monkeypatch.setattr("cockpit.commands.quickstart.shutil.which", lambda _: "/usr/bin/ollama")
        monkeypatch.setattr("cockpit.commands.quickstart._ensure_workspace_db", lambda: True)

        # 模拟模型已存在
        class _FakeResp:
            status = 200

            def read(self):
                return b'{"models": [{"name": "llama3.2"}]}'

        monkeypatch.setattr(
            "cockpit.commands.quickstart.urlrequest.urlopen",
            lambda req, timeout: _FakeResp(),
        )

        code = cmd_quickstart(argparse.Namespace(fix=True, model="llama3.2"))

        output = capture.export_text()
        assert code == 0
        assert "自动修复模式" in output
        assert "Step 1/4" not in output  # 不应显示普通向导

    def test_init_with_fix_dispatch(self, monkeypatch):
        """init 命令也支持 --fix → 转发到 _auto_fix"""
        capture = Console(record=True, force_terminal=True, width=140)
        monkeypatch.setattr("cockpit.commands.quickstart._get_console", lambda: capture)
        monkeypatch.setattr("cockpit.commands.quickstart._check_ollama_running", lambda: True)
        monkeypatch.setattr("cockpit.commands.quickstart.shutil.which", lambda _: "/usr/bin/ollama")
        monkeypatch.setattr("cockpit.commands.quickstart._ensure_workspace_db", lambda: True)

        class _FakeResp:
            status = 200

            def read(self):
                return b'{"models": [{"name": "llama3.2"}]}'

        monkeypatch.setattr(
            "cockpit.commands.quickstart.urlrequest.urlopen",
            lambda req, timeout: _FakeResp(),
        )

        code = cmd_quickstart(argparse.Namespace(fix=True, model="llama3.2"))

        output = capture.export_text()
        assert code == 0
        assert "自动修复模式" in output

    def test_python_too_old_ollama_not_running(self, monkeypatch):
        """Python 太旧 + Ollama 已装未运行 → 覆盖 line 74/86/110"""
        capture = Console(record=True, force_terminal=True, width=140)
        monkeypatch.setattr("cockpit.commands.quickstart._get_console", lambda: capture)
        # Python 太旧
        monkeypatch.setattr("cockpit.commands.quickstart._check_python", lambda: "需要 Python 3.10+，当前: 3.9.0")
        # Ollama 已安装但未运行
        monkeypatch.setattr(
            "cockpit.commands.quickstart._check_cli_tools",
            lambda: {"minerva": True, "git": True, "ollama": True, "pip3": True, "uvicorn": True, "agora": True},
        )
        monkeypatch.setattr("cockpit.commands.quickstart._check_ollama_running", lambda: False)
        monkeypatch.setattr(
            "cockpit.commands.quickstart._check_workspace_db", lambda: {"exists": True, "research_count": 3}
        )

        code = cmd_quickstart(argparse.Namespace())

        output = capture.export_text()
        assert code == 0
        assert "Step 1/4" in output
        # line 74: Python 太旧 → 不会显示绿色 Python 版本号，issues 被收集
        assert "3.9" not in output  # Python 太旧时绿色版本行不显示
        # line 86: Ollama 已安装但未运行
        assert "⚠️" in output
        assert "已安装但未运行" in output
        # line 110: 推荐配置中 ollama 未运行提示
        assert "请启动" in output or "ollama serve" in output


# ═══════════════════════════════════════════════════════════════════════════════
# _ensure_workspace_db — 4 条路径
# ═══════════════════════════════════════════════════════════════════════════════


class TestEnsureWorkspaceDb:
    def test_db_already_exists(self, monkeypatch, tmp_path):
        """数据库已存在 → True"""
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        db_dir = tmp_path / ".workspace"
        db_dir.mkdir(parents=True)
        (db_dir / "data.db").write_text("dummy")
        assert _ensure_workspace_db() is True

    def test_created_successfully(self, monkeypatch, tmp_path):
        """数据库不存在但成功创建 → True"""
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        mock_da = Mock()
        mock_da.save_research = Mock(return_value=42)
        monkeypatch.setattr(
            "cockpit.storage.get_data_access",
            lambda: mock_da,
        )
        assert _ensure_workspace_db() is True
        assert mock_da.save_research.called

    def test_creation_fails(self, monkeypatch, tmp_path):
        """数据库创建失败（get_data_access 异常）→ False"""
        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        def _raise(*a, **kw):
            raise RuntimeError("no storage")

        monkeypatch.setattr(
            "cockpit.storage.get_data_access",
            _raise,
        )
        assert _ensure_workspace_db() is False


# ═══════════════════════════════════════════════════════════════════════════════
# _auto_fix — 6 条路径
# ═══════════════════════════════════════════════════════════════════════════════


class TestAutoFix:
    def test_all_good(self, monkeypatch):
        """ollama 运行中 + 模型就绪 + DB 就绪 → 0 + success panel"""
        capture = Console(record=True, force_terminal=True, width=140)
        monkeypatch.setattr("cockpit.commands.quickstart._get_console", lambda: capture)
        monkeypatch.setattr("cockpit.commands.quickstart.shutil.which", lambda _: "/usr/bin/ollama")
        monkeypatch.setattr("cockpit.commands.quickstart._check_ollama_running", lambda: True)
        monkeypatch.setattr("cockpit.commands.quickstart._ensure_workspace_db", lambda: True)

        class _FakeResp:
            status = 200

            def read(self):
                return b'{"models": [{"name": "llama3.2"}]}'

        monkeypatch.setattr(
            "cockpit.commands.quickstart.urlrequest.urlopen",
            lambda req, timeout: _FakeResp(),
        )

        code = _auto_fix(capture, argparse.Namespace(model="llama3.2"))

        output = capture.export_text()
        assert code == 0
        assert "自动修复完成" in output
        assert "✅ ollama 运行中" in output
        assert "✅ 模型 llama3.2 已就绪" in output
        assert "✅ workspace 数据库就绪" in output

    def test_ollama_not_installed(self, monkeypatch):
        """ollama 未安装 → 跳过 ollama 检查，只处理 DB"""
        capture = Console(record=True, force_terminal=True, width=140)
        monkeypatch.setattr("cockpit.commands.quickstart._get_console", lambda: capture)
        monkeypatch.setattr("cockpit.commands.quickstart.shutil.which", lambda _: None)
        monkeypatch.setattr("cockpit.commands.quickstart._ensure_workspace_db", lambda: True)

        code = _auto_fix(capture, argparse.Namespace(model="llama3.2"))

        output = capture.export_text()
        assert code == 0
        assert "自动修复完成" in output
        assert "✅ workspace 数据库就绪" in output

    def test_ollama_installed_not_running_auto_start(self, monkeypatch):
        """ollama 已装未运行 → 自动启动成功"""
        capture = Console(record=True, force_terminal=True, width=140)
        monkeypatch.setattr("cockpit.commands.quickstart._get_console", lambda: capture)
        monkeypatch.setattr("cockpit.commands.quickstart.shutil.which", lambda _: "/usr/bin/ollama")

        # 一开始没运行，1 秒后运行
        call_count = [0]

        def _ollama_running():
            call_count[0] += 1
            return call_count[0] > 1  # 第二次调用返回 True

        monkeypatch.setattr("cockpit.commands.quickstart._check_ollama_running", _ollama_running)

        monkeypatch.setattr("cockpit.commands.quickstart.subprocess.Popen", Mock())
        monkeypatch.setattr("cockpit.commands.quickstart.time", Mock(sleep=lambda s: None))
        monkeypatch.setattr("cockpit.commands.quickstart._ensure_workspace_db", lambda: True)

        # 模型已就绪
        class _FakeResp:
            status = 200

            def read(self):
                return b'{"models": [{"name": "llama3.2"}]}'

        monkeypatch.setattr(
            "cockpit.commands.quickstart.urlrequest.urlopen",
            lambda req, timeout: _FakeResp(),
        )

        code = _auto_fix(capture, argparse.Namespace(model="llama3.2"))

        output = capture.export_text()
        assert code == 0
        assert "自动修复完成" in output
        assert "启动成功" in output

    def test_ollama_not_running_start_timeout(self, monkeypatch):
        """ollama 已装未运行 → 启动超时 → 1 + warning"""
        capture = Console(record=True, force_terminal=True, width=140)
        monkeypatch.setattr("cockpit.commands.quickstart._get_console", lambda: capture)
        monkeypatch.setattr("cockpit.commands.quickstart.shutil.which", lambda _: "/usr/bin/ollama")
        monkeypatch.setattr("cockpit.commands.quickstart._check_ollama_running", lambda: False)  # 永远不运行
        monkeypatch.setattr("cockpit.commands.quickstart.subprocess.Popen", Mock())
        monkeypatch.setattr("cockpit.commands.quickstart.time", Mock(sleep=lambda s: None))
        monkeypatch.setattr("cockpit.commands.quickstart._ensure_workspace_db", lambda: True)

        code = _auto_fix(capture, argparse.Namespace(model="llama3.2"))

        output = capture.export_text()
        assert code == 1
        assert "启动超时" in output
        assert "ollama 启动失败" in output

    def test_model_missing_auto_pull(self, monkeypatch):
        """模型不存在 → 自动拉取成功"""
        capture = Console(record=True, force_terminal=True, width=140)
        monkeypatch.setattr("cockpit.commands.quickstart._get_console", lambda: capture)
        monkeypatch.setattr("cockpit.commands.quickstart.shutil.which", lambda _: "/usr/bin/ollama")
        monkeypatch.setattr("cockpit.commands.quickstart._check_ollama_running", lambda: True)
        monkeypatch.setattr("cockpit.commands.quickstart._ensure_workspace_db", lambda: True)

        # 模型不在列表中
        class _FakeResp:
            status = 200

            def read(self):
                return b'{"models": [{"name": "llama3.1"}]}'  # llama3.2 不在

        monkeypatch.setattr(
            "cockpit.commands.quickstart.urlrequest.urlopen",
            lambda req, timeout: _FakeResp(),
        )
        monkeypatch.setattr(
            "cockpit.commands.quickstart.subprocess.run",
            Mock(return_value=Mock(returncode=0, stdout="success", stderr="")),
        )

        code = _auto_fix(capture, argparse.Namespace(model="llama3.2"))

        output = capture.export_text()
        assert code == 0
        assert "正在拉取模型" in output
        assert "拉取完成" in output
