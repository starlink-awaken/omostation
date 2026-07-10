"""Dashboard 命令测试。"""

from __future__ import annotations

import argparse
import importlib
import sys
import types
import urllib.request
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
        return "http://localhost:8090/bos"


class _CtrlCProc:
    """proc.wait() 引发 KeyboardInterrupt"""

    def wait(self):
        raise KeyboardInterrupt()

    def terminate(self):
        pass

    def poll(self):
        return None


def _patch_status_subprocess(monkeypatch):
    """Monkeypatch subprocess in commands.status module."""
    from cockpit.commands import status as _status_mod

    _fake_sp = types.ModuleType("fake_subprocess")
    _fake_sp.Popen = lambda *args, **kwargs: _DummyProc()
    _fake_sp.DEVNULL = -3
    monkeypatch.setattr(_status_mod, "subprocess", _fake_sp)


def test_cmd_dashboard_already_running(monkeypatch):
    """Dashboard 已在运行时直接打开浏览器。"""
    capture = Console(record=True, force_terminal=True, width=120)
    monkeypatch.setattr(cli, "console", capture)
    fake_webbrowser = types.SimpleNamespace(open=lambda url: True)
    monkeypatch.setitem(sys.modules, "webbrowser", fake_webbrowser)

    monkeypatch.setattr(urllib.request, "urlopen", lambda *args, **kwargs: _HTTPResponse(200))

    code = cli.cmd_dashboard(argparse.Namespace())

    output = capture.export_text()
    assert code == 0
    assert "Dashboard 已运行" in output


def test_cmd_dashboard_starts_and_handles_ctrl_c(monkeypatch):
    """Dashboard 未运行时启动服务，并在 Ctrl+C 后停止。"""
    from cockpit.commands import status as _status_mod

    capture = Console(record=True, force_terminal=True, width=120)
    monkeypatch.setattr(cli, "console", capture)
    fake_webbrowser = types.SimpleNamespace(open=lambda url: True)
    monkeypatch.setitem(sys.modules, "webbrowser", fake_webbrowser)
    monkeypatch.setattr(cli.time, "sleep", lambda _: None)

    calls = []

    def _fake_urlopen(*args, **kwargs):
        calls.append(1)
        if len(calls) == 1:
            raise ConnectionError("not running")
        return _HTTPResponse(200)

    monkeypatch.setattr(urllib.request, "urlopen", _fake_urlopen)
    monkeypatch.setattr(_status_mod.subprocess, "Popen", lambda *args, **kwargs: _CtrlCProc())
    monkeypatch.setattr(_status_mod.subprocess, "DEVNULL", -3)

    code = cli.cmd_dashboard(argparse.Namespace())

    output = capture.export_text()
    assert code == 0
    assert "Dashboard 已启动" in output
    assert "Dashboard 已停止" in output


def test_cmd_dashboard_shows_fix_suggestions_when_http_is_non_200(monkeypatch):
    capture = Console(record=True, force_terminal=True, width=120)
    monkeypatch.setattr(cli, "console", capture)
    fake_webbrowser = types.SimpleNamespace(open=lambda url: True)
    monkeypatch.setitem(sys.modules, "webbrowser", fake_webbrowser)
    monkeypatch.setattr(cli.time, "sleep", lambda _: None)
    _patch_status_subprocess(monkeypatch)

    calls = []

    def _fake_urlopen(*args, **kwargs):
        calls.append(1)
        # 第一次探测未运行；第二次启动后返回非 200
        if len(calls) == 1:
            raise ConnectionError("not running")
        return _HTTPResponse(502)

    monkeypatch.setattr(urllib.request, "urlopen", _fake_urlopen)

    code = cli.cmd_dashboard(argparse.Namespace())

    output = capture.export_text()
    assert code == 1
    assert "Dashboard returned HTTP 502" in output
    assert "无法启动" not in output


def test_cmd_dashboard_urlopen_exception(monkeypatch):
    """启动后 urlopen 抛出异常→无法连接。"""
    capture = Console(record=True, force_terminal=True, width=120)
    monkeypatch.setattr(cli, "console", capture)
    fake_webbrowser = types.SimpleNamespace(open=lambda url: True)
    monkeypatch.setitem(sys.modules, "webbrowser", fake_webbrowser)
    monkeypatch.setattr(cli.time, "sleep", lambda _: None)
    _patch_status_subprocess(monkeypatch)

    monkeypatch.setattr(
        urllib.request, "urlopen", lambda *args, **kwargs: (_ for _ in ()).throw(ConnectionError("Connection refused"))
    )

    code = cli.cmd_dashboard(argparse.Namespace())

    output = capture.export_text()
    assert code == 1
    assert "无法连接到 Dashboard" in output


def test_cmd_dashboard_file_not_found(monkeypatch):
    """subprocess.Popen 抛出 FileNotFoundError。"""
    from cockpit.commands import status as _status_mod

    capture = Console(record=True, force_terminal=True, width=120)
    monkeypatch.setattr(cli, "console", capture)
    fake_webbrowser = types.SimpleNamespace(open=lambda url: True)
    monkeypatch.setitem(sys.modules, "webbrowser", fake_webbrowser)
    monkeypatch.setattr(cli.time, "sleep", lambda _: None)

    def _popen_raise(*a, **kw):
        raise FileNotFoundError("python not found")

    monkeypatch.setattr(_status_mod.subprocess, "Popen", _popen_raise)
    monkeypatch.setattr(_status_mod.subprocess, "DEVNULL", -3)
    monkeypatch.setattr(
        urllib.request, "urlopen", lambda *args, **kwargs: (_ for _ in ()).throw(ConnectionError("not running"))
    )

    code = cli.cmd_dashboard(argparse.Namespace())

    output = capture.export_text()
    assert code == 1
    assert "无法启动 Dashboard" in output


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


def test_cmd_status_non_watch_calls_render_workbench(monkeypatch):
    """cmd_status 非 watch 模式→调用 _render_workbench 并返回 0。"""
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
