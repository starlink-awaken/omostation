"""Dashboard 命令测试。"""

from __future__ import annotations

import argparse
import importlib
import sys
import types
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from rich.console import Console

cli = importlib.import_module("cockpit.cli")


class _DummyProc:
    def __init__(self):
        self.returncode = 0

    def wait(self):
        pass

    def terminate(self):
        pass

    def poll(self):
        return 0


class _HTTPResponse:
    def __init__(self, status: int):
        self.status = status

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def read(self):
        return b""

    def geturl(self):
        return "http://localhost:8765"


def _patch_status_subprocess(monkeypatch):
    """Monkeypatch subprocess in commands.status module."""
    from cockpit.commands import status as _status_mod

    _fake_sp = types.ModuleType("fake_subprocess")
    _fake_sp.Popen = lambda *args, **kwargs: _DummyProc()
    _fake_sp.DEVNULL = -3
    monkeypatch.setattr(_status_mod, "subprocess", _fake_sp)


def _patch_find_cli(monkeypatch, fn):
    """Monkeypatch _find_cli in ALL modules that import it."""
    from cockpit.commands import base as _base_mod
    from cockpit.commands import status as _status_mod

    monkeypatch.setattr(_base_mod, "_find_cli", fn)
    monkeypatch.setattr(_status_mod, "_find_cli", fn)


def test_cmd_dashboard_shows_fix_suggestions_when_http_is_non_200(monkeypatch):
    capture = Console(record=True, force_terminal=True, width=120)
    monkeypatch.setattr(cli, "console", capture)
    fake_webbrowser = types.SimpleNamespace(open=lambda url: True)
    monkeypatch.setitem(sys.modules, "webbrowser", fake_webbrowser)
    monkeypatch.setattr(cli.time, "sleep", lambda _: None)
    _patch_find_cli(monkeypatch, lambda name: "/usr/bin/uvicorn")
    _patch_status_subprocess(monkeypatch)
    monkeypatch.setattr(cli.urlrequest, "urlopen", lambda *args, **kwargs: _HTTPResponse(502))

    code = cli.cmd_dashboard(argparse.Namespace())

    output = capture.export_text()
    assert code == 1
    assert "Dashboard returned HTTP 502" in output
    assert "workspace status" in output
    assert "cd agora && .venv/bin/python -m uvicorn agora.web.app:app --host 127.0.0.1 --port 8765" in output


def test_cmd_dashboard_suggests_uvicorn_install_when_missing(monkeypatch):
    capture = Console(record=True, force_terminal=True, width=120)
    monkeypatch.setattr(cli, "console", capture)
    fake_webbrowser = types.SimpleNamespace(open=lambda url: True)
    monkeypatch.setitem(sys.modules, "webbrowser", fake_webbrowser)
    monkeypatch.setattr(cli.time, "sleep", lambda _: None)
    _patch_find_cli(monkeypatch, lambda name: None if name == "uvicorn" else "/usr/bin/python3")
    monkeypatch.setattr(cli.Path, "exists", lambda self: False)
    _patch_status_subprocess(monkeypatch)
    monkeypatch.setattr(cli.urlrequest, "urlopen", lambda *args, **kwargs: _HTTPResponse(200))

    code = cli.cmd_dashboard(argparse.Namespace())

    output = capture.export_text()
    assert code == 1
    assert "uvicorn 未安装" in output
    assert "cd agora && pip install uvicorn fastapi" in output


class _StopAfterFirstFrame:
    def __init__(self):
        self.calls = 0

    def __call__(self, seconds: float):
        self.calls += 1
        if self.calls >= 2:
            raise KeyboardInterrupt


def test_cmd_status_watch_renders_live_mode_and_stops_cleanly(monkeypatch):
    capture = Console(record=True, force_terminal=True, width=120)
    monkeypatch.setattr(cli, "console", capture)
    monkeypatch.setattr(cli, "err", capture)
    from cockpit.commands import status as _status_mod

    monkeypatch.setattr(
        _status_mod, "_render_workbench", lambda cycle=None, interval=None: capture.print(f"frame {cycle} / {interval}")
    )
    monkeypatch.setattr(cli.console, "clear", lambda: None)
    stopper = _StopAfterFirstFrame()
    monkeypatch.setattr(cli.time, "sleep", stopper)

    code = cli.cmd_status(argparse.Namespace(watch=True, interval=0.2))

    output = capture.export_text()
    assert code == 0
    assert "实时监控模式" in output
    assert "frame 1 / 0.2" in output
    assert "监控已停止" in output


def test_cmd_status_rejects_non_positive_interval(monkeypatch):
    capture = Console(record=True, force_terminal=True, width=120)
    monkeypatch.setattr(cli, "console", capture)
    monkeypatch.setattr(cli, "err", capture)

    code = cli.cmd_status(argparse.Namespace(watch=True, interval=0))

    output = capture.export_text()
    assert code == 1
    assert "刷新间隔必须大于 0 秒" in output


