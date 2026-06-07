"""Domain routing abstractions — DomainHandler Protocol and DomainRouter."""

from typing import Protocol, runtime_checkable


@runtime_checkable
class DomainHandler(Protocol):
    """Protocol for domain-specific handlers.

    All domain handlers must implement this interface.
    """
