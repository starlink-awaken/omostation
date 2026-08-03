"""Tests for Scheme C Phase 5b container executor."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from agora.execution.container_executor import (
    IsolationProfile,
    MountSpec,
    SpawnSpec,
    build_docker_argv,
    build_spawn_argv,
    describe_executor_status,
    docker_available,
    filter_spawn_env,
    load_profiles,
    resolve_backend,
)


@pytest.fixture()
def profiles_path() -> Path:
    # etc/ sits next to src/ under projects/agora
    root = Path(__file__).resolve().parents[1]
    return root / "etc" / "container-executor-profiles.yaml"


def test_load_profiles_from_ssot(profiles_path: Path):
    cfg = load_profiles(profiles_path)
    assert cfg.default_backend == "local"
    assert "default" in cfg.profiles
    assert "trusted-local" in cfg.profiles
    assert cfg.profiles["default"].network == "none"
    assert cfg.profiles["trusted-local"].local_only is True
    assert cfg.profiles["default"].read_only_root is True


def test_build_docker_argv_contains_isolation_flags(profiles_path: Path):
    cfg = load_profiles(profiles_path)
    profile = cfg.profiles["default"]
    spec = SpawnSpec(command="python3", args=("-m", "demo"), cwd="/tmp/ws")
    argv = build_docker_argv(
        spec,
        profile,
        docker_bin="docker",
        docker_image="python:3.13-slim",
        workspace="/tmp/ws",
    )
    joined = " ".join(argv)
    assert argv[0] == "docker"
    assert "run" in argv
    assert "-i" in argv
    assert "--rm" in argv
    assert "--network=none" in argv
    assert "--read-only" in argv
    assert "--memory" in argv
    assert "512m" in argv
    assert "--cap-drop" in argv
    assert "ALL" in argv
    assert "--security-opt" in argv
    assert "no-new-privileges" in argv
    assert any("python:3.13-slim" in a for a in argv)
    image_args = [a for a in argv if "python:3.13-slim" in a]
    assert image_args, argv
    assert argv[-3:] == [image_args[-1], "python3", "-m"] or (
        "python3" in argv and "-m" in argv and "demo" in argv
    )
    assert "demo" in argv
    assert any(a.startswith("-v") or ":" in a for a in argv)
    assert "--network=host" not in joined


def test_trusted_local_profile_refuses_docker(profiles_path: Path):
    cfg = load_profiles(profiles_path)
    profile = cfg.profiles["trusted-local"]
    with pytest.raises(ValueError, match="local_only"):
        build_docker_argv(
            SpawnSpec(command="echo"),
            profile,
            docker_bin="docker",
            docker_image="python:3.13-slim",
        )


def test_build_spawn_argv_local_default(profiles_path: Path, monkeypatch):
    monkeypatch.setenv("AGORA_SPAWN_BACKEND", "local")
    cfg = load_profiles(profiles_path)
    handle = build_spawn_argv(
        SpawnSpec(command="uv", args=("run", "pytest"), cwd="/w"),
        backend="local",
        config=cfg,
        check_docker=False,
    )
    assert handle.backend == "local"
    assert handle.docker_wrapped is False
    assert handle.argv == ["uv", "run", "pytest"]
    assert handle.cwd == "/w"


def test_build_spawn_argv_docker_wraps(profiles_path: Path, monkeypatch):
    monkeypatch.delenv("AGORA_SPAWN_BACKEND", raising=False)
    cfg = load_profiles(profiles_path)
    handle = build_spawn_argv(
        SpawnSpec(command="python3", args=("-c", "print(1)")),
        backend="docker",
        config=cfg,
        check_docker=False,
    )
    assert handle.backend == "docker"
    assert handle.docker_wrapped is True
    assert handle.argv[0] == "docker"
    assert handle.cwd is None  # container workdir, not host cwd
    assert "python3" in handle.argv


def test_trusted_local_forces_local_even_if_docker_backend(
    profiles_path: Path, monkeypatch
):
    cfg = load_profiles(profiles_path)
    handle = build_spawn_argv(
        SpawnSpec(command="true", profile="trusted-local"),
        backend="docker",
        config=cfg,
        check_docker=False,
    )
    assert handle.backend == "local"
    assert handle.docker_wrapped is False
    assert any("local_only" in n for n in handle.notes)


def test_resolve_backend_local_env(monkeypatch):
    monkeypatch.setenv("AGORA_SPAWN_BACKEND", "local")
    assert resolve_backend(force_check_docker=False) == "local"


def test_resolve_backend_docker_strict_raises(monkeypatch, profiles_path: Path):
    monkeypatch.setenv("AGORA_SPAWN_BACKEND", "docker")
    monkeypatch.setenv("AGORA_SPAWN_STRICT", "1")
    cfg = load_profiles(profiles_path)

    def _no(_bin="docker"):
        return False

    monkeypatch.setattr("agora.execution.container_executor.docker_available", _no)
    with pytest.raises(RuntimeError, match="docker"):
        resolve_backend(config=cfg, force_check_docker=True)


def test_resolve_backend_docker_nonstrict_fallback(monkeypatch, profiles_path: Path):
    monkeypatch.setenv("AGORA_SPAWN_BACKEND", "docker")
    monkeypatch.setenv("AGORA_SPAWN_STRICT", "0")
    cfg = load_profiles(profiles_path)
    monkeypatch.setattr(
        "agora.execution.container_executor.docker_available", lambda _b="docker": False
    )
    assert resolve_backend(config=cfg, force_check_docker=True) == "local"


def test_filter_spawn_env_strips_secrets(monkeypatch):
    monkeypatch.setenv("AGORA_API_KEY", "secret")
    monkeypatch.setenv("SAFE_FLAG", "1")
    env = filter_spawn_env({"EXTRA": "x"})
    assert "AGORA_API_KEY" not in env
    assert env["EXTRA"] == "x"
    assert env["SAFE_FLAG"] == "1"


def test_describe_executor_status_shape(profiles_path: Path, monkeypatch):
    monkeypatch.setenv("AGORA_SPAWN_BACKEND", "local")
    monkeypatch.setenv("AGORA_SPAWN_PROFILES", str(profiles_path))
    status = describe_executor_status()
    assert status["effective_backend"] == "local"
    assert "default" in status["profiles"]
    assert "docker_image" in status
    assert status["error"] is None


def test_builtin_config_when_missing_yaml(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("AGORA_SPAWN_PROFILES", str(tmp_path / "nope.yaml"))
    cfg = load_profiles()
    assert "default" in cfg.profiles
    assert cfg.source == "builtin"


def test_isolation_profile_defaults():
    p = IsolationProfile(name="x", mounts=(MountSpec("/a", "/b", "ro"),))
    assert p.network == "none"
    assert p.drop_caps == ("ALL",)


@pytest.mark.skipif(
    not docker_available(),
    reason="docker daemon not available on this host",
)
def test_docker_available_live():
    assert docker_available() is True
