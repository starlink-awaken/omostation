"""kos/eidos.py — Eidos compatibility shim (MCP-first, direct-import fallback).

Replaces `from eidos import ...` with `from kos.eidos import ...`.
MCP > REST > CLI > direct import — this shim starts the migration.
"""

from __future__ import annotations

import json
import logging
import subprocess
import sys
import warnings
from typing import Any, cast

logger = logging.getLogger(__name__)

# Type classes — re-exported from eidos for structured validation.
# TODO: replace with MCP calls once eidos MCP exposes type constructors.
try:
    from eidos.types import Fact, KnowledgeCard, OntologyNode
except ImportError:
    KnowledgeCard = None
    Fact = None
    OntologyNode = None
    msg = "eidos not installed; schema types unavailable"
    warnings.warn(msg, ImportWarning, stacklevel=2)


# ── MCP client (stdio subprocess) ──────────────────────────────────


def _mcp_call(tool: str, **kwargs: Any) -> dict[str, Any]:
    """Call an eidos MCP tool via stdio subprocess."""
    req = json.dumps(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": tool, "arguments": kwargs},
        }
    )
    try:
        proc = subprocess.run(
            [sys.executable, "-m", "eidos.mcp_server"],
            input=req,
            capture_output=True,
            text=True,
            timeout=15,
        )
        raw = json.loads(proc.stdout.strip())
        return cast("dict[str, Any]", raw.get("result", {}))
    except Exception:
        logger.debug("eidos MCP call failed for %s", tool)
        return {}


def _mcp_result_text(r: dict[str, Any]) -> str:
    """Extract text content from a tools/call response."""
    content = r.get("content") or [{}]
    if isinstance(content, list) and content:
        return cast("str", content[0].get("text", "{}"))
    return "{}"


# ── Public API ─────────────────────────────────────────────────────


def validate_object(data: dict[str, Any], schema_type: str = "KnowledgeCard") -> bool:
    """Validate a data object against an Eidos schema via MCP.

    Returns True if valid, False on any error or MCP failure.
    """
    ok, _ = validate_object_full(data, schema_type)
    return ok


def validate_object_full(
    data: dict[str, Any],
    schema_type: str,
) -> tuple[bool, list[str]]:
    """Validate and return (is_valid, errors) via eidos MCP.

    Falls back to (False, ["eidos MCP unavailable"]) on failure.
    """
    try:
        import importlib

        direct_validator = importlib.import_module("eidos.validator")

        direct_validate = getattr(direct_validator, "validate_object", None)
        if callable(direct_validate):
            return bool(direct_validate(data)), []
    except Exception:
        pass

    try:
        resp = _mcp_call(
            "eidos_validate",
            data=json.dumps(data),
            schema_type=schema_type,
        )
        text = _mcp_result_text(resp)
        result = json.loads(text) if isinstance(text, str) else text
        return bool(result.get("is_valid", False)), result.get("errors", [])
    except Exception:
        return False, ["eidos MCP unavailable"]
