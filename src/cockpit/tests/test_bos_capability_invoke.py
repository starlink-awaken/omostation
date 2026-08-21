"""Contract tests for governed Cockpit BOS capability invocation."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from types import SimpleNamespace

from cockpit.commands import bos as bos_mod


def _service() -> SimpleNamespace:
    return SimpleNamespace(
        uri="bos://capability/swarm/run",
        package="toolbox/swarm",
        domain="capability",
        command=["echo", "must-never-run"],
        description="swarm",
    )


def test_match_capability_requires_full_uri_or_canonical_id() -> None:
    services = [_service()]

    assert bos_mod._match_capability_service(services, "bos://capability/swarm/run") is services[0]
    assert bos_mod._match_capability_service(services, "bos-service:bos://capability/swarm/run") is services[0]
    assert bos_mod._match_capability_service(services, "swarm") is None
    assert bos_mod._match_capability_service(services, "capability/swarm") is None


def test_cmd_bos_capability_invoke_delegates_to_fixed_gateway_cli(monkeypatch, capsys, tmp_path: Path) -> None:
    payload = tmp_path / "payload.json"
    payload.write_text('{"scope":"bounded"}', encoding="utf-8")
    monkeypatch.setattr(bos_mod, "_load_capability_services", lambda: [_service()])
    calls = []

    def fake_run(command, **kwargs):
        calls.append((command, kwargs))
        return SimpleNamespace(
            returncode=0,
            stdout=json.dumps(
                {
                    "schema": "capability-invocation-receipt/v1",
                    "operation": "invoke",
                    "status": "succeeded",
                    "capability_id": "bos-service:bos://capability/swarm/run",
                    "invocation_attempted": True,
                }
            ),
            stderr="",
        )

    monkeypatch.setattr(bos_mod.subprocess, "run", fake_run)
    code = bos_mod.cmd_bos_capability(
        argparse.Namespace(
            capability_command="invoke",
            capability_service="bos://capability/swarm/run",
            capability_input_json=payload,
            global_output="json",
        )
    )

    assert code == 0
    command, kwargs = calls[0]
    assert command == [
        sys.executable,
        str(bos_mod._WORKSPACE / "bin" / "capability-sync.py"),
        "invoke",
        "--id",
        "bos-service:bos://capability/swarm/run",
        "--input-json",
        str(payload),
    ]
    assert kwargs == {"check": False, "capture_output": True, "text": True}
    assert "must-never-run" not in " ".join(command)
    assert json.loads(capsys.readouterr().out)["status"] == "succeeded"


def test_cmd_bos_capability_invoke_rejects_short_selector(monkeypatch, capsys, tmp_path: Path) -> None:
    payload = tmp_path / "payload.json"
    payload.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(bos_mod, "_load_capability_services", lambda: [_service()])

    code = bos_mod.cmd_bos_capability(
        argparse.Namespace(
            capability_command="invoke",
            capability_service="swarm",
            capability_input_json=payload,
        )
    )

    assert code == 1
    assert "精确" in capsys.readouterr().out


def test_cmd_bos_capability_invoke_does_not_echo_gateway_stderr(monkeypatch, capsys, tmp_path: Path) -> None:
    payload = tmp_path / "payload.json"
    payload.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(bos_mod, "_load_capability_services", lambda: [_service()])
    monkeypatch.setattr(
        bos_mod.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(returncode=5, stdout="not-json", stderr="SECRET_ENV=value"),
    )

    code = bos_mod.cmd_bos_capability(
        argparse.Namespace(
            capability_command="invoke",
            capability_service="bos://capability/swarm/run",
            capability_input_json=payload,
        )
    )

    output = capsys.readouterr().out
    assert code == 5
    assert "SECRET_ENV" not in output
    assert "CAPABILITY_GATEWAY_INVALID_RECEIPT" in output


def test_cmd_bos_capability_invoke_strips_unknown_receipt_fields(monkeypatch, capsys, tmp_path: Path) -> None:
    payload = tmp_path / "payload.json"
    payload.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(bos_mod, "_load_capability_services", lambda: [_service()])
    malicious_receipt = {
        "schema": "capability-invocation-receipt/v1",
        "operation": "invoke",
        "status": "rejected",
        "capability_id": "bos-service:bos://capability/swarm/run",
        "invocation_attempted": False,
        "payload": "SECRET_PAYLOAD",
        "path": "/private/secret",
        "error": "SECRET_ENV=value",
    }
    monkeypatch.setattr(
        bos_mod.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(
            returncode=5,
            stdout=json.dumps(malicious_receipt),
            stderr="",
        ),
    )

    code = bos_mod.cmd_bos_capability(
        argparse.Namespace(
            capability_command="invoke",
            capability_service="bos://capability/swarm/run",
            capability_input_json=payload,
        )
    )

    output = capsys.readouterr().out
    assert code == 5
    assert "SECRET_PAYLOAD" not in output
    assert "/private/secret" not in output
    assert "SECRET_ENV" not in output
    assert set(json.loads(output)) == {
        "schema",
        "operation",
        "status",
        "capability_id",
        "invocation_attempted",
    }
