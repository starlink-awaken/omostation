"""F-01: 认证 fail-closed 回归测试。

覆盖:
- tools_auth.require_agora_api_key 在 AGORA_API_KEY 未配置时的 fail-closed 行为
- AGORA_AUTH_MODE=permissive 显式逃生舱
- tools_bos._bos_domain_authorized 的 fail-closed
- MCPAuthMiddleware 无 Authorization 头时拒绝 (401)
"""

from __future__ import annotations

from unittest.mock import MagicMock

from fastmcp.server.auth.authorization import AuthContext

from agora.auth.mcp_auth import MCPAuthError, MCPAuthMiddleware


def _mk_ctx() -> AuthContext:
    return AuthContext(token=None, component=None)


def test_require_api_key_fail_closed_without_key(monkeypatch):
    """AGORA_API_KEY 未配置且未显式 permissive → 必须拒绝 (fail-closed)。"""
    monkeypatch.delenv("AGORA_AUTH_MODE", raising=False)
    from agora.server import tools_auth

    monkeypatch.setattr(tools_auth, "_AGORA_API_KEY", "")
    assert tools_auth.require_agora_api_key(_mk_ctx()) is False
    assert tools_auth.agora_role_ctx.get() == "denied"


def test_require_api_key_explicit_permissive_allows_without_key(monkeypatch):
    """AGORA_AUTH_MODE=permissive 显式 opt-in → 本地开发放行。"""
    monkeypatch.setenv("AGORA_AUTH_MODE", "permissive")
    from agora.server import tools_auth

    monkeypatch.setattr(tools_auth, "_AGORA_API_KEY", "")
    assert tools_auth.require_agora_api_key(_mk_ctx()) is True
    assert tools_auth.agora_role_ctx.get() == "admin"


def test_auth_mode_defaults_required(monkeypatch):
    """默认 auth mode 为 required (fail-closed)。"""
    monkeypatch.delenv("AGORA_AUTH_MODE", raising=False)
    from agora.server.tools_auth import auth_mode, auth_permissive

    assert auth_mode() == "required"
    assert auth_permissive() is False


def test_require_api_key_valid_token(monkeypatch):
    """配置了 key + 正确 token → 通过。"""
    from agora.server import tools_auth

    monkeypatch.setattr(tools_auth, "_AGORA_API_KEY", "secret-key")
    ctx = _mk_ctx()
    ctx.token = MagicMock()
    ctx.token.token = "secret-key"
    assert tools_auth.require_agora_api_key(ctx) is True


def test_require_api_key_invalid_token(monkeypatch):
    """配置了 key + 错误 token → 拒绝。"""
    from agora.server import tools_auth

    monkeypatch.setattr(tools_auth, "_AGORA_API_KEY", "secret-key")
    ctx = _mk_ctx()
    ctx.token = MagicMock()
    ctx.token.token = "wrong-token"
    assert tools_auth.require_agora_api_key(ctx) is False


def test_bos_domain_authorized_fail_closed_without_key(monkeypatch):
    """AGORA_API_KEY 未配置 + 默认 required → _bos_domain_authorized 拒绝。"""
    monkeypatch.delenv("AGORA_AUTH_MODE", raising=False)
    from agora.server import tools_bos

    monkeypatch.setattr(tools_bos, "_AGORA_API_KEY", "")
    ok, msg = tools_bos._bos_domain_authorized(
        "bos://capability/foo/invoke", operation="read"
    )
    assert ok is False
    assert "not configured" in msg


def test_bos_domain_authorized_permissive_without_key(monkeypatch):
    """AGORA_API_KEY 未配置 + AGORA_AUTH_MODE=permissive → 放行。"""
    monkeypatch.setenv("AGORA_AUTH_MODE", "permissive")
    from agora.server import tools_bos

    monkeypatch.setattr(tools_bos, "_AGORA_API_KEY", "")
    ok, msg = tools_bos._bos_domain_authorized(
        "bos://capability/foo/invoke", operation="read"
    )
    assert ok is True
    assert msg == ""


def test_mcp_auth_middleware_rejects_request_without_auth_header(monkeypatch):
    """MCPAuthMiddleware 对无 Authorization 头请求抛 401 (fail-closed)。"""
    monkeypatch.setenv("SHAREDBRAIN_SOVEREIGN_KEY", "test-sovereign")
    mw = MCPAuthMiddleware(token_ttl=3600)
    try:
        mw.authenticate_request({})
        raised = False
    except MCPAuthError as exc:
        raised = True
        assert exc.code == MCPAuthMiddleware.ERR_UNAUTHORIZED
        assert "Authorization" in exc.message
    assert raised, "无 Authorization 头必须抛 401"


def test_mcp_auth_middleware_rejects_invalid_token(monkeypatch):
    """MCPAuthMiddleware 对无效 Bearer token 抛 401。"""
    monkeypatch.setenv("SHAREDBRAIN_SOVEREIGN_KEY", "test-sovereign")
    mw = MCPAuthMiddleware(token_ttl=3600)
    try:
        mw.authenticate_request({"Authorization": "Bearer not-a-real-token"})
        raised = False
    except MCPAuthError as exc:
        raised = True
        assert exc.code in (
            MCPAuthMiddleware.ERR_UNAUTHORIZED,
            MCPAuthMiddleware.ERR_INVALID_TOKEN,
        )
    assert raised, "无效 token 必须被拒绝"
