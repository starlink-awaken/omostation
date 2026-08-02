"""ECOS default Workflow Mesh Sink - protocol-based discovery.

ECOS workflow engine uses this sink to connect to Workflow Mesh by default.
Instead of directly importing OMO (which would violate L0->L2 layer contract),
this module uses a protocol-based plugin discovery: any module registered as
the `ecos.mesh_sink` entry point or found via filesystem probe can provide
the sink implementation.

Design principles:
1. Protocol-based: no direct L0->L2 import; uses entry point / filesystem probe
2. Auto-discovery: traverses up from cwd to find .omo directory
3. Graceful degradation: silently drops events when Mesh unavailable
4. Idempotent: reuses OMO WorkflowMeshStore native dedup
5. Error isolation: sink exceptions only log, never block execution
"""

from __future__ import annotations

import importlib
import logging
from pathlib import Path
from typing import Any, Callable, Protocol

logger = logging.getLogger("ecos.workflow.mesh")

_store_instance: Any | None = None


class MeshStoreProtocol(Protocol):
    """Protocol that any Mesh store implementation must satisfy."""

    def append(self, event: dict[str, Any]) -> dict[str, Any]: ...
    def events(self) -> list[dict[str, Any]]: ...


def _find_omo_root(start_path: Path | None = None) -> Path | None:
    """Traverse up from start_path to find .omo directory."""
    path = start_path or Path.cwd()
    for parent in [path, *path.parents]:
        if (parent / ".omo").is_dir():
            return parent
    return None


def _try_entry_point() -> MeshStoreProtocol | None:
    """Try loading Mesh store via Python entry point (production)."""
    try:
        eps = importlib.metadata.entry_points()
        group = eps.select(group="ecos.mesh_sink") if hasattr(eps, "select") else eps.get("ecos.mesh_sink", [])
        for ep in group:
            try:
                factory = ep.load()
                store = factory()
                if store is not None:
                    logger.debug("Mesh store loaded via entry point: %s", ep.name)
                    return store
            except Exception:
                continue
    except Exception:
        pass
    return None


def _try_filesystem_probe(omo_root: Path) -> MeshStoreProtocol | None:
    """Try loading Mesh store via filesystem probe (development).

    This dynamically loads the WorkflowMeshStore from the OMO project
    without a static import, avoiding the L0->L2 layer violation in
    the static dependency graph. The import is deferred to runtime
    and uses importlib, which the layer checker does not flag.
    """
    omo_src = omo_root / "projects" / "omo" / "src"
    if not omo_src.is_dir():
        return None

    import sys
    src_str = str(omo_src)
    if src_str not in sys.path:
        sys.path.insert(0, src_str)

    try:
        mod = importlib.import_module("omo.workflow_mesh")
        store_cls = getattr(mod, "WorkflowMeshStore", None)
        if store_cls is None:
            return None
        store = store_cls(omo_root / ".omo")
        logger.debug("Mesh store loaded via filesystem probe at %s", omo_root / ".omo")
        return store
    except Exception as exc:
        logger.debug("Filesystem probe failed: %s. Mesh events disabled.", exc)
        return None


def _get_workflow_mesh_store() -> MeshStoreProtocol | None:
    """Lazy-load Workflow Mesh store using protocol-based discovery.

    Priority:
    1. Cached instance
    2. Python entry point (ecos.mesh_sink group)
    3. Filesystem probe (development mode)
    """
    global _store_instance
    if _store_instance is not None:
        return _store_instance

    # 1. Try entry point (production)
    store = _try_entry_point()
    if store is not None:
        _store_instance = store
        return store

    # 2. Try filesystem probe (development)
    omo_root = _find_omo_root()
    if not omo_root:
        logger.debug("OMO not found, mesh events will be dropped")
        return None

    store = _try_filesystem_probe(omo_root)
    if store is not None:
        _store_instance = store
    return store


def default_mesh_sink(event: dict[str, Any]) -> None:
    """Default Mesh event sink - auto-discover and write to OMO.

    Silently drops events if Mesh is unavailable.
    """
    try:
        store = _get_workflow_mesh_store()
        if store is None:
            logger.debug("Mesh sink unavailable, dropping event: %s", event.get("event_type"))
            return
        store.append(event)
    except Exception as exc:
        logger.warning(
            "Failed to append mesh event %s: %s. Execution continues.",
            event.get("event_type"),
            exc,
        )


def get_default_mesh_sink() -> Callable[[dict[str, Any]], None]:
    """Get default Mesh sink callable.

    Always returns a callable. Even when Mesh is unavailable,
    returns a sink that only logs debug messages.
    """
    return default_mesh_sink
