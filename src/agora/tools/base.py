from __future__ import annotations

"""
---
Type: Module
Status: ACTIVE
Version: 1.0.0
Authority: nucleus/Z-Core/L0-Genome/R0-ACT-SYS-AX01-10_holographic_metadata_axiom.md
Layer: L3
---
"""
# =============================================================================
# 0. 形式化摘要 ≝
# =============================================================================
# Mcp Tools ≡ Tool
# 内涵 ≝ {Mcp, Tools}
# 外延 ≝ {e | e ∈ Organs ∧ implements(e, McpTools)}
# 功能 ⊢ {Mcp_Tools, Init_Mcp, Validate_Tools}
# =============================================================================

# ---
# domain: D-Gateway
# layer: organ
# status: active
# ---
"""Tool implementations and typed registry for the BOS MCP server."""


import dataclasses
import json
import logging
import threading
from collections.abc import Callable
from pathlib import Path
from typing import Any

# TODO-migrate: from nucleus.Z_Spore.interfaces.surface_contract import SurfaceContract, SurfaceContractError, SurfaceIngressKind
SurfaceContract: Any = None
SurfaceContractError: Any = Exception
SurfaceIngressKind: Any = None

_log = logging.getLogger(__name__)

type JSONDict = dict[str, Any]
_ResultBus: Any | None = None
_TaskResult: Any | None = None
_NodeIdentityManager: Any | None = None
_SynapseLink: Any | None = None
_synapse_hello_handler: Any | None = None
_synapse_ping_handler: Any | None = None

_psutil: Any | None = None

try:
    import psutil as _psutil

    _HAS_PSUTIL = True
except ImportError:
    _psutil = None
    _HAS_PSUTIL = False
_HAS_RESULT_BUS = False
_ResultBus = None
_TaskResult = None
_HAS_SYNAPSE = False
_SynapseLink = None
_NodeIdentityManager = None
_synapse_hello_handler = None
_synapse_ping_handler = None

_synapse_link: Any | None = None


def _get_synapse_link() -> Any | None:
    """Return (or lazily create) the module-level SynapseLink instance."""
    global _synapse_link
    if _synapse_link is not None:
        return _synapse_link
    if not _HAS_SYNAPSE or _SynapseLink is None or _NodeIdentityManager is None:
        return None
    try:
        mgr = _NodeIdentityManager()
        _synapse_link = _SynapseLink(mgr.load_or_create())
    except (OSError, ValueError) as exc:
        _log.warning("[MCPServer] Could not create SynapseLink: %s", exc)
        return None
    return _synapse_link


class _ParamError(ValueError):
    """Raised when a required JSON-RPC param is missing."""


def _require(params: JSONDict, key: str) -> Any:
    if key not in params:
        raise _ParamError(f"Missing required parameter: '{key}'")
    return params[key]


def _read_json_object(path: Path) -> JSONDict:
    raw = json.loads(path.read_text())
    if not isinstance(raw, dict):
        raise ValueError(f"{path.name} must contain a JSON object")
    return {str(key): value for key, value in raw.items()}


def _json_object(value: Any) -> JSONDict | None:
    if not isinstance(value, dict):
        return None
    return {str(key): item for key, item in value.items()}


def _surface_payload(surface: SurfaceContract) -> dict[str, Any]:  # type: ignore[reportInvalidTypeForm]
    """Return a serializable surface snapshot for tool responses."""
    return {"surface": surface.to_dict()}


def _mcp_surface_contract(
    params: JSONDict,
    *,
    operation: str,
    default_kind: SurfaceIngressKind,  # type: ignore[reportInvalidTypeForm]
) -> SurfaceContract:  # type: ignore[reportInvalidTypeForm]
    """Construct a typed MCP ingress contract from tool params."""
    control_plane = str(params.get("control_plane", "mcp") or "mcp")
    raw_kind = str(params.get("surface_kind", default_kind.value) or default_kind.value)
    try:
        ingress_kind = SurfaceIngressKind(raw_kind)
    except ValueError as exc:
        raise SurfaceContractError(
            f"{operation} received invalid surface_kind '{raw_kind}'"
        ) from exc
    if control_plane == "cockpit":
        ingress_kind = SurfaceIngressKind.SOVEREIGN_CONTROL
    return SurfaceContract.mcp(
        ingress_kind=ingress_kind,
        session_id=str(params.get("session_id", "")),
        node_id=str(params.get("controller_node_id", params.get("node_id", ""))),
        owner_id=str(params.get("owner_id", "")),
        hive_id=str(params.get("hive_id", "")),
        governance_scope=str(params.get("governance_scope", "")),
        sovereignty_level=str(params.get("sovereignty_level", "")),
        risk_tier=str(params.get("risk_tier", "standard")),
        control_plane=control_plane,
        metadata={
            key: params[key]
            for key in ("controller_session_id", "operation")
            if key in params and params[key] not in (None, "")
        }
        | {"operation": operation},
    )


@dataclasses.dataclass
class ToolContext:
    """Shared context passed to every tool handler function."""

    data_dir: str
    start_time: float
    file_lock: threading.Lock


type ToolHandler = Callable[[JSONDict, ToolContext], JSONDict]
type RegistryEntry = tuple[str, ToolHandler, str]


@dataclasses.dataclass(frozen=True)
class ToolEntry:
    """A registered tool with its handler and category."""

    name: str
    handler: ToolHandler
    category: str


class MCPToolRegistry:
    """Typed registry replacing the string-based dispatch dict."""

    def __init__(self) -> None:
        self._entries: dict[str, ToolEntry] = {}

    def register(self, name: str, handler: ToolHandler, category: str) -> None:
        self._entries[name] = ToolEntry(name=name, handler=handler, category=category)

    def get(self, name: str) -> ToolEntry | None:
        return self._entries.get(name)

    def dispatch(self, method: str, params: JSONDict, ctx: ToolContext) -> JSONDict:
        entry = self._entries.get(method)
        if entry is None:
            raise KeyError(method)
        return entry.handler(params, ctx)

    def methods(self) -> list[str]:
        return list(self._entries.keys())
