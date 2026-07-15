"""Agora execution plane — spawn isolation for stdio / mcp_stdio (Scheme C 5b)."""

from .container_executor import (
    BackendName,
    IsolationProfile,
    SpawnHandle,
    SpawnSpec,
    build_spawn_argv,
    docker_available,
    get_backend,
    load_profiles,
    resolve_backend,
    spawn_async,
    spawn_sync,
)

__all__ = [
    "BackendName",
    "IsolationProfile",
    "SpawnHandle",
    "SpawnSpec",
    "build_spawn_argv",
    "docker_available",
    "get_backend",
    "load_profiles",
    "resolve_backend",
    "spawn_async",
    "spawn_sync",
]
