from __future__ import annotations

from agora.mcp_proxy.manager import ProxyManager  # type: ignore[import-not-found]
from agora.mcp_registry.embeddings import (
    EmbeddingStore,  # type: ignore[import-not-found]
)
from agora.mcp_registry.lifecycle import (
    LifecycleManager,  # type: ignore[import-not-found]
)
from agora.mcp_registry.orchestrator import (
    Orchestrator,  # type: ignore[import-not-found]
)
from agora.mcp_registry.repository import ToolCatalog  # type: ignore[import-not-found]
from agora.mcp_registry.router import SmartRouter  # type: ignore[import-not-found]

# Global singletons
_proxy_manager: ProxyManager | None = None
_lifecycle_manager: LifecycleManager | None = None

# Cached components
_cached_catalog: ToolCatalog | None = None
_cached_embeddings: EmbeddingStore | None = None
_cached_orchestrator: Orchestrator | None = None
_cached_router: SmartRouter | None = None
_cached_lifecycle_mgr: LifecycleManager | None = None


def get_proxy_manager() -> ProxyManager | None:
    return _proxy_manager


def set_proxy_manager(pm: ProxyManager | None) -> None:
    global _proxy_manager
    _proxy_manager = pm


def get_lifecycle_manager() -> LifecycleManager:
    """Get or create the global LifecycleManager singleton."""
    global _cached_lifecycle_mgr
    if _cached_lifecycle_mgr is not None:
        return _cached_lifecycle_mgr
    catalog = get_cached_catalog()
    _cached_lifecycle_mgr = LifecycleManager(
        catalog=catalog,
        proxy_manager=_proxy_manager,
    )
    return _cached_lifecycle_mgr


def set_lifecycle_manager(lm: LifecycleManager | None) -> None:
    global _lifecycle_manager, _cached_lifecycle_mgr
    _lifecycle_manager = lm
    _cached_lifecycle_mgr = lm


def get_cached_catalog() -> ToolCatalog:
    """Get or create the module-level cached ToolCatalog instance."""
    global _cached_catalog
    if _cached_catalog is None:
        _cached_catalog = ToolCatalog()
    return _cached_catalog


def get_cached_embeddings() -> EmbeddingStore:
    """Get or create the module-level cached EmbeddingStore instance."""
    global _cached_embeddings
    if _cached_embeddings is None:
        catalog = get_cached_catalog()
        _cached_embeddings = EmbeddingStore(catalog._db_path)
    return _cached_embeddings


def get_cached_orchestrator() -> Orchestrator:
    """Get or create the module-level cached Orchestrator instance."""
    global _cached_orchestrator
    if _cached_orchestrator is None:
        catalog = get_cached_catalog()
        lifecycle = get_lifecycle_manager()
        _cached_orchestrator = Orchestrator(catalog=catalog, lifecycle=lifecycle)
    return _cached_orchestrator


def get_cached_router() -> SmartRouter:
    """Get or create the module-level cached SmartRouter instance."""
    global _cached_router
    if _cached_router is None:
        catalog = get_cached_catalog()
        embeddings = get_cached_embeddings()
        lifecycle = get_lifecycle_manager()
        orchestrator = get_cached_orchestrator()
        _cached_router = SmartRouter(
            catalog=catalog,
            embeddings=embeddings,
            lifecycle=lifecycle,
            orchestrator=orchestrator,
        )
    return _cached_router


def clear_caches() -> None:
    """Clear all singletons and components. Primarily used during shutdown."""
    global \
        _cached_catalog, \
        _cached_embeddings, \
        _cached_orchestrator, \
        _cached_router, \
        _cached_lifecycle_mgr, \
        _lifecycle_manager
    if _cached_embeddings is not None:
        _cached_embeddings.close()
    _cached_catalog = None
    _cached_embeddings = None
    _cached_orchestrator = None
    _cached_router = None
    _cached_lifecycle_mgr = None
    _lifecycle_manager = None
