from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

from omo import mcp_server


def test_default_workspace_root_is_workspace_not_projects_directory() -> None:
    expected = Path(__file__).resolve().parents[3]

    assert mcp_server._default_workspace_root() == expected
    assert (expected / ".omo").is_dir()
    assert (expected / "projects" / "omo").is_dir()
    if "WORKSPACE_ROOT" not in os.environ:
        assert mcp_server.WORKSPACE_ROOT == expected


def test_workspace_root_environment_override_is_resolved(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    configured = tmp_path / "configured" / ".." / "workspace"
    monkeypatch.setenv("WORKSPACE_ROOT", str(configured))

    assert mcp_server._resolve_workspace_root() == configured.resolve()


@pytest.mark.asyncio
async def test_worker_dispatch_cli_is_pinned_to_workspace_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace_root = tmp_path / "workspace"
    unrelated_cwd = tmp_path / "elsewhere"
    workspace_root.mkdir()
    unrelated_cwd.mkdir()
    observed: dict[str, object] = {}

    def fake_run(argv: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        observed["argv"] = argv
        observed.update(kwargs)
        return subprocess.CompletedProcess(argv, 0, stdout="dispatched\n", stderr="")

    monkeypatch.setattr(mcp_server, "WORKSPACE_ROOT", workspace_root)
    monkeypatch.setattr(mcp_server.subprocess, "run", fake_run)
    monkeypatch.chdir(unrelated_cwd)

    result = await mcp_server.omo_worker_dispatch(
        mcp_server.DispatchRequest(task_id="TASK-1", worker_id="pi")
    )

    assert result == "dispatched\n"
    assert observed["cwd"] == workspace_root
    assert observed["argv"] == [
        "python3",
        "-m",
        "omo.cli",
        "worker",
        "dispatch",
        "TASK-1",
        "--worker",
        "pi",
    ]
