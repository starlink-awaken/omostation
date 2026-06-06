from __future__ import annotations

import argparse
import subprocess

from rich.console import Console
from cockpit import cli
from cockpit.tests.conftest import MockDataAccess


def test_base_find_cli_returns_none_for_nonexistent():
    """直接测试 base._find_cli 函数体（covers base.py:60-61）"""
    from cockpit.commands.base import _find_cli as base_find_cli

    result = base_find_cli("nonexistent_tool_xyz_should_not_exist")
    assert result is None


class _SaveSpy:
    def __init__(self):
        self.called = False
        self.payload: dict[str, object] = {}

    def __call__(self, topic: str, summary: str, full_text: str = "", source_count: int = 0) -> int:
        self.called = True
        self.payload = {
            "topic": topic,
            "summary": summary,
            "full_text": full_text,
            "source_count": source_count,
        }
        return 99


def _patch_base(monkeypatch, attrs: dict):
    """Monkeypatch functions in cockpit.commands.base (where cmd modules import from)."""
    from cockpit.commands import base as _base_mod

    for name, value in attrs.items():
        monkeypatch.setattr(_base_mod, name, value)


def _patch_research_mod(monkeypatch, attrs: dict):
    """Monkeypatch functions in cockpit.commands.research directly."""
    from cockpit.commands import research as _research_mod

    for name, value in attrs.items():
        monkeypatch.setattr(_research_mod, name, value)


def test_cmd_research_does_not_save_when_minerva_missing(monkeypatch):
    capture = Console(record=True, force_terminal=True, width=140)
    monkeypatch.setattr(cli, "console", capture)
    monkeypatch.setattr(cli, "err", capture)
    _patch_base(
        monkeypatch,
        {
            "_research_progress": lambda task: None,
            "_notify_research_complete": lambda topic: None,
            "_find_cli": lambda name: None,
        },
    )
    _patch_research_mod(
        monkeypatch,
        {
            "_run_ollama": lambda prompt, **kw: None,
            "_find_cli": lambda name: None,
        },
    )
    save_spy = _SaveSpy()
    mock = MockDataAccess()
    mock.save_research = save_spy
    monkeypatch.setattr(cli, "get_data_access", lambda: mock)

    code = cli.cmd_research(argparse.Namespace(topic=["reliability", "check"]))

    output = capture.export_text()
    assert code == 0  # 本地回退仍成功
    assert save_spy.called is True
    assert "本地缓存（降级）" in output


def test_cmd_research_empty_topic_shows_error(monkeypatch):
    """空主题→显示错误提示（covers research.py:68-70）"""
    capture = Console(record=True, force_terminal=True, width=140)
    monkeypatch.setattr(cli, "console", capture)
    monkeypatch.setattr(cli, "err", capture)
    _patch_base(
        monkeypatch,
        {
            "_research_progress": lambda task: None,
            "_print_research_help_suggestions": lambda: print("suggestion printed"),
        },
    )
    mock = MockDataAccess()
    monkeypatch.setattr(cli, "get_data_access", lambda: mock)

    code = cli.cmd_research(argparse.Namespace(topic=[]))

    output = capture.export_text()
    assert code == 1
    assert "请指定研究主题" in output


def test_cmd_research_minerva_subprocess_exception(monkeypatch):
    """minerva 子进程抛出异常→跳过并走降级链（covers research.py:86-87）"""
    capture = Console(record=True, force_terminal=True, width=140)
    monkeypatch.setattr(cli, "console", capture)
    monkeypatch.setattr(cli, "err", capture)
    _patch_base(
        monkeypatch,
        {
            "_research_progress": lambda task: None,
            "_notify_research_complete": lambda topic: None,
            "_find_cli": lambda name: "/usr/local/bin/minerva",
        },
    )
    _patch_research_mod(
        monkeypatch,
        {
            "_run_ollama": lambda prompt, **kw: None,
            "_find_cli": lambda name: "/usr/local/bin/minerva",
            "subprocess": type(
                "_FakeSubprocess",
                (),
                {
                    "run": lambda *args, **kwargs: (_ for _ in ()).throw(OSError("minerva not found")),
                    "CompletedProcess": subprocess.CompletedProcess,
                },
            )(),
        },
    )
    save_spy = _SaveSpy()
    mock = MockDataAccess()
    mock.save_research = save_spy
    monkeypatch.setattr(cli, "get_data_access", lambda: mock)

    code = cli.cmd_research(argparse.Namespace(topic=["exception", "test"]))

    output = capture.export_text()
    assert code == 0
    assert save_spy.called is True
    assert "本地缓存（降级）" in output


