from __future__ import annotations

import argparse
import json
from types import SimpleNamespace

from cockpit.commands import kems


def test_kems_scan_delegates_to_l4_content_audit(monkeypatch, tmp_path):
    calls: list[tuple[list[str], str]] = []

    def fake_run(command, cwd, *, capture_output, text):
        assert capture_output is True
        assert text is True
        calls.append((command, cwd))
        return SimpleNamespace(
            returncode=7,
            stdout=json.dumps(
                {
                    "ok": False,
                    "data": {
                        "root": str(tmp_path),
                        "counts": {"content": 500_000, "runtime": 13},
                        "violation_count": 13,
                        "truncated_violation_count": 3,
                        "violation_samples": [
                            {
                                "relative_path": "_runtime/run.py",
                                "code": "L4-CONTENT-008",
                            }
                        ],
                    },
                }
            ),
            stderr="",
        )

    monkeypatch.setenv("L4_DOCUMENTS_ROOT", str(tmp_path))
    monkeypatch.setattr(kems.subprocess, "run", fake_run)

    result = kems.cmd_kems_scan(argparse.Namespace())

    assert result == 7
    assert len(calls) == 1
    command, _cwd = calls[0]
    assert command[-8:] == [
        "python",
        "-m",
        "l4_kernel.cli",
        "content",
        "audit",
        str(tmp_path),
        "--json",
        "--summary",
    ]
