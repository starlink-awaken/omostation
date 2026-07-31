"""Tests for Cockpit BOS Gateway CLI (resolve, read, list, status)."""

from unittest.mock import patch
from cockpit.cli import main
from cockpit.commands.bos import cmd_bos_resolve, cmd_bos_read


class DummyArgs:
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


def test_cmd_bos_resolve_valid(capsys):
    args = DummyArgs(uri="bos://system/backends/health")
    ret = cmd_bos_resolve(args)
    assert ret == 0
    out = capsys.readouterr().out
    assert "═══ BOS URI Route Resolution ═══" in out
    assert "bos://system/backends/health" in out
    assert "internal" in out


def test_cmd_bos_resolve_invalid(capsys):
    args = DummyArgs(uri="bos://unknown/domain/service")
    ret = cmd_bos_resolve(args)
    assert ret == 1
    out = capsys.readouterr().out
    assert "❌ 无法解析 BOS URI" in out


def test_cmd_bos_read_valid(capsys):
    args = DummyArgs(uri="bos://system/backends/health", args="{}")
    ret = cmd_bos_read(args)
    assert ret == 0
    out = capsys.readouterr().out
    assert "═══ BOS URI Read Result ═══" in out
    assert "bos://system/backends/health" in out


def test_cmd_bos_read_invalid_json(capsys):
    args = DummyArgs(uri="bos://system/backends/health", args="not-a-json")
    ret = cmd_bos_read(args)
    assert ret == 1
    out = capsys.readouterr().out
    assert "❌ 无法解析 JSON 参数" in out
