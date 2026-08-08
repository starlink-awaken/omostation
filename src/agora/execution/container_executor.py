"""Container Executor — pluggable isolation for stdio / mcp_stdio spawn.

Scheme C Phase 5b (ADR-0184).

Design goals
------------
1. **Single facade** for all Agora stdio spawn paths (proxy client + process pool).
2. **Pluggable backends**: ``local`` (current behavior) and ``docker`` (FS/net limits).
3. **SSOT profiles** in ``etc/container-executor-profiles.yaml``; env overrides.
4. **CI-safe default**: backend=local so required gates need no Docker socket.
5. **No Docker-as-MCP-tool**: this module only *uses* docker CLI as an executor;
   it does not expose container management capabilities to agents.

Env knobs
---------
AGORA_SPAWN_BACKEND   local | docker | auto   (default: SSOT or local)
AGORA_SPAWN_PROFILE   profile name            (default: default)
AGORA_SPAWN_STRICT    0|1 fail if docker missing when required
AGORA_SPAWN_DOCKER_IMAGE
AGORA_SPAWN_DOCKER_BIN
AGORA_SPAWN_PROFILES  path to profiles YAML
WORKSPACE_ROOT        host workspace for mounts
"""

from __future__ import annotations

import asyncio
import os
import shutil
import subprocess
import tempfile
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

try:
    import yaml
except ImportError:  # pragma: no cover - pyyaml is an agora transitive dep in practice
    yaml = None  # type: ignore[assignment]

BackendName = Literal["local", "docker"]
BackendSetting = Literal["local", "docker", "auto"]


# ── Models ────────────────────────────────────────────────────────

# Default image pin (Scheme C 5b follow-up / ADR-0205). Override via env or YAML.
DEFAULT_DOCKER_IMAGE = "python:3.13-slim@sha256:bffeb7bd6a85767587059c6ba23e1e9122078e3aa3fa836099171b9bb5a9bb00"


@dataclass(frozen=True)
class MountSpec:
    host: str
    container: str
    mode: str = "ro"  # ro | rw


@dataclass(frozen=True)
class IsolationProfile:
    name: str
    network: str = "none"
    read_only_root: bool = True
    memory_limit: str | None = "512m"
    cpus: str | None = "1.0"
    no_new_privileges: bool = True
    drop_caps: tuple[str, ...] = ("ALL",)
    workdir: str | None = "/workspace"
    mounts: tuple[MountSpec, ...] = ()
    local_only: bool = False
    image: str | None = None


@dataclass(frozen=True)
class SpawnSpec:
    """What to run (host command view)."""

    command: str
    args: tuple[str, ...] = ()
    cwd: str | None = None
    env: Mapping[str, str] | None = None
    profile: str | None = None
    service_name: str | None = None
    text: bool = False  # for subprocess.Popen text mode


@dataclass
class SpawnHandle:
    """Resolved spawn: argv actually executed + metadata for audit/evidence."""

    argv: list[str]
    backend: BackendName
    profile: str
    cwd: str | None
    env: dict[str, str] | None
    docker_wrapped: bool
    service_name: str | None = None
    notes: list[str] = field(default_factory=list)

    def to_audit_dict(self) -> dict[str, Any]:
        return {
            "backend": self.backend,
            "profile": self.profile,
            "docker_wrapped": self.docker_wrapped,
            "service_name": self.service_name,
            "argv0": self.argv[0] if self.argv else None,
            "argv_len": len(self.argv),
            "notes": list(self.notes),
        }


@dataclass(frozen=True)
class ExecutorConfig:
    default_backend: BackendSetting
    default_profile: str
    strict: bool
    docker_image: str
    docker_bin: str
    profiles: dict[str, IsolationProfile]
    source: str


# ── Profile loading ───────────────────────────────────────────────


def _package_etc() -> Path:
    # src/agora/execution/container_executor.py → projects/agora/etc
    return Path(__file__).resolve().parents[3] / "etc"


def _default_profiles_path() -> Path:
    env = os.environ.get("AGORA_SPAWN_PROFILES")
    if env:
        return Path(env)
    return _package_etc() / "container-executor-profiles.yaml"


def _expand_path(value: str, workspace: str, tmpdir: str) -> str:
    expanded = os.path.expanduser(os.path.expandvars(value))
    expanded = expanded.replace("${WORKSPACE_ROOT}", workspace)
    expanded = expanded.replace("${TMPDIR}", tmpdir)
    return expanded