# ═══════════════════════════════════════════════════════════════════════════════
# cmd_dashboard 补充 — 4 条残余分支 (496, 513-517, 518-525, 526-531)
# ═══════════════════════════════════════════════════════════════════════════════


class _CtrlCProc:
    """proc.wait() 引发 KeyboardInterrupt"""

    def wait(self):
        raise KeyboardInterrupt()

    def terminate(self):
        pass

    def poll(self):
        return None


def test_cmd_dashboard_venv_python_exists(monkeypatch):
    """venv_python.exists()→走 venv 路径 (line 496)"""
    from cockpit.commands import status as _status_mod

    capture = Console(record=True, force_terminal=True, width=120)
    monkeypatch.setattr(cli, "console", capture)
    fake_webbrowser = types.SimpleNamespace(open=lambda url: True)
    monkeypatch.setitem(sys.modules, "webbrowser", fake_webbrowser)
    monkeypatch.setattr(cli.time, "sleep", lambda _: None)
    # uvicorn not on PATH → check venv_python.exists
    _patch_find_cli(monkeypatch, lambda name: None)
    # Let Popen work normally, but venv_python.exists returns True
    _real_exists = cli.Path.exists
    monkeypatch.setattr(cli.Path, "exists", lambda self: True if ".venv" in str(self) else _real_exists(self))
    # Popen returns dummy proc that responds to Ctrl-C
    monkeypatch.setattr(_status_mod.subprocess, "Popen", lambda *args, **kwargs: _CtrlCProc())
    monkeypatch.setattr(_status_mod.subprocess, "DEVNULL", -3)
    monkeypatch.setattr(cli.urlrequest, "urlopen", lambda *args, **kwargs: _HTTPResponse(200))

    code = cli.cmd_dashboard(argparse.Namespace())

    output = capture.export_text()
    assert code == 0
    assert "Dashboard 已启动" in output
    assert "Dashboard 已停止" in output


def test_cmd_dashboard_urlopen_exception(monkeypatch):
    """urlopen 抛出异常→无法连接 (lines 513-517)"""
    capture = Console(record=True, force_terminal=True, width=120)
    monkeypatch.setattr(cli, "console", capture)
    fake_webbrowser = types.SimpleNamespace(open=lambda url: True)
    monkeypatch.setitem(sys.modules, "webbrowser", fake_webbrowser)
    monkeypatch.setattr(cli.time, "sleep", lambda _: None)
    _patch_find_cli(monkeypatch, lambda name: "/usr/bin/uvicorn")
    _patch_status_subprocess(monkeypatch)

    # urlopen raises URLError-like exception
    def _raise_urlopen(*a, **kw):
        raise ConnectionError("Connection refused")

    monkeypatch.setattr(cli.urlrequest, "urlopen", _raise_urlopen)

    code = cli.cmd_dashboard(argparse.Namespace())

    output = capture.export_text()
    assert code == 1
    assert "无法连接到 Dashboard" in output


def test_cmd_status_non_watch_calls_render_workbench(monkeypatch):
    """cmd_status 非 watch 模式→调用 _render_workbench 并返回 0 (lines 173-174)."""
    from cockpit.commands import status as _status_mod

    capture = Console(record=True, force_terminal=True, width=120)
    monkeypatch.setattr(cli, "console", capture)
    monkeypatch.setattr(cli, "err", capture)
    called = [False]

    def _fake_render(cycle=0, interval=0):
        called[0] = True
        capture.print("[bold]✅ workbench rendered[/bold]")

    monkeypatch.setattr(_status_mod, "_render_workbench", _fake_render)

    code = cli.cmd_status(argparse.Namespace(watch=False, interval=5.0))

    output = capture.export_text()
    assert code == 0
    assert called[0] is True
    assert "workbench rendered" in output


def test_cmd_dashboard_file_not_found(monkeypatch):
    """subprocess.Popen 抛出 FileNotFoundError (lines 526-531)"""
    from cockpit.commands import status as _status_mod

    capture = Console(record=True, force_terminal=True, width=120)
    monkeypatch.setattr(cli, "console", capture)
    fake_webbrowser = types.SimpleNamespace(open=lambda url: True)
    monkeypatch.setitem(sys.modules, "webbrowser", fake_webbrowser)
    monkeypatch.setattr(cli.time, "sleep", lambda _: None)
    _patch_find_cli(monkeypatch, lambda name: "/usr/bin/uvicorn")

    # Popen raises FileNotFoundError
    def _popen_raise(*a, **kw):
        raise FileNotFoundError("uvicorn not found")

    monkeypatch.setattr(_status_mod.subprocess, "Popen", _popen_raise)
    monkeypatch.setattr(_status_mod.subprocess, "DEVNULL", -3)

    code = cli.cmd_dashboard(argparse.Namespace())

    output = capture.export_text()
    assert code == 1
    assert "无法启动 Dashboard" in output
