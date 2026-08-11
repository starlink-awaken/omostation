"""Local compute adapters must never consume ambient proxy configuration."""

from __future__ import annotations

from collections.abc import Callable

import httpx
import pytest

from omlxc.adapters import LmStudioAdapter, OllamaAdapter, OmlxAppAdapter


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "factory",
    [
        lambda: OmlxAppAdapter(backend_id="local", base_url="http://127.0.0.1:1"),
        lambda: LmStudioAdapter(backend_id="local", base_url="http://127.0.0.1:1"),
        lambda: OllamaAdapter(backend_id="local", base_url="http://127.0.0.1:1"),
    ],
)
async def test_default_http_client_ignores_ambient_socks_proxy(
    monkeypatch: pytest.MonkeyPatch,
    factory: Callable[[], OmlxAppAdapter | LmStudioAdapter | OllamaAdapter],
) -> None:
    monkeypatch.setenv("ALL_PROXY", "socks5://127.0.0.1:9")
    monkeypatch.delenv("HTTP_PROXY", raising=False)
    monkeypatch.delenv("HTTPS_PROXY", raising=False)

    adapter = factory()
    await adapter.aclose()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "factory",
    [
        lambda transport: OmlxAppAdapter(
            backend_id="local", base_url="http://127.0.0.1:1", transport=transport
        ),
        lambda transport: LmStudioAdapter(
            backend_id="local", base_url="http://127.0.0.1:1", transport=transport
        ),
        lambda transport: OllamaAdapter(
            backend_id="local", base_url="http://127.0.0.1:1", transport=transport
        ),
    ],
)
async def test_local_mock_transport_remains_direct_with_ambient_proxy(
    monkeypatch: pytest.MonkeyPatch,
    factory: Callable[[httpx.AsyncBaseTransport], OmlxAppAdapter | LmStudioAdapter | OllamaAdapter],
) -> None:
    monkeypatch.setenv("ALL_PROXY", "socks5://127.0.0.1:9")

    async def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"data": [], "models": []})

    adapter = factory(httpx.MockTransport(handler))
    try:
        assert await adapter.list_models() == ()
    finally:
        await adapter.aclose()
