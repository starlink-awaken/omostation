from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.kems_dispatch_receipt import ReceiptError, build_receipt, write_receipt


def manifest() -> dict[str, object]:
    return {
        "schema": "bos.reachbridge.manifest.v1",
        "run_id": "run-001",
        "documents": [
            {
                "source_ref": "vault://redacted/source-1",
                "sha256": "a" * 64,
                "size": 12,
            }
        ],
    }


def response_for(
    manifest_value: dict[str, object], *, mode: str = "http"
) -> dict[str, object]:
    from scripts.kems_dispatch_receipt import _manifest_contract

    _, digest, dispatch_id, _ = _manifest_contract(manifest_value)
    return {
        "dispatch_id": dispatch_id,
        "manifest_sha256": digest,
        "status": "accepted",
        "mode": mode,
        "private_response_body": "must not be copied",
    }


def test_build_receipt_is_redacted_and_production_ready() -> None:
    receipt = build_receipt(
        manifest(),
        response_for(manifest()),
        production=True,
        recorded_at="2026-08-01T00:00:00+00:00",
    )

    assert receipt == {
        "schema": "bos.reachbridge.receipt.v1",
        "run_id": "run-001",
        "dispatch_id": receipt["dispatch_id"],
        "manifest_sha256": receipt["manifest_sha256"],
        "document_count": 1,
        "status": "accepted",
        "transport": "http",
        "recorded_at": "2026-08-01T00:00:00+00:00",
    }
    assert "private_response_body" not in receipt


def test_production_rejects_local_hermes_receipt() -> None:
    with pytest.raises(ReceiptError, match="HTTP transport"):
        build_receipt(
            manifest(), response_for(manifest(), mode="local_hermes"), production=True
        )


def test_receipt_rejects_mismatched_dispatch_identity() -> None:
    response = response_for(manifest())
    response["dispatch_id"] = "wrong"
    with pytest.raises(ReceiptError, match="dispatch_id"):
        build_receipt(manifest(), response, production=True)


def test_receipt_rejects_raw_manifest_key() -> None:
    unsafe = manifest()
    unsafe["documents"][0]["text"] = "private"
    with pytest.raises(ReceiptError, match="forbidden"):
        build_receipt(unsafe, response_for(manifest()), production=True)


def test_write_receipt_is_atomic_and_parseable(tmp_path: Path) -> None:
    output = tmp_path / "receipts" / "dispatch.json"
    receipt = build_receipt(manifest(), response_for(manifest()))
    write_receipt(receipt, output)

    assert (
        json.loads(output.read_text(encoding="utf-8"))["schema"]
        == "bos.reachbridge.receipt.v1"
    )
    assert not list(output.parent.glob(".*.tmp"))
