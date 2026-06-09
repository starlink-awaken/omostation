"""Federation — cross-node service discovery and routing."""

from .federation import FederationManager
from .federation_router import FederationRouter

__all__ = ["FederationManager", "FederationRouter"]
