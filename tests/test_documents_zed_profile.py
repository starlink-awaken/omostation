from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "bin" / "gac" / "documents-zed-profile.py"
TOOLS = ("cards_check", "cards_status", "domain_context", "workspace_context")


def _project_registry(tmp_path: Path, *, tools: tuple[str, ...] = TOOLS) -> Path:
    registry_dir = tmp_path / ".omo" / "_truth" / "registry"
    registry_dir.mkdir(parents=True, exist_ok=True)
    generator = tmp_path / "bin" / "gac" / "documents-zed-profile.py"
    generator.parent.mkdir(parents=True, exist_ok=True)
    generator.write_text("# fixture generator\n", encoding="utf-8")
    path = registry_dir / "documents-domain-projects.yaml"
    path.write_text(
        yaml.safe_dump(
            {
                "workspace_mcp": {
                    "server": "cockpit",
                    "read_tools": list(tools),
                },
                "clients": {
                    "zed": {
                        "profile_contract": {
                            "name": "documents",
                            "owner": "workspace",
                            "generator_ref": "bin/gac/documents-zed-profile.py",
                            "exclusive_mcp_server": "cockpit",
                            "approval_mode": "allow_read_tools",
                            "builtin_tool_policy": "disable_all",
                        }
                    }
                },
                "profiles": {
                    "content-domain": {"allowed_workspace_tools": list(tools)}
                },
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    return path


def _settings(tmp_path: Path, *, cockpit: object | None = None) -> Path:
    path = tmp_path / "zed" / "settings.json"
    path.parent.mkdir(parents=True)
    if cockpit is None:
        cockpit = {
            "command": "/opt/homebrew/bin/cockpit-mcp",
            "args": [],
            "env": {"WORKSPACE_ROOT": "/workspace"},
            "enabled": True,
        }
    path.write_text(
        json.dumps(
            {
                "theme": "One Dark",
                "context_servers": {
                    "cockpit": cockpit,
                    "other": {"command": "other-mcp", "enabled": True},
                },
                "agent": {
                    "tool_permissions": {
                        "default": "confirm",
                        "tools": {"move_path": {"default": "allow"}},
                    }
                },
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    path.chmod(0o600)
    return path


def _run(
    tmp_path: Path,
    command: str,
    *,
    settings_path: Path | None = None,
    tools: tuple[str, ...] = TOOLS,
) -> subprocess.CompletedProcess[str]:
    settings_path = settings_path or _settings(tmp_path)
    return subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            command,
            "--project-registry",
            str(_project_registry(tmp_path, tools=tools)),
            "--settings-path",
            str(settings_path),
        ],
        cwd=ROOT,
        env={**os.environ, "PYTHONPATH": str(ROOT)},
        capture_output=True,
        text=True,
        check=False,
    )


def _expected_profile(*, tools: tuple[str, ...] = TOOLS) -> dict[str, object]:
    return {
        "name": "Documents",
        "tools": {},
        "enable_all_context_servers": False,
        "context_servers": {"cockpit": {"tools": {tool: True for tool in tools}}},
    }


def test_render_contains_only_cockpit_read_tools(tmp_path: Path) -> None:
    result = _run(tmp_path, "render")

    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {
        "profile_id": "documents",
        "profile": _expected_profile(),
        "tool_permissions": {
            f"mcp:cockpit:{tool}": {"default": "allow"} for tool in TOOLS
        },
    }


def test_install_preserves_unrelated_settings_and_is_idempotent(tmp_path: Path) -> None:
    settings_path = _settings(tmp_path)
    before = json.loads(settings_path.read_text(encoding="utf-8"))

    first = _run(tmp_path, "install", settings_path=settings_path)
    second = _run(tmp_path, "install", settings_path=settings_path)

    assert first.returncode == 0, first.stderr
    assert second.returncode == 0, second.stderr
    installed = json.loads(settings_path.read_text(encoding="utf-8"))
    assert installed["theme"] == before["theme"]
    assert installed["context_servers"] == before["context_servers"]
    assert installed["agent"]["tool_permissions"]["default"] == "confirm"
    assert installed["agent"]["tool_permissions"]["tools"]["move_path"] == {
        "default": "allow"
    }
    assert installed["agent"]["profiles"]["documents"] == _expected_profile()
    assert settings_path.stat().st_mode & 0o777 == 0o600
    assert json.loads(first.stdout)["status"] == "installed"
    assert json.loads(second.stdout)["status"] == "unchanged"


def test_install_migrates_a_prior_generated_profile_for_an_expanded_contract(
    tmp_path: Path,
) -> None:
    settings_path = _settings(tmp_path)
    expanded_tools = (*TOOLS, "domain_model_freshness_status")

    assert _run(tmp_path, "install", settings_path=settings_path).returncode == 0
    result = _run(
        tmp_path,
        "install",
        settings_path=settings_path,
        tools=expanded_tools,
    )

    assert result.returncode == 0, result.stderr
    settings = json.loads(settings_path.read_text(encoding="utf-8"))
    assert settings["agent"]["profiles"]["documents"] == _expected_profile(
        tools=expanded_tools
    )
    assert settings["agent"]["tool_permissions"]["tools"] == {
        "move_path": {"default": "allow"},
        **{f"mcp:cockpit:{tool}": {"default": "allow"} for tool in expanded_tools},
    }
    assert json.loads(result.stdout)["status"] == "installed"


def test_install_refuses_documents_profile_with_custom_cockpit_tool_subset(
    tmp_path: Path,
) -> None:
    settings_path = _settings(tmp_path)
    expanded_tools = (*TOOLS, "domain_model_freshness_status")
    assert _run(tmp_path, "install", settings_path=settings_path).returncode == 0
    settings = json.loads(settings_path.read_text(encoding="utf-8"))
    settings["agent"]["profiles"]["documents"]["context_servers"]["cockpit"]["tools"][
        "domain_context"
    ] = False
    settings_path.write_text(json.dumps(settings), encoding="utf-8")

    result = _run(
        tmp_path,
        "install",
        settings_path=settings_path,
        tools=expanded_tools,
    )

    assert result.returncode == 1
    assert json.loads(result.stdout)["errors"] == [
        "agent.profiles.documents already exists with different content"
    ]
    assert json.loads(settings_path.read_text(encoding="utf-8")) == settings


def test_check_detects_profile_drift(tmp_path: Path) -> None:
    settings_path = _settings(tmp_path)
    assert _run(tmp_path, "install", settings_path=settings_path).returncode == 0
    settings = json.loads(settings_path.read_text(encoding="utf-8"))
    settings["agent"]["profiles"]["documents"]["tools"] = {"terminal": True}
    settings_path.write_text(json.dumps(settings), encoding="utf-8")

    result = _run(tmp_path, "check", settings_path=settings_path)

    assert result.returncode == 1
    assert json.loads(result.stdout)["errors"] == [
        "agent.profiles.documents does not match the Workspace contract"
    ]


def test_install_refuses_caller_owned_profile(tmp_path: Path) -> None:
    settings_path = _settings(tmp_path)
    settings = json.loads(settings_path.read_text(encoding="utf-8"))
    settings["agent"]["profiles"] = {"documents": {"name": "Mine"}}
    settings_path.write_text(json.dumps(settings), encoding="utf-8")

    result = _run(tmp_path, "install", settings_path=settings_path)

    assert result.returncode == 1
    assert json.loads(result.stdout)["errors"] == [
        "agent.profiles.documents already exists with different content"
    ]
    assert json.loads(settings_path.read_text(encoding="utf-8")) == settings


def test_install_refuses_conflicting_tool_permission(tmp_path: Path) -> None:
    settings_path = _settings(tmp_path)
    settings = json.loads(settings_path.read_text(encoding="utf-8"))
    key = "mcp:cockpit:domain_context"
    settings["agent"]["tool_permissions"]["tools"][key] = {"default": "deny"}
    settings_path.write_text(json.dumps(settings), encoding="utf-8")

    result = _run(tmp_path, "install", settings_path=settings_path)

    assert result.returncode == 1
    assert json.loads(result.stdout)["errors"] == [
        f"agent.tool_permissions.tools.{key} conflicts with the Workspace contract"
    ]
    assert json.loads(settings_path.read_text(encoding="utf-8")) == settings


def test_missing_or_disabled_cockpit_server_fails_closed(tmp_path: Path) -> None:
    settings_path = _settings(
        tmp_path, cockpit={"command": "cockpit-mcp", "enabled": False}
    )

    result = _run(tmp_path, "render", settings_path=settings_path)

    assert result.returncode == 1
    assert json.loads(result.stdout)["errors"] == [
        "context_servers.cockpit.enabled must be true"
    ]


def test_install_refuses_settings_symlink(tmp_path: Path) -> None:
    target = _settings(tmp_path)
    settings_path = tmp_path / "settings-link.json"
    settings_path.symlink_to(target)

    result = _run(tmp_path, "install", settings_path=settings_path)

    assert result.returncode == 1
    assert json.loads(result.stdout)["errors"] == [
        f"settings must be a regular file: {settings_path}"
    ]


def test_required_phase_gate_covers_zed_profile_generator_and_tests() -> None:
    workflow = (ROOT / ".github" / "workflows" / "phase-gate-enforce.yml").read_text(
        encoding="utf-8"
    )

    assert "bin/gac/documents-zed-profile.py" in workflow
    assert "tests/test_documents_zed_profile.py" in workflow
