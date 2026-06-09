"""Agora MCP API Key Management Tools — extracted from server/mcp.py (Section 6).

God Module Phase 1 拆分: API Key CRUD (create/list/revoke).
"""

from __future__ import annotations


def register_tools(mcp, _ok, FORMAT_VERSION):
    """向 FastMCP 实例注册 API Key 工具。"""

    @mcp.tool()
    def create_api_key(
        name: str, scopes: str = "read", tenant: str = "", expires_days: int = 0
    ) -> dict:
        """Create a new API key. The raw secret is shown only once."""
        from agora.governance import KeyManager  # type: ignore[import-not-found]

        scope_list = [s.strip() for s in scopes.split(",") if s.strip()]
        kid, secret = KeyManager().create_key(name, scope_list, tenant, expires_days)
        return _ok(
            {
                "format_version": FORMAT_VERSION,
                "key_id": kid,
                "secret": secret,
                "warning": "Save this secret — it won't be shown again.",
            }
        )

    @mcp.tool()
    def list_api_keys(tenant: str = "") -> dict:
        """List API keys, optionally filtered by tenant."""
        from agora.governance import KeyManager  # type: ignore[import-not-found]

        return _ok(
            {
                "format_version": FORMAT_VERSION,
                "data": KeyManager().list_keys(tenant),
            }
        )

    @mcp.tool()
    def revoke_api_key(key_id: str) -> dict:
        """Revoke an API key by its ID."""
        from agora.governance import KeyManager  # type: ignore[import-not-found]

        KeyManager().revoke(key_id)
        return _ok(
            {
                "format_version": FORMAT_VERSION,
                "action": "revoked",
                "key_id": key_id,
            }
        )
