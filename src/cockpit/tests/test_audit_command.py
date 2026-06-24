from __future__ import annotations

import argparse
from pathlib import Path

from cockpit.commands import audit


def test_cmd_audit_json_keeps_banner_off_stdout(monkeypatch, capsys) -> None:
    class _Result:
        returncode = 0
        stdout = '{"total": 100, "grade": "A+", "dims": {}}'
        stderr = "inner progress"

    monkeypatch.setattr(audit, "WORKSPACE_AUDIT", Path(__file__))
    monkeypatch.setattr(audit.subprocess, "run", lambda *args, **kwargs: _Result())

    rc = audit.cmd_audit(
        argparse.Namespace(
            dim="governance",
            format="json",
            output=None,
            since="7d",
        )
    )

    assert rc == 0
    captured = capsys.readouterr()
    assert captured.out.strip() == _Result.stdout
    assert "Omostation 6 维度全方位审计" in captured.err
