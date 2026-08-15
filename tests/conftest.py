"""Global pytest fixtures and environment configuration for omlxc tests."""

import os

import pytest

# Strip proxy environment variables to ensure test isolation from host network proxies
for _key in [
    "ALL_PROXY",
    "all_proxy",
    "HTTP_PROXY",
    "http_proxy",
    "HTTPS_PROXY",
    "https_proxy",
    "NO_PROXY",
    "no_proxy",
]:
    os.environ.pop(_key, None)


@pytest.fixture(autouse=True)
def _isolate_proxy_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure every test runs with proxy environment variables removed."""
    for key in [
        "ALL_PROXY",
        "all_proxy",
        "HTTP_PROXY",
        "http_proxy",
        "HTTPS_PROXY",
        "https_proxy",
        "NO_PROXY",
        "no_proxy",
    ]:
        monkeypatch.delenv(key, raising=False)
