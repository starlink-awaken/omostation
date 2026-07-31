#!/usr/bin/env python3
"""Validate the complete, redacted KEMS production evidence bundle."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any

FORBIDDEN_KEYS = {"body", "content", "ocr_text", "raw_text", "text"}
SHA256 = re.compile(r"^[0-9a-f]{64}$")
RECEIPT_SCHEMA = "bos.reachbridge.receipt.v1"
PREFLIGHT_SCHEMA = "kems.production-preflight-evidence.v1"
MANIFEST_SCHEMA = "bos.reachbridge.manifest.v1"
ACCEPTED_STATUSES = {"accepted", "succeeded", "completed"}


class CloseoutError(ValueError):
    """The supplied evidence bundle cannot prove production completion."""


def _load_json(path: Path, label: str) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise CloseoutError(f"invalid {label}: {type(exc).__name__}") from exc
    if not isinstance(payload, dict):
        raise CloseoutError(f"invalid {label}: object required")
    return payload


def _contains_forbidden_key(value: object) -> bool:
    if isinstance(value, dict):
        if any(str(key).lower() in FORBIDDEN_KEYS for key in value):
            return True
        return any(_contains_forbidden_key(child) for child in value.values())
    if isinstance(value, list):
        return any(_contains_forbidden_key(child) for child in value)
    return False


def _manifest_digest(manifest: dict[str, Any]) -> tuple[str, str, int]:
    if manifest.get("schema") != MANIFEST_SCHEMA:
        raise CloseoutError("unsupported ReachBridge manifest schema")
    run_id = manifest.get("run_id")
    documents = manifest.get("documents")
    if not isinstance(run_id, str) or not run_id.strip():
        raise CloseoutError("manifest run_id is missing")
    if not isinstance(documents, list) or not documents:
        raise CloseoutError("manifest documents are missing")
    if _contains_forbidden_key(manifest):
        raise CloseoutError("manifest contains forbidden raw content key")
    for document in documents:
        if not isinstance(document, dict):
            raise CloseoutError("manifest document must be an object")
        source_ref = document.get("source_ref")
        digest = document.get("sha256")
        filename = document.get("filename")
        size = document.get("bytes")
        if not isinstance(source_ref, str) or not source_ref.startswith(
            "vault://redacted/"
        ):
            raise CloseoutError("manifest source_ref must be redacted")
        if not isinstance(digest, str) or not SHA256.fullmatch(digest):
            raise CloseoutError("manifest document sha256 is invalid")
        if not isinstance(filename, str) or not filename.strip():
            raise CloseoutError("manifest document filename is invalid")
        if not isinstance(size, int) or size < 0:
            raise CloseoutError("manifest document bytes is invalid")
    canonical = dict(manifest)
    canonical.pop("manifest_sha256", None)
    canonical.pop("dispatch_id", None)
    digest = hashlib.sha256(
        json.dumps(
            canonical, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
    ).hexdigest()
    return run_id.strip(), digest, len(documents)


def _preflight_inventory(
    preflight: dict[str, Any],
) -> tuple[str, list[tuple[str, int, str]]]:
    if preflight.get("schema") != PREFLIGHT_SCHEMA:
        raise CloseoutError("unsupported preflight evidence schema")
    if preflight.get("status") != "ready" or preflight.get("production") is not True:
        raise CloseoutError("production preflight is not ready")
    run_id = preflight.get("run_id")
    if not isinstance(run_id, str) or not run_id.strip():
        raise CloseoutError("preflight run_id is missing")
    checks = preflight.get("checks")
    if (
        not isinstance(checks, list)
        or not checks
        or any(
            not isinstance(check, dict) or check.get("ok") is not True
            for check in checks
        )
    ):
        raise CloseoutError("production preflight contains failed checks")
    for field in ("evaluation", "model_acceptance", "omo"):
        if (
            not isinstance(preflight.get(field), dict)
            or preflight[field].get("available") is not True
        ):
            raise CloseoutError(f"preflight {field} evidence is unavailable")
    inventory = preflight.get("sources")
    if not isinstance(inventory, list) or not inventory:
        raise CloseoutError("preflight source inventory is missing")
    normalized: list[tuple[str, int, str]] = []
    for item in inventory:
        if not isinstance(item, dict):
            raise CloseoutError("preflight source inventory item is invalid")
        name, size, digest = item.get("name"), item.get("bytes"), item.get("sha256")
        if (
            not isinstance(name, str)
            or not name
            or not isinstance(size, int)
            or size < 0
        ):
            raise CloseoutError("preflight source inventory metadata is invalid")
        if not isinstance(digest, str) or not SHA256.fullmatch(digest):
            raise CloseoutError("preflight source inventory sha256 is invalid")
        normalized.append((name, size, digest))
    return run_id.strip(), sorted(normalized)


def validate_closeout(
    *, preflight_path: Path, manifest_path: Path, receipt_path: Path
) -> dict[str, Any]:
    preflight = _load_json(preflight_path, "preflight evidence")
    manifest = _load_json(manifest_path, "ReachBridge manifest")
    receipt = _load_json(receipt_path, "dispatch receipt")
    run_id, inventory = _preflight_inventory(preflight)
    manifest_run_id, manifest_sha256, document_count = _manifest_digest(manifest)
    if manifest_run_id != run_id:
        raise CloseoutError("manifest run_id does not match preflight run_id")
    if receipt.get("schema") != RECEIPT_SCHEMA:
        raise CloseoutError("unsupported dispatch receipt schema")
    if receipt.get("run_id") != run_id:
        raise CloseoutError("receipt run_id does not match preflight run_id")
    if receipt.get("dispatch_id") != f"reach-{run_id}-{manifest_sha256[:16]}":
        raise CloseoutError("receipt dispatch_id does not match manifest")
    if receipt.get("manifest_sha256") != manifest_sha256:
        raise CloseoutError("receipt manifest_sha256 does not match manifest")
    if receipt.get("document_count") != document_count:
        raise CloseoutError("receipt document count does not match manifest")
    if receipt.get("transport") != "http":
        raise CloseoutError("production closeout requires HTTP transport")
    if receipt.get("status") not in ACCEPTED_STATUSES:
        raise CloseoutError("dispatch receipt status is not accepted")

    manifest_inventory = sorted(
        (document["filename"], document["bytes"], document["sha256"])
        for document in manifest["documents"]
    )
    if manifest_inventory != inventory:
        raise CloseoutError(
            "manifest inventory does not match preflight source inventory"
        )
    if document_count != len(inventory):
        raise CloseoutError(
            "manifest document count does not match preflight inventory"
        )
    return {
        "schema": "kems.production-closeout.v1",
        "status": "ready",
        "run_id": run_id,
        "manifest_sha256": manifest_sha256,
        "document_count": document_count,
        "dispatch_id": receipt["dispatch_id"],
        "transport": receipt["transport"],
        "receipt_status": receipt["status"],
        "preflight_checks": len(preflight["checks"]),
    }


def _write_json_atomically(payload: dict[str, Any], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_name(f".{output.name}.tmp")
    try:
        temporary.write_text(
            json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
        )
        temporary.chmod(0o600)
        temporary.replace(output)
        output.chmod(0o600)
    finally:
        if temporary.exists():
            temporary.unlink()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--preflight-evidence", required=True, type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--receipt", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    try:
        result = validate_closeout(
            preflight_path=args.preflight_evidence.expanduser().resolve(),
            manifest_path=args.manifest.expanduser().resolve(),
            receipt_path=args.receipt.expanduser().resolve(),
        )
        _write_json_atomically(result, args.output.expanduser().resolve())
    except (CloseoutError, OSError) as exc:
        result = {
            "schema": "kems.production-closeout.v1",
            "status": "blocked",
            "error": str(exc),
        }
        try:
            _write_json_atomically(result, args.output.expanduser().resolve())
        except OSError:
            pass
        print(json.dumps(result, ensure_ascii=False), flush=True)
        return 1
    result["output"] = str(args.output.expanduser().resolve())
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())