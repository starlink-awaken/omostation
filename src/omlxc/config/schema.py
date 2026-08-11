"""Versioned TOML configuration schema."""

from __future__ import annotations

import re
from collections.abc import Sequence
from pathlib import Path
from typing import Protocol, Self, cast

from pydantic import BaseModel, ConfigDict, Field, JsonValue, field_validator, model_validator

from omlxc.domain import BackendKind, RouteProfile

_URL_WITH_PASSWORD = re.compile(r"(?i)[a-z][a-z0-9+.-]*://[^/@:]+:[^/@]+@")


class ConfigModel(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")


class DaemonConfig(ConfigModel):
    socket_path: Path
    autostart: bool = False
    probe_interval_seconds: float = Field(default=10.0, gt=0)

    @field_validator("socket_path", mode="before")
    @classmethod
    def parse_path(cls, value: object) -> object:
        return Path(value) if isinstance(value, str) else value


class StorageConfig(ConfigModel):
    database_path: Path
    retention_days: int = Field(default=30, ge=1)

    @field_validator("database_path", mode="before")
    @classmethod
    def parse_path(cls, value: object) -> object:
        return Path(value) if isinstance(value, str) else value


class NodeConfig(ConfigModel):
    id: str = Field(min_length=1, pattern=r"^[a-z0-9][a-z0-9._-]*$")
    display_name: str = Field(min_length=1)
    platform: str
    role: str | None = None
    addresses: tuple[str, ...] = ()
    tailscale_identity: str | None = None
    memory_gb: float | None = Field(default=None, gt=0)

    @field_validator("addresses", mode="before")
    @classmethod
    def list_to_tuple(cls, value: object) -> object:
        return tuple(cast(list[object], value)) if isinstance(value, list) else value

    @field_validator("addresses")
    @classmethod
    def reject_embedded_auth(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        for address in value:
            _require_keychain_for_url_auth(address)
        return value


class BackendConfig(ConfigModel):
    id: str = Field(min_length=1, pattern=r"^[a-z0-9][a-z0-9._-]*$")
    node_id: str = Field(min_length=1)
    kind: BackendKind
    base_url: str
    control_endpoint: str | None = None
    protocol_version: str = "openai-v1"
    credential_ref: str | None = None

    @field_validator("kind", mode="before")
    @classmethod
    def parse_kind(cls, value: object) -> object:
        return BackendKind(value) if isinstance(value, str) else value

    @field_validator("credential_ref")
    @classmethod
    def keychain_reference_only(cls, value: str | None) -> str | None:
        if value is not None and (
            not value.startswith("keychain://") or len(value.split("/", maxsplit=3)) < 4
        ):
            raise ValueError("credential_ref must be a Keychain reference")
        return value

    @field_validator("base_url", "control_endpoint")
    @classmethod
    def reject_embedded_auth(cls, value: str | None) -> str | None:
        if value is not None:
            _require_keychain_for_url_auth(value)
        return value


class ModelConfig(ConfigModel):
    id: str = Field(min_length=1)
    category: str
    role: str
    engine: str
    size_gb: float | None = Field(default=None, gt=0)
    reasoning: bool = False
    parameters: dict[str, JsonValue] = Field(default_factory=dict)
    note: str | None = None
    requires_pip: str | None = None


class PlacementConfig(ConfigModel):
    id: str = Field(min_length=1)
    model_id: str = Field(min_length=1)
    backend_id: str = Field(min_length=1)
    backend_model_id: str = Field(min_length=1)
    model_path: str | None = None
    context_limit: int | None = Field(default=None, gt=0)
    memory_gb: float | None = Field(default=None, gt=0)
    resident: bool = False
    legacy_port: int | None = Field(default=None, ge=1, le=65535)


class RemoteResidentConfig(ConfigModel):
    node_id: str = Field(min_length=1)
    kind: BackendKind
    backend_model_id: str = Field(min_length=1)
    port: int = Field(ge=1, le=65535)
    keep_alive_seconds: int | None = Field(default=None, gt=0)
    lms_arguments: tuple[str, ...] = ()
    ssh: bool = False
    ssh_alias: str | None = None
    windows: bool = False

    @field_validator("kind", mode="before")
    @classmethod
    def parse_kind(cls, value: object) -> object:
        return BackendKind(value) if isinstance(value, str) else value

    @field_validator("lms_arguments", mode="before")
    @classmethod
    def list_to_tuple(cls, value: object) -> object:
        return tuple(cast(list[object], value)) if isinstance(value, list) else value


class PoliciesConfig(ConfigModel):
    default_profile: RouteProfile = RouteProfile.INTERACTIVE
    thinking_enabled: bool = False
    memory_free_percent_floor: float | None = Field(default=20.0, ge=0, le=100)
    idle_ttl_seconds: int | None = Field(default=None, ge=0)
    resident_models: tuple[str, ...] = ()
    remote_resident: tuple[RemoteResidentConfig, ...] = ()
    fallbacks: dict[str, str] = Field(default_factory=dict)
    ollama_fallbacks: dict[str, str] = Field(default_factory=dict)
    presets: dict[str, tuple[str, ...]] = Field(default_factory=dict)
    sampling_defaults: dict[str, JsonValue] = Field(default_factory=dict)
    thinking_settings: dict[str, JsonValue] = Field(default_factory=dict)

    @field_validator("default_profile", mode="before")
    @classmethod
    def parse_profile(cls, value: object) -> object:
        return RouteProfile(value) if isinstance(value, str) else value

    @field_validator("resident_models", "remote_resident", mode="before")
    @classmethod
    def list_to_tuple(cls, value: object) -> object:
        return tuple(cast(list[object], value)) if isinstance(value, list) else value

    @field_validator("presets", mode="before")
    @classmethod
    def preset_lists_to_tuples(cls, value: object) -> object:
        if isinstance(value, dict):
            mapping = cast(dict[object, object], value)
            return {
                str(key): tuple(cast(list[object], item)) if isinstance(item, list) else item
                for key, item in mapping.items()
            }
        return value


class AppConfig(ConfigModel):
    schema_version: int = 1
    daemon: DaemonConfig
    storage: StorageConfig
    nodes: tuple[NodeConfig, ...] = ()
    backends: tuple[BackendConfig, ...] = ()
    models: tuple[ModelConfig, ...] = ()
    placements: tuple[PlacementConfig, ...] = ()
    policies: PoliciesConfig = Field(default_factory=PoliciesConfig)
    legacy_extensions: dict[str, JsonValue] = Field(default_factory=dict)

    @field_validator("nodes", "backends", "models", "placements", mode="before")
    @classmethod
    def list_to_tuple(cls, value: object) -> object:
        return tuple(cast(list[object], value)) if isinstance(value, list) else value

    @model_validator(mode="after")
    def validate_references(self) -> Self:
        if self.schema_version != 1:
            raise ValueError("unsupported schema_version; expected 1")
        node_ids = _unique_ids("node", self.nodes)
        backend_ids = _unique_ids("backend", self.backends)
        model_ids = _unique_ids("model", self.models)
        _unique_ids("placement", self.placements)
        for backend in self.backends:
            if backend.node_id not in node_ids:
                raise ValueError(f"backend {backend.id!r} references unknown node")
        for placement in self.placements:
            if placement.backend_id not in backend_ids:
                raise ValueError(f"placement {placement.id!r} references unknown backend")
            if placement.model_id not in model_ids:
                raise ValueError(f"placement {placement.id!r} references unknown model")
        return self


class _Identified(Protocol):
    id: str


def _unique_ids(kind: str, values: Sequence[_Identified]) -> set[str]:
    identifiers = [str(value.id) for value in values]
    if len(identifiers) != len(set(identifiers)):
        raise ValueError(f"duplicate {kind} id")
    return set(identifiers)


def _require_keychain_for_url_auth(value: str) -> None:
    if _URL_WITH_PASSWORD.search(value):
        raise ValueError("URL authentication material must use a Keychain reference")
