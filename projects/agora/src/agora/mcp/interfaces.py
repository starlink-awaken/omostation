"""Protocol interfaces for Agora gateway dependencies.

Provides structural-subtyping Protocol ABCs for OAuth2, rate limiting,
and federation routing.  Extracted from SharedBrain D_Gateway with
nucleus dependencies removed.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class IOAuth2Server(Protocol):
    """Protocol for OAuth2 token issuance and validation."""

    def validate_token(self, token: str) -> Any:
        """Validate a JWT access token and return an AuthenticatedUser.

        Raises:
            TokenRevokedError: Token has been explicitly revoked.
            TokenExpiredError: Token signature is valid but expired.
            InvalidTokenError: Token is malformed or signature is invalid.
        """
        ...

    def issue_token(self, client_id: str, client_secret: str, *args: Any, **kwargs: Any) -> Any:
        """Issue a new OAuth2 token for the given client credentials."""
        ...

    def list_clients(self) -> list:
        """Return a list of registered OAuth2 client info dicts."""
        ...


@runtime_checkable
class IRateLimiter(Protocol):
    """Protocol for request rate limiting."""

    def is_allowed(self, client_ip: str, route_path: str, config: Any) -> bool:
        """Check whether a request from *client_ip* on *route_path* is within limits."""
        ...


@runtime_checkable
class IFederationRouter(Protocol):
    """Protocol for inter-node federation routing."""

    def register_node(self, node_id: str, endpoint: str, capabilities: list[str] | None = None) -> None:
        """Register or update a remote node."""
        ...

    async def route_to_node(self, node_id: str, message: dict) -> dict:
        """Route *message* to the remote node identified by *node_id*."""
        ...

    def unregister_node(self, node_id: str) -> bool:
        """Remove a previously registered node."""
        ...


__all__ = ["IOAuth2Server", "IRateLimiter", "IFederationRouter"]
