"""Small compatibility helpers for the capability-sync verification CLI.

The executable CLI remains the public compatibility surface.  These helpers
hold only receipt shaping, bounded stdin parsing, principal verification, and
the fixed federation-observer delegation so the CLI module does not become a
god module.  They do not own a registry, dispatcher, or execution authority.
"""

from __future__ import annotations

import json
import subprocess
import sys
from collections.abc import Mapping
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from capability_trace_binding import TraceBindingError

VERIFICATION_RECEIPT_SCHEMA = "capability-admission-verification-receipt/v1"
PRINCIPAL_VERIFICATION_RECEIPT_SCHEMA = "principal-authority-verification-receipt/v1"
_VERIFICATION_FAILURES = {
    "source_unprovable",
    "native_route_unprovable",
    "admission_contradiction",
    "admission_expired",
    "admission_receipt_invalid",
    "authorization_required",
    "value_promotion_forbidden",
}


def verification_receipt(
    status: str,
    failure_code: Optional[str] = None,  # noqa: UP045 -- Python 3.9 contract
    **values: Any,
) -> dict[str, Any]:
    """Build the redacted verification receipt used by the compatibility CLI."""
    receipt: dict[str, Any] = {
        "schema": VERIFICATION_RECEIPT_SCHEMA,
        "status": status,
        "value_indicator_policy": False,
    }
    if status == "verified":
        receipt.update(values)
        receipt["authority"] = "omo-workflow-mesh"
    else:
        receipt["failure_code"] = failure_code if failure_code in _VERIFICATION_FAILURES else "native_route_unprovable"
    return receipt


def read_bounded_stdin_json(stream: Any, *, max_bytes: int) -> Any:
    """Read one bounded JSON envelope without leaking parser details."""
    try:
        input_stream = getattr(stream, "buffer", stream)
        content = input_stream.read(max_bytes + 1)
        if not isinstance(content, (bytes, bytearray)) or len(content) > max_bytes:
            raise TraceBindingError("native_route_unprovable")
        return json.loads(content)
    except TraceBindingError:
        raise
    except (OSError, UnicodeError, TypeError, ValueError) as exc:
        raise TraceBindingError("native_route_unprovable") from exc


def verify_principal_envelope(envelope: Mapping[str, Any]) -> dict[str, Any]:
    """Verify a principal against the OMO authority without storing secrets."""
    principal_id = str(envelope.get("principal_id") or "")
    credential_ref = str(envelope.get("credential_ref") or "")
    expected_digest = str(envelope.get("principal_receipt_digest") or "")
    if not principal_id or not credential_ref or not expected_digest:
        return verification_receipt("rejected", "native_route_unprovable")
    try:
        from omo.sovereignty.principal_authority import DefaultPrincipalAuthority, digest_receipt
    except Exception:  # pragma: no cover - OMO unavailable on this host
        return verification_receipt("rejected", "native_route_unprovable")
    try:
        authority = DefaultPrincipalAuthority()
        receipt = authority.verify(
            principal_id,
            credential_ref,
            now=datetime.now(timezone.utc).isoformat(),  # noqa: UP017 -- Python 3.9 has no datetime.UTC
        )
        actual_digest = digest_receipt(receipt)
        if actual_digest != expected_digest:
            return verification_receipt("rejected", "native_route_unprovable")
        return {
            "schema": PRINCIPAL_VERIFICATION_RECEIPT_SCHEMA,
            "status": "verified",
            "value_indicator_policy": False,
            "authority": "omo-sovereignty",
            "principal_id": principal_id,
            "authority_ref": receipt.authority_ref,
            "principal_receipt_digest": actual_digest,
            "membership_version": receipt.membership_version,
        }
    except Exception:  # pragma: no cover - any authority failure is fail-closed
        return verification_receipt("rejected", "native_route_unprovable")


def delegate_to_federation_auditor(workspace_root: Path, *, auditor: Path, strict: bool) -> int:
    """Run the fixed internal read-only federation observer."""
    command = [sys.executable, str(auditor), "--workspace-root", str(workspace_root), "--json"]
    if strict:
        command.append("--strict")
    return subprocess.run(command, check=False).returncode
