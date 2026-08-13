from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "bin" / "gac" / "documents-codex-profile.py"


def _project_registry(tmp_path: Path) -> Path:
    registry_dir = tmp_path / ".omo" / "_truth" / "registry"
    registry_dir.mkdir(parents=True, exist_ok=True)
    generator = tmp_path / "bin" / "gac" / "documents-codex-profile.py"
    generator.parent.mkdir(parents=True, exist_ok=True)
    generator.write_text("# fixture generator\n", encoding="utf-8")
    path = registry_dir / "documents-domain-projects.yaml"
    path.write_text(
        yaml.safe_dump(
            {
                "workspace_mcp": {
                    "server": "cockpit",
                    "read_tools": [
                        "workspace_context",
                        "domain_context",
                        "cards_status",
                        "cards_check",
                    ],
                },
                "clients": {
                    "codex": {
                        "profile_contract": {
                            "name": "documents",
                            "owner": "workspace",
                            "generator_ref": "bin/gac/documents-codex-profile.py",
                            "exclusive_mcp_server": "cockpit",
                            "approval_mode": "approve",
                            "skill_policy": "disable_user_local",
                        }
                    }
                },
                "profiles": {
                    "content-domain": {
                        "allowed_workspace_tools": [
                            "workspace_context",
                            "domain_context",
                            "cards_status",
                            "cards_check",
                        ]
                    }
                },
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    return path


def _fake_codex(
    tmp_path: Path,
    *,
    user_skill: Path,
    broken_skill: Path,
    plugin_skill: Path,
    system_skill: Path,
    mcp_servers: tuple[str, ...] = ("cockpit", "gitnexus", "web-reader"),
) -> Path:
    path = tmp_path / "fake-codex"
    payload = {
        "data": [
            {
                "cwd": str(tmp_path),
                "skills": [
                    {
                        "name": "user-skill",
                        "description": "user skill",
                        "enabled": True,
                        "path": str(user_skill),
                        "scope": "user",
                    },
                    {
                        "name": "documents",
                        "description": "plugin skill",
                        "enabled": True,
                        "path": str(plugin_skill),
                        "scope": "user",
                    },
                    {
                        "name": "system-skill",
                        "description": "system skill",
                        "enabled": True,
                        "path": str(system_skill),
                        "scope": "system",
                    },
                ],
                "errors": [
                    {
                        "path": str(broken_skill),
                        "message": "missing YAML frontmatter",
                    }
                ],
            }
        ]
    }
    path.write_text(
        f"""#!/usr/bin/env python3
import json
import sys

if sys.argv[1:] == ["mcp", "list", "--json"]:
    print(json.dumps([{{"name": name, "enabled": True}} for name in {mcp_servers!r}]))
    raise SystemExit(0)

if sys.argv[1:3] == ["app-server", "--listen"]:
    for line in sys.stdin:
        message = json.loads(line)
        if message.get("method") == "initialize":
            print(json.dumps({{"id": message["id"], "result": {{}}}}), flush=True)
        elif message.get("method") == "skills/list":
            print(json.dumps({{"id": message["id"], "result": {payload!r}}}), flush=True)
    raise SystemExit(0)

raise SystemExit(64)
""",
        encoding="utf-8",
    )
    path.chmod(0o755)
    return path


def _run(
    tmp_path: Path,
    command: str,
    *,
    profile_path: Path | None = None,
    mcp_servers: tuple[str, ...] = ("cockpit", "gitnexus", "web-reader"),
) -> subprocess.CompletedProcess[str]:
    user_root = tmp_path / "user-skills"
    user_skill = user_root / "valid" / "SKILL.md"
    broken_skill = user_root / "broken" / "SKILL.md"
    plugin_skill = tmp_path / "plugins" / "documents" / "SKILL.md"
    system_skill = user_root / ".system" / "system-skill" / "SKILL.md"
    for path in (user_skill, broken_skill, plugin_skill, system_skill):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("fixture\n", encoding="utf-8")
    codex = _fake_codex(
        tmp_path,
        user_skill=user_skill,
        broken_skill=broken_skill,
        plugin_skill=plugin_skill,
        system_skill=system_skill,
        mcp_servers=mcp_servers,
    )
    arguments = [
        sys.executable,
        str(SCRIPT),
        command,
        "--project-registry",
        str(_project_registry(tmp_path)),
        "--codex-bin",
        str(codex),
        "--cwd",
        str(tmp_path),
        "--user-skill-root",
        str(user_root),
    ]
    if profile_path is not None:
        arguments.extend(("--profile-path", str(profile_path)))
    return subprocess.run(
        arguments,
        cwd=ROOT,
        env={**os.environ, "PYTHONPATH": str(ROOT)},
        capture_output=True,
        text=True,
        check=False,
    )


def test_render_is_cockpit_only_and_disables_only_user_local_skills(
    tmp_path: Path,
) -> None:
    result = _run(tmp_path, "render")

    assert result.returncode == 0, result.stderr
    assert "[mcp_servers.cockpit]" in result.stdout
    assert 'default_tools_approval_mode = "approve"' in result.stdout
    assert (
        'enabled_tools = ["cards_check", "cards_status", "domain_context", '
        '"workspace_context"]'
    ) in result.stdout
    assert "[mcp_servers.gitnexus]\nenabled = false" in result.stdout
    assert "[mcp_servers.web-reader]\nenabled = false" in result.stdout
    assert str(tmp_path / "user-skills" / "valid" / "SKILL.md") in result.stdout
    assert str(tmp_path / "user-skills" / "broken" / "SKILL.md") in result.stdout
    assert str(tmp_path / "plugins" / "documents" / "SKILL.md") not in result.stdout
    assert (
        str(tmp_path / "user-skills" / ".system" / "system-skill" / "SKILL.md")
        not in result.stdout
    )


def test_install_then_check_detects_profile_drift(tmp_path: Path) -> None:
    profile_path = tmp_path / "codex" / "documents.config.toml"
    installed = _run(tmp_path, "install", profile_path=profile_path)

    assert installed.returncode == 0, installed.stderr
    install_payload = json.loads(installed.stdout)
    assert install_payload["ok"] is True
    assert profile_path.is_file()

    checked = _run(tmp_path, "check", profile_path=profile_path)
    assert checked.returncode == 0, checked.stderr
    assert json.loads(checked.stdout)["ok"] is True

    profile_path.write_text(
        profile_path.read_text(encoding="utf-8") + "\n# caller drift\n",
        encoding="utf-8",
    )
    drifted = _run(tmp_path, "check", profile_path=profile_path)
    assert drifted.returncode == 1
    assert json.loads(drifted.stdout)["errors"] == [f"profile drift: {profile_path}"]


def test_install_refuses_to_overwrite_existing_profile(tmp_path: Path) -> None:
    profile_path = tmp_path / "documents.config.toml"
    profile_path.write_text("caller owned\n", encoding="utf-8")

    result = _run(tmp_path, "install", profile_path=profile_path)

    assert result.returncode == 1
    assert profile_path.read_text(encoding="utf-8") == "caller owned\n"
    assert json.loads(result.stdout)["errors"] == [
        f"profile already exists with different content: {profile_path}"
    ]


def test_install_refreshes_a_stale_generated_profile(tmp_path: Path) -> None:
    profile_path = tmp_path / "documents.config.toml"
    profile_path.write_text(
        "# Generated by Workspace bin/gac/documents-codex-profile.py.\n# stale\n",
        encoding="utf-8",
    )

    result = _run(tmp_path, "install", profile_path=profile_path)

    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["ok"] is True
    assert "[mcp_servers.cockpit]" in profile_path.read_text(encoding="utf-8")
    assert "# stale" not in profile_path.read_text(encoding="utf-8")


def test_install_repairs_generated_profile_permissions(tmp_path: Path) -> None:
    profile_path = tmp_path / "documents.config.toml"
    rendered = _run(tmp_path, "render")
    assert rendered.returncode == 0, rendered.stderr
    profile_path.write_text(rendered.stdout, encoding="utf-8")
    profile_path.chmod(0o644)

    result = _run(tmp_path, "install", profile_path=profile_path)

    assert result.returncode == 0, result.stderr
    assert profile_path.stat().st_mode & 0o777 == 0o600


def test_install_refuses_matching_profile_through_symlink(tmp_path: Path) -> None:
    target = tmp_path / "caller-owned.config.toml"
    rendered = _run(tmp_path, "render")
    assert rendered.returncode == 0, rendered.stderr
    target.write_text(rendered.stdout, encoding="utf-8")
    profile_path = tmp_path / "documents.config.toml"
    profile_path.symlink_to(target)

    result = _run(tmp_path, "install", profile_path=profile_path)

    assert result.returncode == 1
    assert profile_path.is_symlink()
    assert json.loads(result.stdout)["errors"] == [
        f"profile must be a regular file owned by the generator: {profile_path}"
    ]


def test_missing_cockpit_server_fails_closed(tmp_path: Path) -> None:
    result = _run(tmp_path, "render", mcp_servers=("gitnexus",))

    assert result.returncode == 1
    assert json.loads(result.stdout)["errors"] == [
        "required Codex MCP server is missing: cockpit"
    ]


def test_required_phase_gate_covers_profile_generator_and_tests() -> None:
    workflow = (ROOT / ".github" / "workflows" / "phase-gate-enforce.yml").read_text(
        encoding="utf-8"
    )

    assert "bin/gac/documents-codex-profile.py" in workflow
    assert "tests/test_documents_codex_profile.py" in workflow
