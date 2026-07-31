from __future__ import annotations

import json

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