def _parse_profile(
    name: str, raw: dict[str, Any], default_image: str
) -> IsolationProfile:
    mounts_raw = raw.get("mounts") or []
    mounts: list[MountSpec] = []
    for m in mounts_raw:
        if not isinstance(m, dict):
            continue
        mounts.append(
            MountSpec(
                host=str(m.get("host", "")),
                container=str(m.get("container", "")),
                mode=str(m.get("mode", "ro")),
            )
        )
    caps = raw.get("drop_caps") or []
    if isinstance(caps, str):
        caps = [caps]
    return IsolationProfile(
        name=name,
        network=str(raw.get("network", "none")),
        read_only_root=bool(raw.get("read_only_root", True)),
        memory_limit=raw.get("memory_limit"),
        cpus=str(raw["cpus"]) if raw.get("cpus") is not None else None,
        no_new_privileges=bool(raw.get("no_new_privileges", True)),
        drop_caps=tuple(str(c) for c in caps),
        workdir=raw.get("workdir"),
        mounts=tuple(mounts),
        local_only=bool(raw.get("local_only", False)),
        image=raw.get("image") or default_image,
    )


def _builtin_config() -> ExecutorConfig:
    """Fallback when YAML missing or PyYAML unavailable."""
    default = IsolationProfile(
        name="default",
        mounts=(
            MountSpec("${WORKSPACE_ROOT}", "/workspace", "ro"),
            MountSpec("${TMPDIR}", "/tmp", "rw"),
        ),
        image=DEFAULT_DOCKER_IMAGE,
    )
    trusted = IsolationProfile(
        name="trusted-local",
        network="host",
        read_only_root=False,
        no_new_privileges=False,
        drop_caps=(),
        mounts=(),
        local_only=True,
        image=None,
    )
    return ExecutorConfig(
        default_backend="local",
        default_profile="default",
        strict=False,
        docker_image=DEFAULT_DOCKER_IMAGE,
        docker_bin="docker",
        profiles={"default": default, "trusted-local": trusted},
        source="builtin",
    )


