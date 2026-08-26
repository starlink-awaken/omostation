"""Fixed, fail-closed adapter for root capability-admission verification."""

from __future__ import annotations

import json
import subprocess
import sys
from collections.abc import Mapping
from pathlib import Path

_WORKSPACE_ROOT = Path(__file__).resolve().parents[5]
_VERIFY_TIMEOUT_SECONDS = 5.0
_MAX_ENVELOPE_BYTES = 1_048_576
_VERIFICATION_RECEIPT_SCHEMA = "capability-admission-verification-receipt/v1"


def verify_binding_envelope(envelope: object) -> bool:
    """Return true only when the fixed root verifier emits a verified receipt."""
    if not isinstance(envelope, Mapping) or not envelope:
        return False
    try:
        payload = json.dumps(envelope, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    except (TypeError, ValueError):
        return False
    if len(payload) > _MAX_ENVELOPE_BYTES:
        return False

    try:
        result = subprocess.run(
            [sys.executable, str(_WORKSPACE_ROOT / "bin" / "capability-sync.py"), "verify-material"],
            cwd=str(_WORKSPACE_ROOT),
            input=payload,
            capture_output=True,
            check=False,
            timeout=_VERIFY_TIMEOUT_SECONDS,
            shell=False,
            env={
                "PYTHONDONTWRITEBYTECODE": "1",
                "PYTHONIOENCODING": "utf-8",
                "PYTHONUTF8": "1",
                "PYTHONNOUSERSITE": "1",
            },
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    if result.returncode != 0:
        return False

    try:
        receipt = json.loads(result.stdout)
    except (json.JSONDecodeError, TypeError, UnicodeDecodeError):
        return False
    return bool(
        isinstance(receipt, Mapping)
        and receipt.get("schema") == _VERIFICATION_RECEIPT_SCHEMA
        and receipt.get("status") == "verified"
        and receipt.get("value_indicator_policy") is False
    )