def test_cmd_research_minerva_fails_ollama_succeeds(monkeypatch):
    """minerva 不可用→ollama 降级成功（covers research.py:93-94）"""
    capture = Console(record=True, force_terminal=True, width=140)
    monkeypatch.setattr(cli, "console", capture)
    monkeypatch.setattr(cli, "err", capture)
    _patch_base(
        monkeypatch,
        {
            "_research_progress": lambda task: None,
            "_notify_research_complete": lambda topic: None,
            "_find_cli": lambda name: None,
        },
    )
    _patch_research_mod(
        monkeypatch,
        {
            "_run_ollama": lambda prompt, **kw: "这是 ollama 生成的回答内容。",
            "_find_cli": lambda name: None,
        },
    )
    save_spy = _SaveSpy()
    mock = MockDataAccess()
    mock.save_research = save_spy
    monkeypatch.setattr(cli, "get_data_access", lambda: mock)

    code = cli.cmd_research(argparse.Namespace(topic=["ollama", "success"]))

    output = capture.export_text()
    assert code == 0
    assert save_spy.called is True
    assert "ollama（降级）" in output


def test_cmd_research_saves_local_fallback_when_traceback_and_ollama_fail(monkeypatch):
    capture = Console(record=True, force_terminal=True, width=140)
    monkeypatch.setattr(cli, "console", capture)
    monkeypatch.setattr(cli, "err", capture)
    _patch_base(
        monkeypatch,
        {
            "_research_progress": lambda task: None,
            "_notify_research_complete": lambda topic: None,
            "_find_cli": lambda name: "/usr/local/bin/minerva",
        },
    )
    _patch_research_mod(
        monkeypatch,
        {
            "_run_ollama": lambda prompt, **kw: None,
            "_find_cli": lambda name: "/usr/local/bin/minerva",
            "subprocess": type(
                "_FakeSubprocess",
                (),
                {
                    "run": lambda *args, **kwargs: subprocess.CompletedProcess(
                        args=["minerva"],
                        returncode=1,
                        stdout="",
                        stderr="Traceback (most recent call last):\nModuleNotFoundError: broken",
                    ),
                    "CompletedProcess": subprocess.CompletedProcess,
                },
            )(),
        },
    )
    save_spy = _SaveSpy()
    mock = MockDataAccess()
    mock.save_research = save_spy
    monkeypatch.setattr(cli, "get_data_access", lambda: mock)

    code = cli.cmd_research(argparse.Namespace(topic=["broken", "research"]))

    output = capture.export_text()
    assert code == 0  # 本地回退仍成功
    assert save_spy.called is True
    assert "本地缓存（降级）" in output
    assert "Traceback" not in output


def test_cmd_research_saves_successful_output(monkeypatch):
    capture = Console(record=True, force_terminal=True, width=140)
    monkeypatch.setattr(cli, "console", capture)
    monkeypatch.setattr(cli, "err", capture)
    _patch_base(
        monkeypatch,
        {
            "_research_progress": lambda task: None,
            "_notify_research_complete": lambda topic: None,
            "_find_cli": lambda name: "/usr/local/bin/minerva",
        },
    )
    _patch_research_mod(
        monkeypatch,
        {
            "_find_cli": lambda name: "/usr/local/bin/minerva",
            "subprocess": type(
                "_FakeSubprocess",
                (),
                {
                    "run": lambda *args, **kwargs: subprocess.CompletedProcess(
                        args=["minerva"], returncode=0, stdout="# Result\n\nUseful research body.", stderr=""
                    ),
                    "CompletedProcess": subprocess.CompletedProcess,
                },
            )(),
        },
    )
    save_spy = _SaveSpy()
    mock = MockDataAccess()
    mock.save_research = save_spy
    monkeypatch.setattr(cli, "get_data_access", lambda: mock)

    code = cli.cmd_research(argparse.Namespace(topic=["good", "research"]))

    output = capture.export_text()
    assert code == 0
    assert save_spy.called is True
    assert save_spy.payload["topic"] == "good research"
    assert "Useful research body." in str(save_spy.payload["full_text"])
    assert "ID: 99" in output
