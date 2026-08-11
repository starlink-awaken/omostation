from __future__ import annotations

import argparse
from types import SimpleNamespace

from cockpit.commands import kems


def test_kems_scan_delegates_to_l4_content_audit(monkeypatch, tmp_path):
    calls: list[tuple[list[str], str]] = []

    def fake_run(command, cwd):
        calls.append((command, cwd))
        return SimpleNamespace(returncode=7)

    monkeypatch.setenv("L4_DOCUMENTS_ROOT", str(tmp_path))
    monkeypatch.setattr(kems.subprocess, "run", fake_run)

    result = kems.cmd_kems_scan(argparse.Namespace())

    assert result == 7
    assert len(calls) == 1
    command, _cwd = calls[0]
    assert command[-7:] == [
        "python",
        "-m",
        "l4_kernel.cli",
        "content",
        "audit",
        str(tmp_path),
        "--json",
    ]
