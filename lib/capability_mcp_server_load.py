"""capability_mcp_server_load.py — the shared exact find/load entry (T1-12).

WP-T1-12-P0-EXACT-MCP-LOAD: every cockpit/agora/omo consumer that needs to
locate, inspect, or load a declared capability goes through this module
instead of re-implementing subprocess/importlib tricks against
``bin/capability-sync.py``.

Contract (waiver 2026-08-30 helper scope amendment):
- read-only: find / inspect / load only — no invocation, no admission
  decision, no receipt minting (those stay behind the PEP / verifier);
- exact ids only (``skill:…``, ``workflow:…``, ``mcp-server:…``,
  ``mcp-tool:<server>:<tool>``, ``bos-service:bos://…``) — no fuzzy query;
- single source: delegates to the canonical ``bin/capability-sync.py``
  resolver loaded once per process (no second registry/dispatcher);
- fail-closed: a missing registry or unresolved id raises
  :class:`CapabilityLoadError` with a redacted, stable reason.

Constraints honored: keeps capability-sync under its 1500-line gate (this
helper lives beside it, not inside it), no ``tools/call``, no caller-supplied
command/argv, no fallback paths.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

__all__ = [
    "CAPABILITY_SYNC_PATH",
    "CapabilityLoadError",
    "find_capability",
    "inspect_capability",
    "load_capability",
    "load_sync_module",
]

CAPABILITY_SYNC_PATH = Path(__file__).resolve().parents[1] / "bin" / "capability-sync.py"

_SYNC_MODULE: Any = None

VALID_PREFIXES = ("skill:", "workflow:", "mcp-server:", "mcp-tool:", "bos-service:")


class CapabilityLoadError(Exception):
    """Stable, redacted failure for exact find/inspect/load requests."""


def load_sync_module(root: Path | None = None) -> Any:
    """Load the canonical capability-sync resolver module once per process."""
    global _SYNC_MODULE
    if _SYNC_MODULE is not None:
        return _SYNC_MODULE
    path = (root or Path(__file__).resolve().parents[1]) / "bin" / "capability-sync.py"
    if not path.is_file():
        raise CapabilityLoadError("resolver_unavailable")
    spec = importlib.util.spec_from_file_location("_capability_sync_shared", path)
    if spec is None or spec.loader is None:
        raise CapabilityLoadError("resolver_unavailable")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    try:
        spec.loader.exec_module(module)
    except Exception as exc:  # noqa: BLE001 - fail closed on a broken resolver
        sys.modules.pop(spec.name, None)
        raise CapabilityLoadError("resolver_broken") from exc
    _SYNC_MODULE = module
    return module


def _require_exact_id(capability_id: str) -> None:
    if not isinstance(capability_id, str) or not capability_id.startswith(VALID_PREFIXES):
        raise CapabilityLoadError("capability_id_invalid")
    if capability_id.endswith(":"):
        raise CapabilityLoadError("capability_id_invalid")  # empty tail after the prefix


def _parse_receipt(raw: str) -> dict[str, Any]:
    try:
        receipt = json.loads(raw)
    except ValueError as exc:
        raise CapabilityLoadError("resolver_output_invalid") from exc
    if not isinstance(receipt, dict):
        raise CapabilityLoadError("resolver_output_invalid")
    return receipt


def find_capability(capability_id: str, *, root: Path | None = None) -> dict[str, Any]:
    """Exact-resolution only: return the resolution receipt for ``capability_id``.

    Delegates to ``capability-sync.main(["find", "--id", …])`` — the resolver
    prints exactly one capability-resolution-receipt/v1 JSON document on
    stdout for a resolved id and exits non-zero on a miss.
    """
    _require_exact_id(capability_id)
    module = load_sync_module(root)
    if not hasattr(module, "main"):
        raise CapabilityLoadError("resolver_unavailable")

    import io
    from contextlib import redirect_stdout

    buf = io.StringIO()
    old_argv, old_stdout = sys.argv, sys.stdout
    sys.argv = ["capability-sync", "find", "--id", capability_id]
    exit_code = 0
    try:
        with redirect_stdout(buf):
            module.main(["find", "--id", capability_id])
    except SystemExit as exc:
        exit_code = int(exc.code or 0)
    finally:
        sys.argv, sys.stdout = old_argv, old_stdout
    receipt = _parse_receipt(buf.getvalue())
    if receipt.get("match_count", 0) < 1 or not receipt.get("status") == "resolved":
        raise CapabilityLoadError("capability_not_found")
    if exit_code not in (0, None):
        raise CapabilityLoadError("capability_not_found")
    return receipt


def inspect_capability(capability_id: str, *, root: Path | None = None) -> dict[str, Any]:
    """Static inspection of a declared capability (no execution, no admission)."""
    _require_exact_id(capability_id)
    module = load_sync_module(root)
    if not hasattr(module, "inspect_native_capability"):
        raise CapabilityLoadError("resolver_unavailable")
    registry_path = (root or Path(__file__).resolve().parents[1]) / "docs" / "generated" / "capability-registry.yaml"
    if not registry_path.is_file():
        raise CapabilityLoadError("registry_unavailable")
    root_dir = root or Path(__file__).resolve().parents[1]
    registry_path = root_dir / "docs" / "generated" / "capability-registry.yaml"
    if not registry_path.is_file():
        raise CapabilityLoadError("registry_unavailable")
    binding = {
        "correlation_id": "helper-inspect",
        "workflow_run_id": "helper-inspect",
        "packet_id": "packet:helper-inspect",
        "packet_hash": "sha256:" + "0" * 64,
        "assignment_id": "assignment:helper-inspect",
        "dispatch_id": "dispatch:helper-inspect",
        "actor_id": "actor:helper-inspect",
        "delivery_attempt_id": "attempt:helper-inspect",
    }
    receipt = module.inspect_native_capability(
        root=root_dir,
        capability_id=capability_id,
        registry={},
        registry_content=b"",
        binding=binding,
    )
    if not isinstance(receipt, dict):
        raise CapabilityLoadError("resolver_output_invalid")
    return receipt


def load_capability(capability_id: str, *, root: Path | None = None) -> dict[str, Any]:
    """Exact load: resolution + inspection receipts, still without execution.

    ``load`` is the last read-only step of the identity chain — callers that
    intend to *invoke* must additionally carry a verified admission binding
    (WP4 authority + WorkPacket admission), enforced elsewhere.
    """
    resolution = find_capability(capability_id, root=root)
    inspection = inspect_capability(capability_id, root=root)
    return {"resolution": resolution, "inspection": inspection, "capability_id": capability_id}
