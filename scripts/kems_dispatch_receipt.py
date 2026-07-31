"""Record a redacted, auditable KEMS enterprise dispatch receipt."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

FORBIDDEN_KEYS = {"body", "content", "ocr_text", "raw_text", "text"}
ACCEPTED_STATUSES = {"accepted", "queued", "succeeded", "completed"}


class ReceiptError(ValueError):
    """The dispatch response cannot be admitted as a production receipt."""


def _load_json(path: Path, label: str) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ReceiptError(f"invalid {label}: {type(exc).__name__}") from exc
    if not isinstance(payload, dict):
        raise ReceiptError(f"invalid {label}: object required")
    return payload


def _contains_forbidden_key(value: object) -> bool:
    if isinstance(value, dict):
        if any(str(key).lower() in FORBIDDEN_KEYS for key in value):
            return True
        return any(_contains_forbidden_key(child) for child in value.values())
    if isinstance(value, list):
        return any(_contains_forbidden_key(child) for child in value)
    return False


def _canonical_manifest(manifest: dict[str, Any]) -> bytes:
    return json.dumps(
        manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def _manifest_contract(manifest: dict[str, Any]) -> tuple[str, str, str, int]:
    if manifest.get("schema") != "bos.reachbridge.manifest.v1":
        raise ReceiptError("unsupported manifest schema")
    run_id = manifest.get("run_id")
    documents = manifest.get("documents")
    if not isinstance(run_id, str) or not run_id:
        raise ReceiptError("manifest run_id is missing")
    if not isinstance(documents, list) or not documents:
        raise ReceiptError("manifest documents are missing")
    if _contains_forbidden_key(manifest):
        raise ReceiptError("manifest contains forbidden raw content key")
    for document in documents:
        if not isinstance(document, dict):
            raise ReceiptError("manifest document must be an object")
        source_ref = document.get("source_ref")
        if not isinstance(source_ref, str) or not source_ref.startswith(
            "vault://redacted/"
        ):
            raise ReceiptError("manifest source_ref must be redacted")
    canonical = dict(manifest)
    canonical.pop("manifest_sha256", None)
    canonical.pop("dispatch_id", None)
    digest = hashlib.sha256(_canonical_manifest(canonical)).hexdigest()
    dispatch_id = f"reach-{run_id}-{digest[:16]}"
    return run_id, digest, dispatch_id, len(documents)


def build_receipt(
    manifest: dict[str, Any],
    response: dict[str, Any],
    *,
    production: bool = False,
    recorded_at: str | None = None,
) -> dict[str, Any]:
    run_id, digest, dispatch_id, document_count = _manifest_contract(manifest)
    if response.get("dispatch_id") != dispatch_id:
        raise ReceiptError("response did not confirm dispatch_id")
    if response.get("manifest_sha256") != digest:
        raise ReceiptError("response did not confirm manifest_sha256")
    mode = response.get("mode")
    if mode not in {"http", "local_hermes"}:
        raise ReceiptError("response transport mode is invalid")
    if production and mode != "http":
        raise ReceiptError("production receipt requires HTTP transport")
    status = response.get("status")
    if status not in ACCEPTED_STATUSES:
        raise ReceiptError("response status is not accepted")
    return {
        "schema": "bos.reachbridge.receipt.v1",
        "run_id": run_id,
        "dispatch_id": dispatch_id,
        "manifest_sha256": digest,
        "document_count": document_count,
        "status": status,
        "transport": mode,
        # timezone.utc is required here because this script supports system Python 3.9.
        "recorded_at": recorded_at or datetime.now(timezone.utc).isoformat(),  # noqa: UP017
    }


def write_receipt(receipt: dict[str, Any], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_name(f".{output.name}.tmp")
    try:
        temporary.write_text(
            json.dumps(receipt, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
        )
        temporary.replace(output)
    finally:
        if temporary.exists():
            temporary.unlink()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--response", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--production", action="store_true")
    args = parser.parse_args()
    try:
        manifest = _load_json(args.manifest.expanduser().resolve(), "manifest")
        response = _load_json(args.response.expanduser().resolve(), "dispatch response")
        receipt = build_receipt(manifest, response, production=args.production)
        write_receipt(receipt, args.output.expanduser().resolve())
    except (OSError, ReceiptError) as exc:
        print(
            json.dumps({"status": "failed", "error": str(exc)}, ensure_ascii=False),
            file=sys.stderr,
        )
        return 1
    print(json.dumps({"status": "succeeded", **receipt}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
