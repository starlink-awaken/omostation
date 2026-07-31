"""KEMS manifest dispatch contract for ReachBridge."""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone

from . import ReachGateway, ReachPayload, ScenarioLevel, dispatch_http


class ManifestError(ValueError):
    """The input is not an approved redacted KEMS manifest."""


@dataclass(frozen=True)
class KemsDispatchResult:
    dispatch_id: str
    status: str
    mode: str
    manifest_sha256: str

    def as_dict(self) -> dict[str, str]:
        return {
            "dispatch_id": self.dispatch_id,
            "status": self.status,
            "mode": self.mode,
            "manifest_sha256": self.manifest_sha256,
        }


def _canonical_manifest(manifest: dict[str, object]) -> bytes:
    return json.dumps(
        manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def validate_manifest(manifest: dict[str, object]) -> None:
    if manifest.get("schema") != "bos.reachbridge.manifest.v1":
        raise ManifestError("unsupported manifest schema")
    run_id = manifest.get("run_id")
    documents = manifest.get("documents")
    if not isinstance(run_id, str) or not run_id:
        raise ManifestError("missing run_id")
    if not isinstance(documents, list) or not documents:
        raise ManifestError("documents must be non-empty")
    for document in documents:
        if not isinstance(document, dict):
            raise ManifestError("document entry must be an object")
        source_ref = document.get("source_ref")
        if not isinstance(source_ref, str) or not source_ref.startswith(
            "vault://redacted/"
        ):
            raise ManifestError("document source_ref must be redacted")
        if "content" in document or "body" in document or "text" in document:
            raise ManifestError("raw document content is forbidden")


def prepare_manifest(manifest: dict[str, object]) -> dict[str, object]:
    validate_manifest(manifest)
    prepared = dict(manifest)
    digest = hashlib.sha256(_canonical_manifest(manifest)).hexdigest()
    prepared["manifest_sha256"] = digest
    prepared["dispatch_id"] = f"reach-{manifest['run_id']}-{digest[:16]}"
    prepared.setdefault("created_at", datetime.now(timezone.utc).isoformat())  # noqa: UP017
    return prepared


def dispatch_manifest(
    manifest: dict[str, object], *, timeout: int = 15
) -> KemsDispatchResult:
    """Dispatch a redacted manifest through explicitly configured transport.

    ``BOS_REACHBRIDGE_ENDPOINT`` selects HTTP transport. Otherwise
    ``BOS_REACHBRIDGE_MODE=local_hermes`` enables the local relay explicitly.
    No implicit success path exists.
    """
    prepared = prepare_manifest(manifest)
    digest = str(prepared["manifest_sha256"])
    dispatch_id = str(prepared["dispatch_id"])
    endpoint = os.environ.get("BOS_REACHBRIDGE_ENDPOINT", "").strip()
    if endpoint:
        response = dispatch_http(
            endpoint,
            os.environ.get("BOS_REACHBRIDGE_TOKEN", ""),
            prepared,
            timeout,
        )
        return KemsDispatchResult(
            dispatch_id, str(response.get("status", "accepted")), "http", digest
        )

    if os.environ.get("BOS_REACHBRIDGE_MODE") != "local_hermes":
        raise RuntimeError("ReachBridge transport is not configured")

    body = f"{len(prepared['documents'])} 个私有源清单已生成，manifest={digest[:16]}"
    payload = ReachPayload(
        app_id="app_bos_kems",
        user_id=os.environ.get("BOS_REACHBRIDGE_USER", "usr_primary_owner"),
        scenario=ScenarioLevel.ACTIONABLE,
        title="BOS KEMS 待审清单",
        body=body,
        action_url=os.environ.get("BOS_REACHBRIDGE_ACTION_URL"),
        target_channels=["hermes_relay"],
        dispatch_id=dispatch_id,
    )
    if not ReachGateway().dispatch_payload(payload):
        raise RuntimeError("local Hermes relay did not confirm delivery")
    return KemsDispatchResult(dispatch_id, "queued", "local_hermes", digest)
