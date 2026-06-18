from __future__ import annotations

import argparse
from pathlib import Path

from cockpit.commands import governance


def test_cmd_governance_surfaces_routes_to_omo_governance(
    monkeypatch, tmp_path: Path
) -> None:
    recorded: dict[str, object] = {}

    def fake_run(cmd, cwd):
        recorded["cmd"] = cmd
        recorded["cwd"] = cwd

        class _Result:
            returncode = 0

        return _Result()

    monkeypatch.setattr(governance, "resolve_workspace_root", lambda: tmp_path)
    monkeypatch.setattr(governance.subprocess, "run", fake_run)

    rc = governance.cmd_governance(
        argparse.Namespace(subcommand="surfaces", extra_args=["--json"])
    )

    assert rc == 0
    cmd = recorded["cmd"]
    assert isinstance(cmd, list)
    assert cmd[:10] == [
        "uv",
        "run",
        "--directory",
        str(tmp_path / "projects" / "omo"),
        "python",
        "-W",
        "ignore::DeprecationWarning",
        "-m",
        "omo.cli",
        "governance",
    ]
    assert cmd[10:] == ["surfaces", "--json"]
    assert recorded["cwd"] == str(tmp_path)


def test_cmd_governance_ingress_task_routes_to_omo_governance(
    monkeypatch, tmp_path: Path
) -> None:
    recorded: dict[str, object] = {}

    def fake_run(cmd, cwd):
        recorded["cmd"] = cmd
        recorded["cwd"] = cwd

        class _Result:
            returncode = 0

        return _Result()

    monkeypatch.setattr(governance, "resolve_workspace_root", lambda: tmp_path)
    monkeypatch.setattr(governance.subprocess, "run", fake_run)

    rc = governance.cmd_governance(
        argparse.Namespace(
            subcommand="ingress-task",
            extra_args=["task.yaml", "--ingress-plane", "projects/c2g"],
        )
    )

    assert rc == 0
    cmd = recorded["cmd"]
    assert isinstance(cmd, list)
    assert cmd[10:] == [
        "ingress-task",
        "task.yaml",
        "--ingress-plane",
        "projects/c2g",
    ]


def test_cmd_governance_ingress_debt_routes_to_omo_governance(
    monkeypatch, tmp_path: Path
) -> None:
    recorded: dict[str, object] = {}

    def fake_run(cmd, cwd):
        recorded["cmd"] = cmd
        recorded["cwd"] = cwd

        class _Result:
            returncode = 0

        return _Result()

    monkeypatch.setattr(governance, "resolve_workspace_root", lambda: tmp_path)
    monkeypatch.setattr(governance.subprocess, "run", fake_run)

    rc = governance.cmd_governance(
        argparse.Namespace(
            subcommand="ingress-debt",
            extra_args=["debt.yaml", "--ingress-plane", "projects/aetherforge"],
        )
    )

    assert rc == 0
    cmd = recorded["cmd"]
    assert isinstance(cmd, list)
    assert cmd[10:] == [
        "ingress-debt",
        "debt.yaml",
        "--ingress-plane",
        "projects/aetherforge",
    ]
