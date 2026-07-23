"""Unit tests for cockpit bos capability list/invoke matching."""

from __future__ import annotations

import argparse
from types import SimpleNamespace
from unittest import mock

from cockpit.commands import bos as bos_mod


def test_match_capability_by_short_name():
    services = [
        SimpleNamespace(
            uri="bos://capability/media-crawler/crawl",
            package="toolbox/media-crawler",
            domain="capability",
            command=["echo", "ok"],
            description="crawler",
        ),
        SimpleNamespace(
            uri="bos://capability/last30days-skill/fetch",
            package="toolbox/last30days-skill",
            domain="capability",
            command=[],
            description="skill",
        ),
    ]
    assert bos_mod._match_capability_service(services, "media-crawler").uri.endswith("/crawl")
    assert bos_mod._match_capability_service(services, "last30days").uri.endswith("/fetch")
    assert bos_mod._match_capability_service(services, "bos://capability/media-crawler/crawl") is not None
    assert bos_mod._match_capability_service(services, "nope") is None


def test_cmd_bos_capability_invoke_runs_command(monkeypatch, capsys):
    svc = SimpleNamespace(
        uri="bos://capability/media-crawler/crawl",
        package="toolbox/media-crawler",
        domain="capability",
        command=["echo", "media-crawler-ok"],
        description="crawler",
    )
    monkeypatch.setattr(bos_mod, "_load_capability_services", lambda: [svc])

    code = bos_mod.cmd_bos_capability(
        argparse.Namespace(capability_command="invoke", capability_service="media-crawler", capability_args=[])
    )
    out = capsys.readouterr().out
    assert code == 0
    assert "media-crawler" in out
    assert "exit 0" in out or "✅" in out


def test_cmd_bos_capability_invoke_missing(monkeypatch, capsys):
    monkeypatch.setattr(bos_mod, "_load_capability_services", lambda: [])
    code = bos_mod.cmd_bos_capability(
        argparse.Namespace(capability_command="invoke", capability_service="missing", capability_args=[])
    )
    assert code == 1
    assert "未找到" in capsys.readouterr().out


def test_cmd_bos_capability_invoke_no_command(monkeypatch, capsys):
    svc = SimpleNamespace(
        uri="bos://capability/last30days-skill/fetch",
        package="toolbox/last30days-skill",
        domain="capability",
        command=[],
        description="skill",
    )
    monkeypatch.setattr(bos_mod, "_load_capability_services", lambda: [svc])
    code = bos_mod.cmd_bos_capability(
        argparse.Namespace(capability_command="invoke", capability_service="last30days", capability_args=[])
    )
    assert code == 2
    assert "无 command" in capsys.readouterr().out
