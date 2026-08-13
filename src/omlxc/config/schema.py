"""Versioned TOML configuration schema."""

from __future__ import annotations

import ipaddress
import re
from collections.abc import Sequence
from pathlib import Path
from typing import Literal, Protocol, Self, cast

from pydantic import BaseModel, ConfigDict, Field, JsonValue, field_validator, model_validator

from omlxc.domain import BackendKind, RouteProfile
from omlxc.domain.security import (
    CredentialPolicyError,
    has_embedded_url_auth,
    is_keychain_reference,
    validate_keychain_only,
)


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


class TailscaleConfig(ConfigModel):
    executable: Path
    snapshot_ttl_seconds: int = Field(default=30, ge=1, le=300)

    @field_validator("executable", mode="before")
    @classmethod
    def parse_executable(cls, value: object) -> object:
        return Path(value) if isinstance(value, str) else value

    @field_validator("executable")
    @classmethod
    def absolute_executable(cls, value: Path) -> Path:
        if not value.is_absolute():
            raise ValueError("Tailscale executable must use an absolute path")
        return value


class TailscaleNodePolicyConfig(ConfigModel):
    peer_id: str = Field(min_length=16, max_length=128, pattern=r"^[A-Za-z0-9_-]+$")
    public_key: str = Field(
        min_length=28,
        max_length=136,
        pattern=r"^nodekey:[A-Za-z0-9+/=_-]+$",
    )
    magic_dns_name: str = Field(min_length=1)
    allowed_ips: tuple[str, ...] = Field(min_length=1)
    allowed_http_ports: tuple[int, ...] = Field(min_length=1)
    allowed_ssh_users: tuple[str, ...] = Field(min_length=1)

    @field_validator("allowed_ips", "allowed_http_ports", "allowed_ssh_users", mode="before")
    @classmethod
    def lists_to_tuples(cls, value: object) -> object:
        return tuple(cast(list[object], value)) if isinstance(value, list) else value

    @field_validator("magic_dns_name")
    @classmethod
    def normalize_dns(cls, value: str) -> str:
        normalized = value.rstrip(".").lower()
        labels = normalized.split(".")
        if len(labels) < 2 or any(
            not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", label) for label in labels
        ):
            raise ValueError("invalid Tailscale MagicDNS name")
        return normalized

    @field_validator("allowed_ips")
    @classmethod
    def tailscale_ips_only(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        normalized: list[str] = []
        networks = (
            ipaddress.ip_network("100.64.0.0/10"),
            ipaddress.ip_network("fd7a:115c:a1e0::/48"),
        )
        for value in values:
            address = ipaddress.ip_address(value)
            if not any(address in network for network in networks):
                raise ValueError("allowed IP must be in a Tailscale range")
            normalized.append(str(address))
        if len(normalized) != len(set(normalized)):
            raise ValueError("allowed Tailscale IPs must be unique")
        return tuple(normalized)

    @field_validator("allowed_http_ports")
    @classmethod
    def valid_ports(cls, values: tuple[int, ...]) -> tuple[int, ...]:
        if any(isinstance(port, bool) or not 1 <= port <= 65535 for port in values):
            raise ValueError("allowed HTTP port is invalid")
        if len(values) != len(set(values)):
            raise ValueError("allowed HTTP ports must be unique")
        return values

    @field_validator("allowed_ssh_users")
    @classmethod
    def valid_users(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        if any(not re.fullmatch(r"[A-Za-z_][A-Za-z0-9._-]{0,31}", user) for user in values):
            raise ValueError("allowed SSH user is invalid")
        if len(values) != len(set(values)):
            raise ValueError("allowed SSH users must be unique")
        return values


class NodeConfig(ConfigModel):
    id: str = Field(min_length=1, pattern=r"^[a-z0-9][a-z0-9._-]*$")
    display_name: str = Field(min_length=1)
    platform: str
    role: str | None = None
    addresses: tuple[str, ...] = ()
    tailscale_identity: str | None = None
    tailscale: TailscaleNodePolicyConfig | None = None
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
    probe_model_id: str | None = None
    known_hosts_file: Path | None = None
    lms_platform: Literal["macos", "windows"] = "macos"

    @field_validator("kind", mode="before")
    @classmethod
    def parse_kind(cls, value: object) -> object:
        return BackendKind(value) if isinstance(value, str) else value

    @field_validator("credential_ref")
    @classmethod
    def keychain_reference_only(cls, value: str | None) -> str | None:
        if value is not None and not is_keychain_reference(value):
            raise CredentialPolicyError("credential_ref must be a valid Keychain reference")
        return value

    @field_validator("base_url", "control_endpoint")
    @classmethod
    def reject_embedded_auth(cls, value: str | None) -> str | None:
        if value is not None:
            _require_keychain_for_url_auth(value)
        return value

    @field_validator("known_hosts_file", mode="before")
    @classmethod
    def parse_known_hosts(cls, value: object) -> object:
        return Path(value) if isinstance(value, str) else value

    @model_validator(mode="after")
    def validate_lm_control_pair(self) -> Self:
        if self.kind in {BackendKind.LM_STUDIO, BackendKind.LM_LINK}:
            if (self.control_endpoint is None) != (self.known_hosts_file is None):
                raise ValueError(
                    "LM control_endpoint and known_hosts_file must be configured together"
                )
        elif self.known_hosts_file is not None:
            raise ValueError("known_hosts_file is only valid for LM backends")
        return self


class ModelConfig(ConfigModel):
    id: str = Field(min_length=1)
    category: str
    role: str
    engine: str
    size_gb: float | None = Field(default=None, gt=0)
    reasoning: bool = False
    parameters: dict[str, JsonValue] = Field(default_factory=dict)
    aliases: tuple[str, ...] = ()
    note: str | None = None
    requires_pip: str | None = None

    @field_validator("aliases", mode="before")
    @classmethod
    def list_to_tuple(cls, value: object) -> object:
        return tuple(cast(list[object], value)) if isinstance(value, list) else value


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
    tailscale: TailscaleConfig | None = None
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
        validate_keychain_only(self.model_dump(mode="python", exclude_none=True))
        return self


class _Identified(Protocol):
    id: str


def _unique_ids(kind: str, values: Sequence[_Identified]) -> set[str]:
    identifiers = [str(value.id) for value in values]
    if len(identifiers) != len(set(identifiers)):
        raise ValueError(f"duplicate {kind} id")
    return set(identifiers)


def _require_keychain_for_url_auth(value: str) -> None:
    if has_embedded_url_auth(value):
        raise CredentialPolicyError(
            "URL authentication material must use a valid Keychain reference"
        )