def load_profiles(path: Path | None = None) -> ExecutorConfig:
    """Load SSOT profiles; always returns a usable config."""
    cfg_path = path or _default_profiles_path()
    if yaml is None or not cfg_path.is_file():
        return _builtin_config()

    with cfg_path.open(encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    if not isinstance(data, dict):
        return _builtin_config()

    docker_image = str(
        os.environ.get("AGORA_SPAWN_DOCKER_IMAGE")
        or data.get("docker_image")
        or DEFAULT_DOCKER_IMAGE
    )
    docker_bin = str(
        os.environ.get("AGORA_SPAWN_DOCKER_BIN") or data.get("docker_bin") or "docker"
    )
    profiles: dict[str, IsolationProfile] = {}
    for name, raw in (data.get("profiles") or {}).items():
        if isinstance(raw, dict):
            profiles[str(name)] = _parse_profile(str(name), raw, docker_image)

    if not profiles:
        return _builtin_config()

    backend = str(data.get("default_backend") or "local").lower()
    if backend not in ("local", "docker", "auto"):
        backend = "local"

    return ExecutorConfig(
        default_backend=backend,  # type: ignore[arg-type]
        default_profile=str(data.get("default_profile") or "default"),
        strict=bool(data.get("strict", False)),
        docker_image=docker_image,
        docker_bin=docker_bin,
        profiles=profiles,
        source=str(cfg_path),
    )


# ── Backend resolution ────────────────────────────────────────────


def docker_available(docker_bin: str = "docker") -> bool:
    """True when docker CLI exists and daemon answers (best-effort)."""
    path = shutil.which(docker_bin) or (
        docker_bin if Path(docker_bin).is_file() else None
    )
    if not path:
        return False
    try:
        r = subprocess.run(
            [path, "info", "--format", "{{.ServerVersion}}"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        return r.returncode == 0 and bool((r.stdout or "").strip())
    except (OSError, subprocess.TimeoutExpired):
        return False


def resolve_backend(
    setting: BackendSetting | None = None,
    *,
    config: ExecutorConfig | None = None,
    force_check_docker: bool = True,
) -> BackendName:
    """Resolve effective backend from env / SSOT / docker availability."""
    cfg = config or load_profiles()
    raw = (
        setting or os.environ.get("AGORA_SPAWN_BACKEND") or cfg.default_backend
    ).lower()
    if raw not in ("local", "docker", "auto"):
        raw = "local"

    strict = os.environ.get("AGORA_SPAWN_STRICT", "1" if cfg.strict else "0") in (
        "1",
        "true",
        "yes",
    )

    if raw == "local":
        return "local"
    if raw == "docker":
        if not force_check_docker or docker_available(cfg.docker_bin):
            return "docker"
        if strict:
            raise RuntimeError(
                "AGORA_SPAWN_BACKEND=docker but docker CLI/daemon unavailable "
                "(set AGORA_SPAWN_STRICT=0 to fall back to local)"
            )
        return "local"
    # auto
    if force_check_docker and docker_available(cfg.docker_bin):
        return "docker"
    return "local"


def get_backend() -> BackendName:
    """Public helper: current effective backend."""
    return resolve_backend()


# ── Argv construction ─────────────────────────────────────────────


def _workspace_root(cwd: str | None) -> str:
    return os.environ.get("WORKSPACE_ROOT") or cwd or os.getcwd()


def _tmpdir() -> str:
    return os.environ.get("TMPDIR") or tempfile.gettempdir()


def _resolve_profile(name: str | None, config: ExecutorConfig) -> IsolationProfile:
    key = name or os.environ.get("AGORA_SPAWN_PROFILE") or config.default_profile
    if key not in config.profiles:
        # fall back gracefully
        return config.profiles.get(config.default_profile) or next(
            iter(config.profiles.values())
        )
    return config.profiles[key]


def build_docker_argv(
    spec: SpawnSpec,
    profile: IsolationProfile,
    *,
    docker_bin: str,
    docker_image: str,
    workspace: str | None = None,
) -> list[str]:
    """Translate host command into ``docker run -i --rm ...`` argv."""
    if profile.local_only:
        raise ValueError(
            f"profile {profile.name!r} is local_only — cannot use docker backend"
        )

    ws = workspace or _workspace_root(spec.cwd)
    tmp = _tmpdir()
    image = os.environ.get("AGORA_SPAWN_DOCKER_IMAGE") or profile.image or docker_image

    argv: list[str] = [
        docker_bin,
        "run",
        "-i",
        "--rm",
        f"--network={profile.network or 'none'}",
    ]
    if profile.read_only_root:
        argv.append("--read-only")
    if profile.memory_limit:
        argv.extend(["--memory", str(profile.memory_limit)])
    if profile.cpus:
        argv.extend(["--cpus", str(profile.cpus)])
    if profile.no_new_privileges:
        argv.extend(["--security-opt", "no-new-privileges"])
    for cap in profile.drop_caps:
        argv.extend(["--cap-drop", cap])
    if profile.workdir:
        argv.extend(["-w", profile.workdir])

    for m in profile.mounts:
        host = _expand_path(m.host, ws, tmp)
        # Ensure host path exists so docker doesn't create a root-owned dir
        Path(host).mkdir(parents=True, exist_ok=True)
        mode = m.mode if m.mode in ("ro", "rw") else "ro"
        argv.extend(["-v", f"{host}:{m.container}:{mode}"])

    # Pass through filtered env as -e KEY=VAL
    if spec.env:
        for k, v in spec.env.items():
            if k in _SENSITIVE_ENV_KEYS:
                continue
            # Skip huge PATH/HOME inheritance into container — set minimal set
            if k in ("PATH", "HOME", "PWD", "OLDPWD", "SHELL", "USER", "LOGNAME"):
                continue
            argv.extend(["-e", f"{k}={v}"])

    argv.append(image)
    argv.append(spec.command)
    argv.extend(list(spec.args))
    return argv


_SENSITIVE_ENV_KEYS = frozenset(
    {
        "AGORA_API_KEY",
        "AWS_SECRET_ACCESS_KEY",
        "AWS_ACCESS_KEY_ID",
        "DATABASE_URL",
        "DB_URL",
        "REDIS_URL",
        "REDIS_PASSWORD",
        "METAOS_SESSION_INTEGRITY_SECRET",
        "ECOS_WF_PREFLIGHT_SECRET",
    }
)


def filter_spawn_env(custom_env: Mapping[str, str] | None) -> dict[str, str]:
    """Merge + strip secrets (shared with mcp_proxy client)."""
    if custom_env:
        env = {**os.environ, **dict(custom_env)}
    else:
        env = os.environ.copy()
    for key in _SENSITIVE_ENV_KEYS:
        env.pop(key, None)
    return env


def build_spawn_argv(
    spec: SpawnSpec,
    *,
    backend: BackendName | None = None,
    config: ExecutorConfig | None = None,
    check_docker: bool = True,
) -> SpawnHandle:
    """Build final argv without spawning. Useful for tests and evidence."""
    cfg = config or load_profiles()
    profile = _resolve_profile(spec.profile, cfg)
    effective = backend or resolve_backend(config=cfg, force_check_docker=check_docker)
    notes: list[str] = []

    if effective == "docker" and profile.local_only:
        notes.append("profile local_only → force local backend")
        effective = "local"

    if effective == "docker":
        argv = build_docker_argv(
            spec,
            profile,
            docker_bin=cfg.docker_bin,
            docker_image=cfg.docker_image,
            workspace=_workspace_root(spec.cwd),
        )
        # Inside container, cwd is profile.workdir; do not pass host cwd to Popen
        return SpawnHandle(
            argv=argv,
            backend="docker",
            profile=profile.name,
            cwd=None,
            env=None,  # env already inlined as -e
            docker_wrapped=True,
            service_name=spec.service_name,
            notes=notes,
        )

    argv = [spec.command, *list(spec.args)]
    return SpawnHandle(
        argv=argv,
        backend="local",
        profile=profile.name,
        cwd=spec.cwd,
        env=filter_spawn_env(spec.env)
        if spec.env is not None
        else filter_spawn_env(None),
        docker_wrapped=False,
        service_name=spec.service_name,
        notes=notes,
    )


# ── Spawn entry points ────────────────────────────────────────────


async def spawn_async(
    spec: SpawnSpec,
    *,
    backend: BackendName | None = None,
    config: ExecutorConfig | None = None,
    stdin: int | None = asyncio.subprocess.PIPE,
    stdout: int | None = asyncio.subprocess.PIPE,
    stderr: int | None = asyncio.subprocess.PIPE,
    limit: int = 2**20,
) -> tuple[asyncio.subprocess.Process, SpawnHandle]:
    """Async spawn used by StdioMCPClient."""
    handle = build_spawn_argv(spec, backend=backend, config=config)
    proc = await asyncio.create_subprocess_exec(
        *handle.argv,
        stdin=stdin,
        stdout=stdout,
        stderr=stderr,
        cwd=handle.cwd,
        env=handle.env,
        limit=limit,
    )
    return proc, handle


def spawn_sync(
    spec: SpawnSpec,
    *,
    backend: BackendName | None = None,
    config: ExecutorConfig | None = None,
    stdin: int | None = subprocess.PIPE,
    stdout: int | None = subprocess.PIPE,
    stderr: int | None = subprocess.PIPE,
    text: bool | None = None,
) -> tuple[subprocess.Popen[Any], SpawnHandle]:
    """Sync spawn used by ProcessPool."""
    handle = build_spawn_argv(spec, backend=backend, config=config)
    use_text = spec.text if text is None else text
    proc = subprocess.Popen(
        handle.argv,
        stdin=stdin,
        stdout=stdout,
        stderr=stderr,
        text=use_text,
        cwd=handle.cwd,
        env=handle.env,
    )
    return proc, handle


def describe_executor_status() -> dict[str, Any]:
    """Evidence / doctor helper — no spawn side effects beyond docker info probe."""
    cfg = load_profiles()
    try:
        backend = resolve_backend(config=cfg, force_check_docker=True)
        docker_ok = backend == "docker" or docker_available(cfg.docker_bin)
    except RuntimeError as e:
        backend = "local"
        docker_ok = False
        err = str(e)
    else:
        err = None
    return {
        "default_backend_setting": cfg.default_backend,
        "effective_backend": backend,
        "default_profile": cfg.default_profile,
        "profiles": sorted(cfg.profiles.keys()),
        "docker_available": docker_ok,
        "docker_image": cfg.docker_image,
        "profiles_source": cfg.source,
        "strict": cfg.strict,
        "error": err,
    }
