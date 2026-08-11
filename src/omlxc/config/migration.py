"""Read-only legacy JSON migration into configuration schema v1."""

from __future__ import annotations

import json
import re
import shlex
from collections.abc import Mapping
from pathlib import Path
from typing import Any, cast

from pydantic import BaseModel, ConfigDict, JsonValue

from omlxc.domain import BackendKind, RouteProfile

from .loading import ConfigError, safe_defaults
from .schema import (
    AppConfig,
    BackendConfig,
    ModelConfig,
    NodeConfig,
    PlacementConfig,
    PoliciesConfig,
    RemoteResidentConfig,
)


class MigrationPlan(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    schema_version: str = "1"
    source_schema: str
    target_schema: str = "omlxc-config-v1"
    model_count: int
    node_count: int
    backend_count: int
    placement_count: int
    fallback_count: int
    ollama_fallback_count: int
    resident_count: int
    remote_resident_count: int
    will_write: bool = False
    target_exists: bool


def migrate_legacy_json(source: Path, *, base_directory: Path | None = None) -> AppConfig:
    legacy = _read_legacy_json(source)
    _assert_no_plaintext_auth(legacy)
    cluster = _mapping(legacy.get("cluster"), "cluster")
    legacy_nodes = _sequence(cluster.get("nodes"), "cluster.nodes")
    nodes = tuple(_migrate_node(item, index) for index, item in enumerate(legacy_nodes))
    address_to_node = {address: node.id for node in nodes for address in node.addresses}
    local_node_id = _local_node_id(legacy, nodes)
    backends = _migrate_backends(legacy, legacy_nodes, nodes, local_node_id)
    app_backend_id = next(
        backend.id for backend in backends if backend.kind is BackendKind.OMLX_APP
    )
    legacy_models = _mapping(legacy.get("models"), "models")
    resident = tuple(
        str(item)
        for item in _sequence(
            _mapping(legacy.get("autopilot"), "autopilot").get("resident", []),
            "autopilot.resident",
        )
    )
    models = tuple(
        _migrate_model(str(model_id), _mapping(value, f"models.{model_id}"))
        for model_id, value in legacy_models.items()
    )
    placements = tuple(
        _migrate_placement(
            model,
            _mapping(legacy_models[model.id], f"models.{model.id}"),
            app_backend_id,
            resident,
        )
        for model in models
    )
    defaults = safe_defaults(base_directory=base_directory)
    return AppConfig(
        schema_version=1,
        daemon=defaults.daemon,
        storage=defaults.storage,
        nodes=nodes,
        backends=backends,
        models=models,
        placements=placements,
        policies=_migrate_policies(legacy, address_to_node),
        legacy_extensions=_legacy_extensions(legacy),
    )


def build_migration_plan(
    source: Path, *, target: Path, base_directory: Path | None = None
) -> MigrationPlan:
    config = migrate_legacy_json(source, base_directory=base_directory)
    return MigrationPlan(
        source_schema="legacy-models-json-v2",
        model_count=len(config.models),
        node_count=len(config.nodes),
        backend_count=len(config.backends),
        placement_count=len(config.placements),
        fallback_count=len(config.policies.fallbacks),
        ollama_fallback_count=len(config.policies.ollama_fallbacks),
        resident_count=len(config.policies.resident_models),
        remote_resident_count=len(config.policies.remote_resident),
        target_exists=target.expanduser().exists(),
    )


def _read_legacy_json(source: Path) -> dict[str, Any]:
    def reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ConfigError("legacy JSON contains a duplicate key")
            result[key] = value
        return result

    try:
        raw = json.loads(source.read_text(encoding="utf-8"), object_pairs_hook=reject_duplicates)
    except (OSError, json.JSONDecodeError) as exc:
        raise ConfigError("unable to read valid legacy JSON") from exc
    if not isinstance(raw, dict):
        raise ConfigError("legacy JSON root must be an object")
    typed_raw = cast(dict[str, Any], raw)
    if typed_raw.get("version") != 2:
        raise ConfigError("unsupported legacy JSON version")
    return typed_raw


def _migrate_node(value: object, index: int) -> NodeConfig:
    item = _mapping(value, f"cluster.nodes[{index}]")
    display_name = _required_string(item.get("name"), "node name")
    role = _required_string(item.get("role"), "node role")
    address = _required_string(item.get("host"), "node address")
    return NodeConfig(
        id=_slug(display_name),
        display_name=display_name,
        platform="unknown",
        role=role,
        addresses=(address,),
    )


def _migrate_backends(
    legacy: Mapping[str, Any],
    legacy_nodes: list[object],
    nodes: tuple[NodeConfig, ...],
    local_node_id: str,
) -> tuple[BackendConfig, ...]:
    result: list[BackendConfig] = []
    app = _mapping(legacy.get("omlx_app"), "omlx_app")
    result.append(
        BackendConfig(
            id=f"{local_node_id}-omlx-app",
            node_id=local_node_id,
            kind=BackendKind.OMLX_APP,
            base_url=_required_string(app.get("base_url"), "omlx_app.base_url"),
        )
    )
    for source_node, node in zip(legacy_nodes, nodes, strict=True):
        probes = _mapping(_mapping(source_node, "cluster node").get("probe"), "node.probe")
        address = node.addresses[0]
        for service, raw_port in probes.items():
            kind = _backend_kind(str(service))
            if kind is None:
                continue
            port = _integer(raw_port, f"probe.{service}")
            result.append(
                BackendConfig(
                    id=f"{node.id}-{kind.value}",
                    node_id=node.id,
                    kind=kind,
                    base_url=f"http://{address}:{port}",
                )
            )
    unique = {backend.id: backend for backend in result}
    return tuple(unique.values())


def _migrate_model(model_id: str, value: Mapping[str, Any]) -> ModelConfig:
    parameters = _mapping(value.get("params", {}), f"models.{model_id}.params")
    size = value.get("size_gb")
    return ModelConfig(
        id=model_id,
        category=str(value.get("category") or "unknown"),
        role=str(value.get("role") or "chat"),
        engine=str(value.get("engine") or "unknown"),
        size_gb=float(size) if isinstance(size, int | float) else None,
        reasoning=bool(value.get("reasoning", False)),
        parameters=dict(parameters),
        note=str(value["note"]) if value.get("note") is not None else None,
        requires_pip=(
            str(value["requires_pip"]) if value.get("requires_pip") is not None else None
        ),
    )


def _migrate_placement(
    model: ModelConfig,
    value: Mapping[str, Any],
    backend_id: str,
    resident: tuple[str, ...],
) -> PlacementConfig:
    path = value.get("alias")
    port = value.get("port")
    max_tokens = _mapping(value.get("params", {}), "model.params").get("max_tokens")
    return PlacementConfig(
        id=f"{_slug(model.id)}-local",
        model_id=model.id,
        backend_id=backend_id,
        backend_model_id=model.id,
        model_path=str(path) if path is not None else None,
        context_limit=_integer(max_tokens, "params.max_tokens") if max_tokens else None,
        memory_gb=model.size_gb,
        resident=model.id in resident,
        legacy_port=_integer(port, "model.port") if port is not None else None,
    )


def _migrate_policies(
    legacy: Mapping[str, Any], address_to_node: Mapping[str, str]
) -> PoliciesConfig:
    autopilot = _mapping(legacy.get("autopilot"), "autopilot")
    app = _mapping(legacy.get("omlx_app"), "omlx_app")
    request_defaults = _mapping(app.get("request_defaults", {}), "request_defaults")
    remote_values = _sequence(autopilot.get("remote_resident", []), "remote_resident")
    remote = tuple(
        _migrate_remote_resident(value, index, address_to_node)
        for index, value in enumerate(remote_values)
    )
    presets = _mapping(legacy.get("presets", {}), "presets")
    return PoliciesConfig(
        default_profile=RouteProfile.INTERACTIVE,
        thinking_enabled=False,
        memory_free_percent_floor=_optional_float(autopilot.get("mem_free_pct_floor")),
        idle_ttl_seconds=_optional_int(autopilot.get("idle_ttl_sec")),
        resident_models=tuple(
            str(item) for item in _sequence(autopilot.get("resident", []), "resident")
        ),
        remote_resident=remote,
        fallbacks=_string_mapping(legacy.get("fallback", {}), "fallback"),
        ollama_fallbacks=_string_mapping(legacy.get("fallback_ollama", {}), "fallback_ollama"),
        presets={
            str(key): tuple(str(item) for item in _sequence(value, f"presets.{key}"))
            for key, value in presets.items()
        },
        sampling_defaults=dict(_mapping(legacy.get("defaults", {}), "defaults")),
        thinking_settings={"legacy_request_defaults": dict(request_defaults)},
    )


def _migrate_remote_resident(
    value: object, index: int, address_to_node: Mapping[str, str]
) -> RemoteResidentConfig:
    item = _mapping(value, f"remote_resident[{index}]")
    address = _required_string(item.get("host"), "remote resident address")
    node_id = address_to_node.get(address)
    if node_id is None:
        raise ConfigError("remote resident references an unknown node address")
    kind = _backend_kind(_required_string(item.get("engine"), "remote resident engine"))
    if kind is None or kind not in {BackendKind.LM_STUDIO, BackendKind.OLLAMA}:
        raise ConfigError("remote resident uses an unsupported backend kind")
    return RemoteResidentConfig(
        node_id=node_id,
        kind=kind,
        backend_model_id=_required_string(item.get("model"), "remote resident model"),
        port=_integer(item.get("port"), "remote resident port"),
        keep_alive_seconds=_optional_int(item.get("keep_alive_sec")),
        lms_arguments=tuple(shlex.split(str(item.get("lms_args") or ""))),
        ssh=bool(item.get("ssh", False)),
        ssh_alias=str(item["ssh_alias"]) if item.get("ssh_alias") is not None else None,
        windows=bool(item.get("windows", False)),
    )


def _local_node_id(legacy: Mapping[str, Any], nodes: tuple[NodeConfig, ...]) -> str:
    host = legacy.get("host")
    for node in nodes:
        if host in node.addresses:
            return node.id
    if not nodes:
        raise ConfigError("legacy configuration contains no nodes")
    return nodes[0].id


def _backend_kind(service: str) -> BackendKind | None:
    normalized = service.lower().replace("-", "").replace("_", "")
    return {
        "omlxapp": BackendKind.OMLX_APP,
        "lmstudio": BackendKind.LM_STUDIO,
        "lmlink": BackendKind.LM_LINK,
        "ollama": BackendKind.OLLAMA,
    }.get(normalized)


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    if not slug:
        raise ConfigError("unable to derive a stable node id from its name")
    return slug


def _mapping(value: object, name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ConfigError(f"legacy field {name} must be an object")
    return cast(dict[str, Any], value)


def _sequence(value: object, name: str) -> list[object]:
    if not isinstance(value, list):
        raise ConfigError(f"legacy field {name} must be an array")
    return cast(list[object], value)


def _required_string(value: object, name: str) -> str:
    if not isinstance(value, str) or not value:
        raise ConfigError(f"legacy field {name} must be a non-empty string")
    return value


def _integer(value: object, name: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise ConfigError(f"legacy field {name} must be an integer")
    return value


def _optional_int(value: object) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _optional_float(value: object) -> float | None:
    if isinstance(value, int | float) and not isinstance(value, bool):
        return float(value)
    return None


def _string_mapping(value: object, name: str) -> dict[str, str]:
    mapping = _mapping(value, name)
    result: dict[str, str] = {}
    for key, item in mapping.items():
        if key.startswith("_"):
            continue
        if not isinstance(item, str):
            raise ConfigError(f"legacy field {name} values must be strings")
        result[str(key)] = item
    return result


_AUTH_KEY = re.compile(
    r"(?i)(^|[_-])(secret|token|key|password|authorization|credential)"
    r"([_-](value|ref))?$"
)
_URL_AUTH = re.compile(r"(?i)[a-z][a-z0-9+.-]*://[^/@\s]+@")


def _assert_no_plaintext_auth(value: object, *, key: str | None = None) -> None:
    if (
        key is not None
        and _AUTH_KEY.search(key)
        and value is not None
        and not (isinstance(value, str) and value.startswith("keychain://"))
    ):
        raise ConfigError("legacy plaintext authentication material must use a Keychain reference")
    if isinstance(value, str) and _URL_AUTH.search(value):
        raise ConfigError(
            "legacy address authentication material must be replaced with a Keychain reference"
        )
    if isinstance(value, dict):
        for child_key, child in cast(dict[object, object], value).items():
            _assert_no_plaintext_auth(child, key=str(child_key))
    elif isinstance(value, list):
        for child in cast(list[object], value):
            _assert_no_plaintext_auth(child)


def _legacy_extensions(legacy: Mapping[str, Any]) -> dict[str, JsonValue]:
    consumed_root = {
        "version",
        "host",
        "omlx_app",
        "defaults",
        "models",
        "cluster",
        "autopilot",
        "engine_policy",
        "fallback",
        "fallback_ollama",
        "presets",
    }
    extensions: dict[str, Any] = {
        str(key): value for key, value in legacy.items() if key not in consumed_root
    }
    cluster = _mapping(legacy.get("cluster"), "cluster")
    cluster_metadata = {key: value for key, value in cluster.items() if key != "nodes"}
    if cluster_metadata:
        extensions["cluster_metadata"] = cluster_metadata
    autopilot = _mapping(legacy.get("autopilot"), "autopilot")
    autopilot_metadata = {
        key: value
        for key, value in autopilot.items()
        if key
        not in {
            "resident",
            "remote_resident",
            "mem_free_pct_floor",
            "idle_ttl_sec",
        }
    }
    if autopilot_metadata:
        extensions["autopilot_metadata"] = autopilot_metadata
    app = _mapping(legacy.get("omlx_app"), "omlx_app")
    app_metadata = {
        key: value for key, value in app.items() if key not in {"base_url", "request_defaults"}
    }
    if app_metadata:
        extensions["omlx_app_metadata"] = app_metadata
    engine_policy = _mapping(legacy.get("engine_policy", {}), "engine_policy")
    if engine_policy:
        extensions["engine_policy"] = engine_policy
    fallback_metadata = {
        key: value
        for key, value in _mapping(legacy.get("fallback", {}), "fallback").items()
        if str(key).startswith("_")
    }
    if fallback_metadata:
        extensions["fallback_metadata"] = fallback_metadata
    ollama_metadata = {
        key: value
        for key, value in _mapping(legacy.get("fallback_ollama", {}), "fallback_ollama").items()
        if str(key).startswith("_")
    }
    if ollama_metadata:
        extensions["fallback_ollama_metadata"] = ollama_metadata
    return cast(dict[str, JsonValue], extensions)
