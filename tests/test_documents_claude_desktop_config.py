from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "bin" / "gac" / "documents-claude-desktop-config.py"


def _project_registry(tmp_path: Path) -> tuple[Path, Path]:
    workspace = tmp_path / "workspace"
    registry_dir = workspace / ".omo" / "_truth" / "registry"
    registry_dir.mkdir(parents=True, exist_ok=True)
    generator = workspace / "bin" / "gac" / "documents-claude-desktop-config.py"
    generator.parent.mkdir(parents=True, exist_ok=True)
    generator.write_text("# fixture generator\n", encoding="utf-8")
    cockpit = workspace / "projects" / "cockpit" / ".venv" / "bin" / "cockpit-mcp"
    cockpit.parent.mkdir(parents=True, exist_ok=True)
    cockpit.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    cockpit.chmod(0o755)

    registry = registry_dir / "documents-domain-projects.yaml"
    registry.write_text(
        yaml.safe_dump(
            {
                "workspace_mcp": {
                    "server": "cockpit",
                    "entrypoint": "cockpit-mcp",
                    "transport": "stdio",
                },
                "clients": {
                    "claude": {
                        "instruction_file": "CLAUDE.md",
                        "mcp_scope": "user",
                        "config_contract": {
                            "owner": "workspace",
                            "generator_ref": "bin/gac/documents-claude-desktop-config.py",
                            "configuration_surface": "native_json",
                            "config_path": "~/Library/Application Support/Claude/claude_desktop_config.json",
                            "managed_mcp_server": "cockpit",
                            "preserve_unrelated_servers": True,
                        },
                    }
                },
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    return registry, cockpit


def _domain_registry(tmp_path: Path) -> Path:
    documents = tmp_path / "Documents"
    registry = documents / "@公共" / "_control" / "L4-DOMAIN-REGISTRY.yaml"
    registry.parent.mkdir(parents=True, exist_ok=True)
    registry.write_text("apiVersion: l4/v1\n", encoding="utf-8")
    (documents / "CLAUDE.md").write_text("# Documents gateway\n", encoding="utf-8")
    return registry


def _settings(tmp_path: Path, payload: object | None = None) -> Path:
    settings = tmp_path / "home" / "Claude" / "claude_desktop_config.json"
    settings.parent.mkdir(parents=True, exist_ok=True)
    if payload is None:
        payload = {
            "provider": {"third-party": {"kind": "openai-compatible"}},
            "mcpServers": {"other": {"command": "other-mcp", "args": ["--stdio"]}},
        }
    settings.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    settings.chmod(0o644)
    return settings


def _run(
    tmp_path: Path,
    command: str,
    *,
    settings_path: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    registry, _ = _project_registry(tmp_path)
    domain_registry = _domain_registry(tmp_path)
    settings = settings_path or _settings(tmp_path)
    return subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            command,
            "--project-registry",
            str(registry),
            "--domain-registry",
            str(domain_registry),
            "--settings-path",
            str(settings),
        ],
        cwd=ROOT,
        env={**os.environ, "PYTHONPATH": str(ROOT)},
        capture_output=True,
        text=True,
        check=False,
    )


def test_render_derives_claude_cockpit_projection(tmp_path: Path) -> None:
    registry, cockpit = _project_registry(tmp_path)
    domain_registry = _domain_registry(tmp_path)

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "render",
            "--project-registry",
            str(registry),
            "--domain-registry",
            str(domain_registry),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {
        "mcpServers": {
            "cockpit": {
                "command": str(cockpit),
                "args": [],
                "env": {
                    "WORKSPACE_ROOT": str(registry.parents[3]),
                    "L4_DOCUMENTS_ROOT": str(domain_registry.parents[2]),
                    "L4_DOMAIN_REGISTRY": str(domain_registry),
                },
            }
        }
    }


def test_install_preserves_unrelated_settings_and_is_idempotent(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    before = json.loads(settings.read_text(encoding="utf-8"))

    first = _run(tmp_path, "install", settings_path=settings)
    second = _run(tmp_path, "install", settings_path=settings)

    assert first.returncode == 0, first.stderr
    assert second.returncode == 0, second.stderr
    installed = json.loads(settings.read_text(encoding="utf-8"))
    assert installed["provider"] == before["provider"]
    assert installed["mcpServers"]["other"] == before["mcpServers"]["other"]
    assert installed["mcpServers"]["cockpit"]["args"] == []
    assert settings.stat().st_mode & 0o777 == 0o600
    assert json.loads(first.stdout)["status"] == "installed"
    assert json.loads(first.stdout)["restart_required"] is True
    assert json.loads(second.stdout)["status"] == "unchanged"
    assert json.loads(second.stdout)["restart_required"] is False


def test_check_fails_closed_for_drift_and_insecure_mode(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    assert _run(tmp_path, "install", settings_path=settings).returncode == 0
    payload = json.loads(settings.read_text(encoding="utf-8"))
    payload["mcpServers"]["cockpit"]["env"]["WORKSPACE_ROOT"] = "/wrong"
    settings.write_text(json.dumps(payload), encoding="utf-8")
    settings.chmod(0o644)

    result = _run(tmp_path, "check", settings_path=settings)

    assert result.returncode == 1
    errors = json.loads(result.stdout)["errors"]
    assert "mcpServers.cockpit does not match the Workspace contract" in errors
    assert "settings mode must be 0600" in errors


def test_install_refuses_settings_symlink(tmp_path: Path) -> None:
    target = _settings(tmp_path)
    settings = tmp_path / "settings-link.json"
    settings.symlink_to(target)

    result = _run(tmp_path, "install", settings_path=settings)

    assert result.returncode == 1
    assert json.loads(result.stdout)["errors"] == [
        f"settings must be a regular file: {settings}"
    ]


def test_check_does_not_create_missing_config(tmp_path: Path) -> None:
    settings = tmp_path / "home" / "Claude" / "claude_desktop_config.json"

    result = _run(tmp_path, "check", settings_path=settings)

    assert result.returncode == 1
    assert not settings.exists()
    assert json.loads(result.stdout)["errors"] == [f"settings unavailable: {settings}"]


def test_required_phase_gate_covers_claude_config_generator_and_tests() -> None:
    workflow = (ROOT / ".github" / "workflows" / "phase-gate-enforce.yml").read_text(
        encoding="utf-8"
    )

    assert "bin/gac/documents-claude-desktop-config.py" in workflow
    assert "tests/test_documents_claude_desktop_config.py" in workflow
