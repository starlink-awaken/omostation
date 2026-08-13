from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "bin" / "gac" / "documents-chatgpt-tunnel.py"
TOOLS = [
    "workspace_context",
    "domain_context",
    "cards_status",
    "cards_check",
    "domain_facts_validation_status",
]


def _project_registry(tmp_path: Path) -> tuple[Path, Path]:
    workspace = tmp_path / "workspace"
    registry = (
        workspace / ".omo" / "_truth" / "registry" / "documents-domain-projects.yaml"
    )
    registry.parent.mkdir(parents=True)
    checker = workspace / "bin" / "gac" / "documents-chatgpt-tunnel.py"
    checker.parent.mkdir(parents=True)
    checker.write_text("# fixture checker\n", encoding="utf-8")
    entrypoint = (
        workspace / "projects" / "cockpit" / ".venv" / "bin" / "cockpit-documents-mcp"
    )
    entrypoint.parent.mkdir(parents=True)
    entrypoint.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    entrypoint.chmod(0o755)
    registry.write_text(
        yaml.safe_dump(
            {
                "clients": {
                    "chatgpt_web": {
                        "instruction_file": None,
                        "mcp_scope": "public_https_or_secure_tunnel",
                        "requires_developer_mode": True,
                        "setup_ref": "https://developers.openai.com/plugins/deploy/connect-chatgpt",
                        "tunnel_ref": "https://developers.openai.com/api/docs/guides/secure-mcp-tunnels",
                        "tunnel_contract": {
                            "owner": "workspace",
                            "checker_ref": "bin/gac/documents-chatgpt-tunnel.py",
                            "transport": "secure_mcp_tunnel",
                            "local_entrypoint": "cockpit-documents-mcp",
                            "tool_profile": "content-domain",
                            "tunnel_profile": "documents-readonly",
                            "tunnel_id_env": "DOCUMENTS_CHATGPT_TUNNEL_ID",
                            "api_key_env": "CONTROL_PLANE_API_KEY",
                        },
                    }
                },
                "profiles": {
                    "content-domain": {
                        "allowed_workspace_tools": TOOLS,
                        "execution_policy": "workspace_only",
                    }
                },
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    return registry, entrypoint


def _domain_registry(tmp_path: Path) -> Path:
    registry = tmp_path / "Documents" / "@公共" / "_control" / "L4-DOMAIN-REGISTRY.yaml"
    registry.parent.mkdir(parents=True)
    registry.write_text("apiVersion: l4/v1\n", encoding="utf-8")
    return registry


def _run(
    tmp_path: Path,
    command: str,
    *,
    tunnel_client: Path | None = None,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    assert SCRIPT.is_file(), "ChatGPT tunnel checker must exist"
    registry, _ = _project_registry(tmp_path)
    domain_registry = _domain_registry(tmp_path)
    arguments = [
        sys.executable,
        str(SCRIPT),
        command,
        "--project-registry",
        str(registry),
        "--domain-registry",
        str(domain_registry),
    ]
    if tunnel_client is not None:
        arguments.extend(["--tunnel-client", str(tunnel_client)])
    return subprocess.run(
        arguments,
        cwd=ROOT,
        env={
            **os.environ,
            "CONTROL_PLANE_API_KEY": "",
            "DOCUMENTS_CHATGPT_TUNNEL_ID": "",
            **(env or {}),
        },
        capture_output=True,
        text=True,
        check=False,
    )


def test_render_derives_secret_free_readonly_plan(tmp_path: Path) -> None:
    registry, entrypoint = _project_registry(tmp_path)
    domain_registry = _domain_registry(tmp_path)
    assert SCRIPT.is_file(), "ChatGPT tunnel checker must exist"

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
    payload = json.loads(result.stdout)
    assert payload == {
        "ok": True,
        "status": "plan",
        "transport": "secure_mcp_tunnel",
        "tunnel_profile": "documents-readonly",
        "mcp_command": str(entrypoint),
        "tool_profile": "content-domain",
        "allowed_tools": TOOLS,
        "required_environment": [
            "CONTROL_PLANE_API_KEY",
            "DOCUMENTS_CHATGPT_TUNNEL_ID",
        ],
        "tunnel_ref": "https://developers.openai.com/api/docs/guides/secure-mcp-tunnels",
    }
    assert "sk-" not in result.stdout
    assert "tunnel_0123456789abcdef0123456789abcdef" not in result.stdout


def test_check_fails_closed_when_runtime_prerequisites_are_missing(
    tmp_path: Path,
) -> None:
    missing_client = tmp_path / "missing-tunnel-client"

    result = _run(tmp_path, "check", tunnel_client=missing_client)

    assert result.returncode == 1
    payload = json.loads(result.stdout)
    assert payload["ok"] is False
    assert payload["status"] == "unavailable"
    assert payload["errors"] == [
        f"tunnel-client unavailable: {missing_client}",
        "CONTROL_PLANE_API_KEY is required",
        "DOCUMENTS_CHATGPT_TUNNEL_ID is required",
    ]


def test_check_reports_ready_without_emitting_credentials(tmp_path: Path) -> None:
    tunnel_client = tmp_path / "tunnel-client"
    doctor_log = tmp_path / "doctor.log"
    tunnel_client.write_text(
        '#!/bin/sh\nprintf "%s\\n" "$*" > "$TUNNEL_CLIENT_LOG"\nexit 0\n',
        encoding="utf-8",
    )
    tunnel_client.chmod(0o755)
    api_key = "sk-test-never-print"
    tunnel_id = "tunnel_0123456789abcdef0123456789abcdef"

    result = _run(
        tmp_path,
        "check",
        tunnel_client=tunnel_client,
        env={
            "CONTROL_PLANE_API_KEY": api_key,
            "DOCUMENTS_CHATGPT_TUNNEL_ID": tunnel_id,
            "TUNNEL_CLIENT_LOG": str(doctor_log),
        },
    )

    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {
        "ok": True,
        "status": "ready",
        "errors": [],
    }
    assert api_key not in result.stdout
    assert tunnel_id not in result.stdout
    assert doctor_log.read_text(encoding="utf-8").strip() == (
        "doctor --profile documents-readonly --explain"
    )


def test_check_fails_closed_when_tunnel_doctor_fails(tmp_path: Path) -> None:
    tunnel_client = tmp_path / "tunnel-client"
    tunnel_client.write_text(
        '#!/bin/sh\nprintf "%s\\n" "$CONTROL_PLANE_API_KEY" >&2\nexit 7\n',
        encoding="utf-8",
    )
    tunnel_client.chmod(0o755)
    api_key = "sk-test-never-print"
    tunnel_id = "tunnel_0123456789abcdef0123456789abcdef"

    result = _run(
        tmp_path,
        "check",
        tunnel_client=tunnel_client,
        env={
            "CONTROL_PLANE_API_KEY": api_key,
            "DOCUMENTS_CHATGPT_TUNNEL_ID": tunnel_id,
        },
    )

    assert result.returncode == 1
    assert json.loads(result.stdout) == {
        "ok": False,
        "status": "unavailable",
        "errors": ["tunnel-client doctor failed (exit 7)"],
    }
    assert api_key not in result.stdout
    assert tunnel_id not in result.stdout


def test_render_rejects_symlinked_authority_files(tmp_path: Path) -> None:
    registry, _ = _project_registry(tmp_path)
    domain_registry = _domain_registry(tmp_path)

    for authority, label in (
        (registry, "project registry"),
        (domain_registry, "domain registry"),
    ):
        target = authority.with_name(f"{authority.name}.target")
        authority.rename(target)
        authority.symlink_to(target)

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

        assert result.returncode == 1
        assert json.loads(result.stdout) == {
            "ok": False,
            "status": "error",
            "errors": [f"{label} must be a regular file: {authority}"],
        }

        authority.unlink()
        target.rename(authority)


def test_workspace_registry_declares_bounded_tunnel_contract() -> None:
    raw = yaml.safe_load(
        (
            ROOT / ".omo" / "_truth" / "registry" / "documents-domain-projects.yaml"
        ).read_text(encoding="utf-8")
    )

    assert raw["clients"]["chatgpt_web"]["tunnel_contract"] == {
        "owner": "workspace",
        "checker_ref": "bin/gac/documents-chatgpt-tunnel.py",
        "transport": "secure_mcp_tunnel",
        "local_entrypoint": "cockpit-documents-mcp",
        "tool_profile": "content-domain",
        "tunnel_profile": "documents-readonly",
        "tunnel_id_env": "DOCUMENTS_CHATGPT_TUNNEL_ID",
        "api_key_env": "CONTROL_PLANE_API_KEY",
    }
    assert raw["profiles"]["content-domain"]["allowed_workspace_tools"] == TOOLS


def test_required_phase_gate_covers_root_tunnel_contract() -> None:
    workflow = (ROOT / ".github" / "workflows" / "phase-gate-enforce.yml").read_text(
        encoding="utf-8"
    )

    for required in (
        "bin/gac/documents-chatgpt-tunnel.py",
        "tests/test_documents_chatgpt_tunnel.py",
        "projects/cockpit",
    ):
        assert required in workflow
