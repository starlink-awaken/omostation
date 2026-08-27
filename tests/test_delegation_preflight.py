from __future__ import annotations

import importlib.util
import json
import sys
import urllib.request
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "bin" / "delegation-preflight.py"
SPEC = importlib.util.spec_from_file_location("delegation_preflight", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
PREFLIGHT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PREFLIGHT)


def _ctx(**overrides: object) -> SimpleNamespace:
    values = {
        "base_url": "http://127.0.0.1:9290/v1",
        "api_key": None,
        "expected_models": [],
        "required_models": [],
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_http_probe_uses_configured_bearer_credential(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: list[urllib.request.Request] = []

    class Response:
        status = 200

        def __enter__(self) -> Response:
            return self

        def __exit__(self, *_args: object) -> None:
            return None

        def read(self, _limit: int) -> bytes:
            return b'{"data":[{"id":"coding"}]}'

    def fake_urlopen(request: urllib.request.Request, timeout: int) -> Response:
        assert timeout == PREFLIGHT.HTTP_TIMEOUT
        captured.append(request)
        return Response()

    monkeypatch.setattr(PREFLIGHT.urllib.request, "urlopen", fake_urlopen)

    status, _body, error = PREFLIGHT._http_get(
        "http://127.0.0.1:9290/v1",
        "/models",
        api_key="test-key",
    )

    assert status == 200
    assert error is None
    assert captured[0].get_header("Authorization") == "Bearer test-key"


@pytest.mark.parametrize(
    ("status", "body", "reason_fragment"),
    [
        (401, b"", "authentication"),
        (403, b"", "authorization"),
        (404, b"", "HTTP 404"),
        (500, b"", "HTTP 500"),
        (200, b"not-json", "valid JSON"),
        (200, b'{"data": {}}', "data list"),
        (200, b'{"data": []}', "no models"),
    ],
)
def test_endpoint_requires_authorized_openai_model_inventory(
    monkeypatch: pytest.MonkeyPatch,
    status: int,
    body: bytes,
    reason_fragment: str,
) -> None:
    monkeypatch.setattr(PREFLIGHT, "_http_get", lambda *_args, **_kwargs: (status, body, None))

    check_status, reason = PREFLIGHT.check_omlxc_endpoint_reachable(_ctx())

    assert check_status == "FAIL"
    assert reason_fragment in reason


def test_endpoint_passes_for_nonempty_openai_model_inventory(monkeypatch: pytest.MonkeyPatch) -> None:
    body = json.dumps({"object": "list", "data": [{"id": "coding"}]}).encode()
    monkeypatch.setattr(PREFLIGHT, "_http_get", lambda *_args, **_kwargs: (200, body, None))

    check_status, reason = PREFLIGHT.check_omlxc_endpoint_reachable(_ctx())

    assert check_status == "PASS"
    assert "1 model" in reason


def test_endpoint_requires_bound_agent_model_in_authorized_inventory(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    body = json.dumps({"object": "list", "data": [{"id": "coder"}]}).encode()
    monkeypatch.setattr(PREFLIGHT, "_http_get", lambda *_args, **_kwargs: (200, body, None))

    check_status, reason = PREFLIGHT.check_omlxc_endpoint_reachable(
        _ctx(required_models=["coding"]),
    )

    assert check_status == "FAIL"
    assert "bound agent models" in reason
    assert "coding" in reason


def test_bound_model_extraction_uses_only_real_omlxc_agent_bindings() -> None:
    data = {
        "provider": {
            "omlxc": {"models": {"configured-but-unbound": {}}},
            "other": {"models": {"remote": {}}},
        },
        "agent": {
            "local-a": {"model": "omlxc/coding"},
            "local-b": {"model": "omlxc/coding"},
            "remote": {"model": "other/remote"},
            "malformed": {"model": "coding"},
            "not-a-record": None,
        },
    }

    assert PREFLIGHT.extract_bound_provider_models(data, "omlxc") == ["coding"]


@pytest.mark.parametrize(
    ("status", "body", "reason_fragment"),
    [
        (401, b"", "authentication"),
        (403, b"", "authorization"),
        (500, b"", "HTTP 500"),
        (200, b"not-json", "valid JSON"),
        (200, b'{"data": []}', "no models"),
        (200, b'{"data": [{}, null, {"id": " "}]}', "no models"),
    ],
)
def test_gateway_inventory_never_passes_an_unauthorized_or_empty_response(
    monkeypatch: pytest.MonkeyPatch,
    status: int,
    body: bytes,
    reason_fragment: str,
) -> None:
    monkeypatch.setattr(PREFLIGHT, "_http_get", lambda *_args, **_kwargs: (status, body, None))

    check_status, reason = PREFLIGHT.check_gateway_models_available(_ctx())

    assert check_status == "WARN"
    assert reason_fragment in reason


def test_gateway_inventory_never_passes_transport_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        PREFLIGHT,
        "_http_get",
        lambda *_args, **_kwargs: (None, b"", OSError("connection refused")),
    )

    check_status, reason = PREFLIGHT.check_gateway_models_available(_ctx())

    assert check_status == "WARN"
    assert "transport" in reason


def test_single_gateway_check_reports_warn_without_blocking_exit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    config = tmp_path / "opencode.json"
    config.write_text(
        json.dumps(
            {
                "provider": {
                    "omlxc": {
                        "options": {"baseURL": "http://127.0.0.1:9290/v1"},
                        "models": {},
                    }
                },
                "agent": {"local": {"model": "omlxc/coding"}},
            }
        )
    )
    monkeypatch.setattr(PREFLIGHT, "_http_get", lambda *_args, **_kwargs: (401, b"", None))
    monkeypatch.setattr(
        sys,
        "argv",
        [
            str(SCRIPT),
            "--json",
            "--check",
            "gateway_models_available",
            "--opencode-config",
            str(config),
        ],
    )

    exit_code = PREFLIGHT.main()
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["preflight"] == "WARN"
    assert payload["checks"][0]["status"] == "WARN"


def test_single_endpoint_check_exits_nonzero_for_auth_failure(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(PREFLIGHT, "_http_get", lambda *_args, **_kwargs: (401, b"", None))
    monkeypatch.setattr(
        sys,
        "argv",
        [
            str(SCRIPT),
            "--json",
            "--check",
            "omlxc_endpoint_reachable",
            "--base-url",
            "http://127.0.0.1:9290/v1",
        ],
    )

    exit_code = PREFLIGHT.main()
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 1
    assert payload["preflight"] == "FAIL"
    assert payload["checks"][0]["status"] == "FAIL"
