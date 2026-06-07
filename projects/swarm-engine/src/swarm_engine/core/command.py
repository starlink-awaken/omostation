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
# Command ≡ Module
# 内涵 ≝ {Command}
# 外延 ≝ {e | e ∈ Organs ∧ implements(e, Command)}
# 功能 ⊢ {Init_Command, Execute_Command, Validate_Command}
# =============================================================================

"""
---
Type: Module
Status: ACTIVE
Version: 1.0.0
Authority: organs/D-Execution/AGENTS.md
Layer: L3
---
Command pattern base classes for execution dispatch.
"""

from abc import ABC, abstractmethod
from typing import Any


class Command(ABC):
    """Abstract base for all executable commands in the dispatch system."""

    @abstractmethod
    async def execute(self, resource: str, action: str, params: dict[str, Any] | None) -> dict[str, Any]:
        """Execute the command with the given resource, action, and parameters.

        Args:
            resource: The resource identifier (e.g., "task", "agent", "ledger").
            action: The action to perform on the resource.
            params: Optional parameters for the action.

        Returns:
            A result dictionary with at minimum a "status" key.
        """
        ...


class CommandRegistry:
    """Registry for mapping (domain, resource, action) triples to Command instances.

    Replaces the if-elif chain in ExecutionCoordinator._handle_execution_call().
    """

    def __init__(self) -> None:
        # Three-level lookup: domain -> resource -> action -> Command
        self._commands: dict[str, dict[str, dict[str, Command]]] = {}

    def register(self, domain: str, resource: str, action: str, command: Command) -> None:
        """Register a command for a domain/resource/action triple."""
        if domain not in self._commands:
            self._commands[domain] = {}
        if resource not in self._commands[domain]:
            self._commands[domain][resource] = {}
        self._commands[domain][resource][action] = command

    def register_domain(self, domain: str) -> None:
        """Ensure a domain entry exists (no-op if already present)."""
        if domain not in self._commands:
            self._commands[domain] = {}

    def get(self, domain: str, resource: str, action: str) -> Command | None:
        """Retrieve a registered command, or None if not found."""
        return self._commands.get(domain, {}).get(resource, {}).get(action)

    def get_resource_commands(self, domain: str, resource: str) -> dict[str, Command]:
        """Get all registered commands for a domain/resource pair."""
        return self._commands.get(domain, {}).get(resource, {})

    def list_domains(self) -> list[str]:
        """List all registered domains."""
        return list(self._commands.keys())


# Module-level singleton registry for use by handlers and coordinator.
_registry: CommandRegistry | None = None


def get_registry() -> CommandRegistry:
    """Return the module-level CommandRegistry singleton, creating it if needed."""
    global _registry
    if _registry is None:
        _registry = CommandRegistry()
    return _registry
