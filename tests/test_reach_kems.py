from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
from reach_gateway.kems import ManifestError, dispatch_manifest, prepare_manifest


def manifest() -> dict[str, object]:
    return {
        "schema": "bos.reachbridge.manifest.v1",
        "run_id": "bos-mesh-test-1",
        "documents": [
            {
                "source_ref": "vault://redacted/source.md",
                "sha256": "a" * 64,
                "bytes": 12,
            }
        ],
    }


def test_prepare_manifest_is_stable_and_redacted() -> None:
    first = prepare_manifest(manifest())
    second = prepare_manifest(manifest())
    assert first["dispatch_id"] == second["dispatch_id"]
    assert first["manifest_sha256"] == second["manifest_sha256"]
    assert "content" not in first["documents"][0]


def test_manifest_rejects_raw_content() -> None:
    payload = manifest()
    payload["documents"][0]["content"] = "secret"
    with pytest.raises(ManifestError, match="raw document content"):
        prepare_manifest(payload)


def test_dispatch_fails_without_explicit_transport(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("BOS_REACHBRIDGE_ENDPOINT", raising=False)
    monkeypatch.delenv("BOS_REACHBRIDGE_MODE", raising=False)
    with pytest.raises(RuntimeError, match="not configured"):
        dispatch_manifest(manifest())


def test_local_hermes_dispatch_is_idempotent(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    import reach_gateway

    relay = tmp_path / "relay.json"
    monkeypatch.setenv("BOS_REACHBRIDGE_MODE", "local_hermes")
    monkeypatch.delenv("BOS_REACHBRIDGE_ENDPOINT", raising=False)
    monkeypatch.setattr(reach_gateway, "RELAY_FILE", relay)
    monkeypatch.setattr(reach_gateway, "HERMES_BIN", tmp_path / "missing-hermes")

    result = dispatch_manifest(manifest())
    assert result.status == "queued"
    stored = json.loads(relay.read_text(encoding="utf-8"))
    assert stored["dispatch_id"] == result.dispatch_id
    assert "secret" not in relay.read_text(encoding="utf-8")
    again = dispatch_manifest(manifest())
    assert again.dispatch_id == result.dispatch_id


def test_http_dispatch_requires_and_confirms_dispatch_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    received: dict[str, object] = {}

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            length = int(self.headers["Content-Length"])
            received["body"] = json.loads(self.rfile.read(length).decode("utf-8"))
            received["idempotency_key"] = self.headers["Idempotency-Key"]
            payload = json.dumps(
                {"dispatch_id": received["body"]["dispatch_id"], "status": "accepted"}
            ).encode()
            self.send_response(202)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, format: str, *args: object) -> None:
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        monkeypatch.setenv(
            "BOS_REACHBRIDGE_ENDPOINT",
            f"http://127.0.0.1:{server.server_port}/dispatch",
        )
        monkeypatch.delenv("BOS_REACHBRIDGE_MODE", raising=False)
        result = dispatch_manifest(manifest())
    finally:
        server.shutdown()
        thread.join(timeout=2)

    assert result.status == "accepted"
    assert received["idempotency_key"] == result.dispatch_id
    assert "content" not in received["body"]["documents"][0]
