"""BackendHealthChecker._is_transient — stdio 按需服务跳过 heartbeat 测试.

治本 transport 错配: stdio (有 command 无 mcp_endpoint) 调用时才 spawn 进程,
不该用常驻 heartbeat 验活 (ADR-0179 / p76).
"""

from __future__ import annotations

from unittest.mock import MagicMock

from agora.mcp_proxy.health import BackendHealthChecker


def _make_checker(services_config: dict[str, dict]) -> BackendHealthChecker:
    """造 checker, registry.get_saved_config 返回 services_config."""
    registry = MagicMock()
    registry.get_saved_config = lambda name: services_config.get(name)
    manager = MagicMock()
    manager.registry = registry
    return BackendHealthChecker(manager)


def test_stdio_service_is_transient():
    """stdio (有 command 无 mcp_endpoint) = transient, 跳过 heartbeat."""
    c = _make_checker(
        {"kos": {"command": ["uv", "run", "--directory", "projects/kairon"]}}
    )
    assert c._is_transient("kos") is True


def test_http_service_not_transient():
    """http/sse (有 mcp_endpoint) = 常驻, 参与 heartbeat."""
    c = _make_checker({"ollama": {"mcp_endpoint": "http://localhost:11434"}})
    assert c._is_transient("ollama") is False


def test_no_config_not_transient():
    """无 config = 保守不跳过 (未知服务仍 probe)."""
    c = _make_checker({"unknown": {}})
    assert c._is_transient("unknown") is False


def test_both_command_and_endpoint_not_transient():
    """command + endpoint = endpoint 优先, 视为常驻 (非 transient)."""
    c = _make_checker(
        {"hybrid": {"command": ["x"], "mcp_endpoint": "http://localhost:9"}}
    )
    assert c._is_transient("hybrid") is False


def test_no_registry_not_transient():
    """无 registry = 保守不跳过."""
    manager = MagicMock()
    manager.registry = None
    c = BackendHealthChecker(manager)
    assert c._is_transient("any") is False
