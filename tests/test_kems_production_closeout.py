from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from scripts.kems_production_closeout import CloseoutError, validate_closeout


def _manifest(run_id: str = "run-001") -> dict[str, object]:
    return {
        "schema": "bos.reachbridge.manifest.v1",
        "run_id": run_id,
        "created_at": "2026-08-01T00:00:00+00:00",
        "documents": [
            {
                "source_ref": "vault://redacted/source-1",
                "filename": "source-1.md",
                "sha256": "a" * 64,
                "bytes": 12,
            }
        ],
    }


def _digest(manifest: dict[str, object]) -> str:
    canonical = dict(manifest)
    canonical.pop("manifest_sha256", None)
    canonical.pop("dispatch_id", None)
    return hashlib.sha256(
        json.dumps(
            canonical, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode()
    ).hexdigest()


def _evidence(run_id: str = "run-001") -> dict[str, object]:
    return {
        "schema": "kems.production-preflight-evidence.v1",
        "status": "ready",
        "production": True,
        "run_id": run_id,
        "source_count": 1,
        "sources": [{"name": "source-1.md", "bytes": 12, "sha256": "a" * 64}],
        "evaluation": {"available": True},
        "model_acceptance": {"available": True},
        "omo": {"available": True},
        "checks": [{"id": "all", "ok": True, "detail": "ok"}],
    }


def _receipt(manifest: dict[str, object]) -> dict[str, object]:
    digest = _digest(manifest)
    return {
        "schema": "bos.reachbridge.receipt.v1",
        "run_id": manifest["run_id"],
        "dispatch_id": f"reach-{manifest['run_id']}-{digest[:16]}",
        "manifest_sha256": digest,
        "document_count": 1,
        "status": "accepted",
        "transport": "http",
        "recorded_at": "2026-08-01T00:00:00+00:00",
    }


def _write_bundle(
    tmp_path: Path, *, run_id: str = "run-001"
) -> tuple[Path, Path, Path]:
    manifest = _manifest(run_id)
    paths = (
        tmp_path / "preflight.json",
        tmp_path / "manifest.json",
        tmp_path / "receipt.json",
    )
    paths[0].write_text(json.dumps(_evidence(run_id)), encoding="utf-8")
    paths[1].write_text(json.dumps(manifest), encoding="utf-8")
    paths[2].write_text(json.dumps(_receipt(manifest)), encoding="utf-8")
    return paths


def test_validate_closeout_binds_all_redacted_artifacts(tmp_path: Path) -> None:
    paths = _write_bundle(tmp_path)
    result = validate_closeout(
        preflight_path=paths[0], manifest_path=paths[1], receipt_path=paths[2]
    )
    assert result["status"] == "ready"
    assert result["transport"] == "http"
    assert result["document_count"] == 1


@pytest.mark.parametrize("field", ["run_id", "manifest_sha256", "transport"])
def test_validate_closeout_rejects_mismatched_receipt(
    tmp_path: Path, field: str
) -> None:
    paths = _write_bundle(tmp_path)
    receipt = json.loads(paths[2].read_text(encoding="utf-8"))
    receipt[field] = "wrong"
    paths[2].write_text(json.dumps(receipt), encoding="utf-8")
    with pytest.raises(CloseoutError):
        validate_closeout(
            preflight_path=paths[0], manifest_path=paths[1], receipt_path=paths[2]
        )


def test_validate_closeout_rejects_inventory_drift(tmp_path: Path) -> None:
    paths = _write_bundle(tmp_path)
    evidence = json.loads(paths[0].read_text(encoding="utf-8"))
    evidence["sources"][0]["bytes"] = 99
    paths[0].write_text(json.dumps(evidence), encoding="utf-8")
    with pytest.raises(CloseoutError, match="inventory"):
        validate_closeout(
            preflight_path=paths[0], manifest_path=paths[1], receipt_path=paths[2]
        )


def test_validate_closeout_rejects_failed_preflight(tmp_path: Path) -> None:
    paths = _write_bundle(tmp_path)
    evidence = json.loads(paths[0].read_text(encoding="utf-8"))
    evidence["checks"][0]["ok"] = False
    paths[0].write_text(json.dumps(evidence), encoding="utf-8")
    with pytest.raises(CloseoutError, match="preflight"):
        validate_closeout(
            preflight_path=paths[0], manifest_path=paths[1], receipt_path=paths[2]
        )