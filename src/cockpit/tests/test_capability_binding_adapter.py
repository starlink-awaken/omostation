"""Tests for the fixed Cockpit-to-root capability verification adapter."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from cockpit.adapters import capability_binding


def _envelope() -> dict[str, object]:
    return {
        "schema": "capability-admission-verification-request/v1",
        "material": {"opaque": "material"},
        "request": {"opaque": "request"},
        "expected": {"opaque": "expected"},
    }


def _receipt(*, status: str = "verified", schema: str = "capability-admission-verification-receipt/v1") -> str:
    return json.dumps({"schema": schema, "status": status, "value_indicator_policy": False})


def test_verified_envelope_uses_only_fixed_bounded_verifier_transport(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[list[str], dict[str, object]]] = []
    caller_environment = {
        "HOME": "/caller/home",
        "PATH": "/caller/bin",
        "OMO_DIR": "/caller/omo",
        "PYTHONPATH": "/caller/pythonpath",
        "PYTHONHOME": "/caller/pythonhome",
        "PYTHONUSERBASE": "/caller/user-site",
        "PYTHONPYCACHEPREFIX": "/caller/pycache",
        "PYTHONDONTWRITEBYTECODE": "0",
        "PYTHONIOENCODING": "latin-1",
        "PYTHONUTF8": "0",
        "PYTHONNOUSERSITE": "0",
    }
    for name, value in caller_environment.items():
        monkeypatch.setenv(name, value)

    def fake_run(argv: list[str], **kwargs: object) -> SimpleNamespace:
        calls.append((argv, kwargs))
        return SimpleNamespace(returncode=0, stdout=_receipt(), stderr="")

    monkeypatch.setattr(capability_binding.subprocess, "run", fake_run)

    assert capability_binding.verify_binding_envelope(_envelope()) is True
    assert calls == [
        (
            [
                sys.executable,
                str(capability_binding._WORKSPACE_ROOT / "bin" / "capability-sync.py"),
                "verify-material",
            ],
            {
                "cwd": str(capability_binding._WORKSPACE_ROOT),
                "input": json.dumps(_envelope(), ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
                    "utf-8"
                ),
                "capture_output": True,
                "check": False,
                "timeout": capability_binding._VERIFY_TIMEOUT_SECONDS,
                "shell": False,
                "env": {
                    "PYTHONDONTWRITEBYTECODE": "1",
                    "PYTHONIOENCODING": "utf-8",
                    "PYTHONUTF8": "1",
                    "PYTHONNOUSERSITE": "1",
                },
            },
        )
    ]


@pytest.mark.parametrize("envelope", [None, {}, [], "not-an-envelope", {"opaque": object()}])
def test_missing_empty_or_malformed_envelope_is_rejected_without_starting_verifier(
    monkeypatch: pytest.MonkeyPatch, envelope: object
) -> None:
    forbidden = pytest.fail
    monkeypatch.setattr(capability_binding.subprocess, "run", forbidden)

    assert capability_binding.verify_binding_envelope(envelope) is False


def test_oversize_envelope_is_rejected_without_starting_verifier(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(capability_binding.subprocess, "run", pytest.fail)
    envelope = {"payload": "x" * capability_binding._MAX_ENVELOPE_BYTES}

    assert capability_binding.verify_binding_envelope(envelope) is False


@pytest.mark.parametrize(
    "failure",
    [
        FileNotFoundError("verifier unavailable"),
        OSError("verifier unavailable"),
        subprocess.TimeoutExpired(cmd="verify-material", timeout=1),
    ],
)
def test_unavailable_or_timed_out_verifier_is_rejected(monkeypatch: pytest.MonkeyPatch, failure: BaseException) -> None:
    def fail(*_args: object, **_kwargs: object) -> None:
        raise failure

    monkeypatch.setattr(capability_binding.subprocess, "run", fail)

    assert capability_binding.verify_binding_envelope(_envelope()) is False


@pytest.mark.parametrize(
    ("returncode", "stdout"),
    [
        (4, _receipt()),
        (0, "not-json"),
        (0, "[]"),
        (0, _receipt(status="rejected")),
        (0, _receipt(status="pending")),
        (0, _receipt(schema="other-receipt/v1")),
    ],
)
def test_nonzero_malformed_nonmapping_or_nonverified_receipt_is_rejected(
    monkeypatch: pytest.MonkeyPatch, returncode: int, stdout: str
) -> None:
    monkeypatch.setattr(
        capability_binding.subprocess,
        "run",
        lambda *_args, **_kwargs: SimpleNamespace(returncode=returncode, stdout=stdout, stderr="private"),
    )

    assert capability_binding.verify_binding_envelope(_envelope()) is False


def test_verifier_output_and_envelope_are_never_emitted_or_written(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    private_value = "BINDING_MATERIAL_SENTINEL"
    envelope = _envelope()
    envelope["material"] = {"private": private_value}
    before = list(tmp_path.rglob("*"))
    monkeypatch.setenv("OMO_DIR", str(tmp_path / "caller-controlled-omo"))
    monkeypatch.setattr(
        capability_binding.subprocess,
        "run",
        lambda *_args, **_kwargs: SimpleNamespace(
            returncode=4,
            stdout=_receipt(status="rejected"),
            stderr=f"private verifier detail {private_value}",
        ),
    )

    assert capability_binding.verify_binding_envelope(envelope) is False
    assert capsys.readouterr() == ("", "")
    assert list(tmp_path.rglob("*")) == before
