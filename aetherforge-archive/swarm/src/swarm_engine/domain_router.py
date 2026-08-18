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
# Domain Router ≡ Router
# 内涵 ≝ {Domain, Router}
# 外延 ≝ {e | e ∈ Organs ∧ implements(e, DomainRouter)}
# 功能 ⊢ {Domain_Router, Init_Domain, Validate_Router}
# =============================================================================

"""
---
Type: Module
Status: ACTIVE
Version: 1.0.0
Authority: organs/D-Execution/AGENTS.md
Layer: L3
---
Domain routing abstractions: DomainHandler Protocol and DomainRouter.
"""

from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

if TYPE_CHECKING:
    pass


@runtime_checkable
class DomainHandler(Protocol):
    """Protocol for domain-specific handlers.

    All domain handlers (agent, tool, execution, economy, genesis, memory)
    must implement this interface. The ExecutionCoordinator depends on this
    abstraction rather than concrete handler classes (DIP).
    """

    async def handle(self, resource: str, action: str, params: dict[str, Any] | None) -> dict[str, Any]:
        """Handle a domain call for the given resource and action.

        Args:
            resource: The resource identifier within the domain.
            action: The action to perform on the resource.
            params: Optional parameters for the action.

        Returns:
            A result dictionary with at minimum a "status" key.
        """
        ...


class DomainRouter:
    """Routes calls to the appropriate DomainHandler based on domain name.

    Replaces the _DOMAIN_HANDLERS dict in ExecutionCoordinator with a
    handler-based dispatch mechanism.
    """

    def __init__(self) -> None:
        self._handlers: dict[str, DomainHandler] = {}

    def register(self, domain: str, handler: DomainHandler) -> None:
        """Register a handler for a domain."""
        self._handlers[domain] = handler

    async def route(self, domain: str, resource: str, action: str, params: dict[str, Any] | None) -> dict[str, Any]:
        """Route a call to the appropriate handler (async).

        Returns an error dict if no handler is registered for the domain.
        """
        handler = self._handlers.get(domain)
        if handler is None:
            return {"status": "error", "message": f"Unknown domain: {domain}"}
        return await handler.handle(resource, action, params)

    def list_domains(self) -> list[str]:
        """List all registered domains."""
        return list(self._handlers.keys())
