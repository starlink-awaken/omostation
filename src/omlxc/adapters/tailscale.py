"""Fail-closed Tailscale identity discovery and endpoint authorization."""

from __future__ import annotations

import asyncio
import ipaddress
import json
import math
import os
import re
import stat
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from types import MappingProxyType
from typing import cast
from urllib.parse import urlsplit

from pydantic import ConfigDict, Field, field_validator

from omlxc.domain.models import DomainModel

from .process import (
    BoundedProcessRunner,
    ProcessOutput,
    ProcessOutputLimitError,
    ProcessRunner,
    ProcessSpawnError,
)

TAILSCALE_STATUS_ARGS = ("status", "--json")
TAILSCALE_STATUS_TIMEOUT = 10.0
TAILSCALE_STATUS_OUTPUT_LIMIT = 4 * 1024 * 1024
TAILSCALE_PROCESS_ENV: Mapping[str, str] = MappingProxyType(
    {
        "PATH": "/usr/bin:/bin:/usr/sbin:/sbin",
        "LANG": "C",
        "LC_ALL": "C",
    }
)

_TAILSCALE_V4 = ipaddress.ip_network("100.64.0.0/10")
_TAILSCALE_V6 = ipaddress.ip_network("fd7a:115c:a1e0::/48")
_PEER_ID = re.compile(r"^[A-Za-z0-9_-]{16,128}$")
_PUBLIC_KEY = re.compile(r"^nodekey:[A-Za-z0-9+/=_-]{20,128}$")
_DNS_LABEL = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$")
_SSH_USER = re.compile(r"^[A-Za-z_][A-Za-z0-9._-]{0,31}$")


class TailscaleErrorCode(StrEnum):
    SPAWN = "spawn"
    TIMEOUT = "timeout"
    OUTPUT_LIMIT = "output_limit"
    PROCESS = "process"
    STATUS_FAILED = "status_failed"
    INVALID_JSON = "invalid_json"
    INVALID_SNAPSHOT = "invalid_snapshot"
    IDENTITY_CONFLICT = "identity_conflict"
    IDENTITY_DRIFT = "identity_drift"
    UNKNOWN_NODE = "unknown_node"
    OFFLINE = "offline"
    STALE = "stale"
    ENDPOINT_NOT_ALLOWED = "endpoint_not_allowed"


_ERROR_MESSAGES: dict[TailscaleErrorCode, str] = {
    TailscaleErrorCode.SPAWN: "Tailscale status process is unavailable",
    TailscaleErrorCode.TIMEOUT: "Tailscale status process timed out",
    TailscaleErrorCode.OUTPUT_LIMIT: "Tailscale status output exceeded its safety limit",
    TailscaleErrorCode.PROCESS: "Tailscale status process failed",
    TailscaleErrorCode.STATUS_FAILED: "Tailscale status command failed",
    TailscaleErrorCode.INVALID_JSON: "Tailscale status returned invalid JSON",
    TailscaleErrorCode.INVALID_SNAPSHOT: "Tailscale status has an invalid shape",
    TailscaleErrorCode.IDENTITY_CONFLICT: "Tailscale identity conflict detected",
    TailscaleErrorCode.IDENTITY_DRIFT: "Tailscale identity drift detected",
    TailscaleErrorCode.UNKNOWN_NODE: "Tailscale node is not allowlisted",
    TailscaleErrorCode.OFFLINE: "Tailscale node is offline",
    TailscaleErrorCode.STALE: "Tailscale snapshot is stale",
    TailscaleErrorCode.ENDPOINT_NOT_ALLOWED: "Tailscale endpoint is not authorized",
}


class TailscaleFailure(Exception):
    """Typed error boundary whose rendering never includes status or identity data."""

    def __init__(self, code: TailscaleErrorCode) -> None:
        self.code = code
        super().__init__(_ERROR_MESSAGES[code])

    def __repr__(self) -> str:
        return f"TailscaleFailure(code={self.code.value!r})"


class _DuplicateJsonKey(ValueError):
    pass


class _InvalidJsonConstant(ValueError):
    pass


class _AuthorizationFreshness(StrEnum):
    UNKNOWN = "unknown"
    STALE = "stale"
    FRESH = "fresh"


@dataclass(frozen=True, slots=True)
class _PathFingerprint:
    path: str
    device: int
    inode: int
    mode: int
    uid: int


@dataclass(frozen=True, slots=True)
class _TrustedExecutable:
    path: Path
    fingerprint: tuple[_PathFingerprint, ...]


class TailscaleNodePolicy(DomainModel):
    """Stable omlxc node identity bound to strong Tailscale identity and endpoints."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid", hide_input_in_errors=True)

    node_id: str = Field(min_length=1, pattern=r"^[a-z0-9][a-z0-9._-]*$")
    expected_peer_id: str = Field(exclude=True, repr=False)
    expected_public_key: str = Field(exclude=True, repr=False)
    magic_dns_name: str = Field(exclude=True, repr=False)
    allowed_ips: frozenset[str] = Field(exclude=True, repr=False, min_length=1)
    allowed_http_ports: frozenset[int] = Field(min_length=1)
    allowed_ssh_users: frozenset[str] = Field(min_length=1)

    @field_validator("expected_peer_id")
    @classmethod
    def validate_peer_id(cls, value: str) -> str:
        if not _PEER_ID.fullmatch(value):
            raise ValueError("expected Tailscale peer ID is invalid")
        return value

    @field_validator("expected_public_key")
    @classmethod
    def validate_public_key(cls, value: str) -> str:
        if not _PUBLIC_KEY.fullmatch(value):
            raise ValueError("expected Tailscale public key is invalid")
        return value

    @field_validator("magic_dns_name")
    @classmethod
    def validate_dns_name(cls, value: str) -> str:
        return _normalize_dns(value)

    @field_validator("allowed_ips")
    @classmethod
    def validate_allowed_ips(cls, values: frozenset[str]) -> frozenset[str]:
        try:
            normalized = frozenset(_tailscale_ip(value) for value in values)
        except ValueError:
            raise ValueError("allowed IP must be in a Tailscale range") from None
        if len(normalized) != len(values):
            raise ValueError("allowed Tailscale IPs must be unique")
        return normalized

    @field_validator("allowed_http_ports")
    @classmethod
    def validate_ports(cls, values: frozenset[int]) -> frozenset[int]:
        if any(isinstance(port, bool) or port < 1 or port > 65535 for port in values):
            raise ValueError("allowed HTTP port is invalid")
        return values

    @field_validator("allowed_ssh_users")
    @classmethod
    def validate_users(cls, values: frozenset[str]) -> frozenset[str]:
        if any(not _SSH_USER.fullmatch(user) for user in values):
            raise ValueError("allowed SSH user is invalid")
        return values


class TailscaleNodeSnapshot(DomainModel):
    node_id: str
    online: bool
    os: str
    peer_id: str = Field(exclude=True, repr=False)
    public_key: str = Field(exclude=True, repr=False)
    host_name: str = Field(exclude=True, repr=False)
    dns_name: str = Field(exclude=True, repr=False)
    tailscale_ips: frozenset[str] = Field(exclude=True, repr=False)


class TailscaleSnapshot(DomainModel):
    nodes: tuple[TailscaleNodeSnapshot, ...]
    observed_at: datetime

    @field_validator("observed_at")
    @classmethod
    def normalize_observed_at(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("Tailscale observation time must be timezone-aware")
        return value.astimezone(UTC)


class AuthorizedHttpEndpoint(DomainModel):
    node_id: str
    port: int
    url: str = Field(exclude=True, repr=False)
    host: str = Field(exclude=True, repr=False)


class AuthorizedSshTarget(DomainModel):
    node_id: str
    target: str = Field(exclude=True, repr=False)


class _Peer(DomainModel):
    peer_id: str = Field(exclude=True, repr=False)
    public_key: str = Field(exclude=True, repr=False)
    host_name: str = Field(exclude=True, repr=False)
    dns_name: str = Field(exclude=True, repr=False)
    tailscale_ips: frozenset[str] = Field(exclude=True, repr=False)
    online: bool
    os: str


class TailscaleAdapter:
    """Read-only status adapter and pure endpoint authorization boundary."""

    def __init__(
        self,
        *,
        policies: tuple[TailscaleNodePolicy, ...],
        tailscale_executable: Path,
        process_runner: ProcessRunner | None = None,
        snapshot_ttl_seconds: int = 30,
        monotonic_clock: Callable[[], float] | None = None,
        wall_clock: Callable[[], datetime] | None = None,
    ) -> None:
        snapshot_ttl = _validate_snapshot_ttl(snapshot_ttl_seconds)
        trusted_executable = _validate_trusted_executable(tailscale_executable)
        self._policies = policies
        self._trusted_executable = trusted_executable
        self._runner = process_runner or BoundedProcessRunner(
            TAILSCALE_STATUS_OUTPUT_LIMIT,
            env=TAILSCALE_PROCESS_ENV,
        )
        self._snapshot_ttl_seconds = snapshot_ttl
        self._monotonic_clock = monotonic_clock or time.monotonic
        self._wall_clock = wall_clock or (lambda: datetime.now(UTC))
        self._snapshot: TailscaleSnapshot | None = None
        self._snapshot_monotonic: float | None = None
        self._authorization_freshness = _AuthorizationFreshness.UNKNOWN

    async def snapshot(self) -> TailscaleSnapshot:
        self._snapshot = None
        self._snapshot_monotonic = None
        self._authorization_freshness = _AuthorizationFreshness.STALE
        self._validate_policy_conflicts()
        output = await self._status_output()
        document = _json_document(output.stdout)
        self_peer, peers = _parse_document(document)
        _validate_global_identity_uniqueness((self_peer, *peers))

        matches: dict[str, list[_Peer]] = {policy.node_id: [] for policy in self._policies}
        peer_match_counts: dict[int, int] = {index: 0 for index in range(len(peers))}
        drift = False
        for index, peer in enumerate(peers):
            for policy in self._policies:
                if _full_match(peer, policy):
                    matches[policy.node_id].append(peer)
                    peer_match_counts[index] += 1
                elif _partial_match(peer, policy):
                    drift = True
        if drift:
            raise TailscaleFailure(TailscaleErrorCode.IDENTITY_DRIFT)
        if any(len(owners) > 1 for owners in matches.values()) or any(
            count > 1 for count in peer_match_counts.values()
        ):
            raise TailscaleFailure(TailscaleErrorCode.IDENTITY_CONFLICT)

        nodes = tuple(
            _authorized_snapshot(policy.node_id, owners[0])
            for policy in self._policies
            if (owners := matches[policy.node_id])
        )
        observed_at = self._wall_clock()
        refresh_monotonic = self._monotonic_clock()
        if not math.isfinite(refresh_monotonic):
            raise TailscaleFailure(TailscaleErrorCode.PROCESS)
        snapshot = TailscaleSnapshot(nodes=nodes, observed_at=observed_at)
        self._snapshot = snapshot
        self._snapshot_monotonic = refresh_monotonic
        self._authorization_freshness = _AuthorizationFreshness.FRESH
        return snapshot

    async def _status_output(self) -> ProcessOutput:
        try:
            accepted = _validate_trusted_executable(self._trusted_executable.path)
            if accepted.fingerprint != self._trusted_executable.fingerprint:
                raise ValueError
            immediate = _validate_trusted_executable(self._trusted_executable.path)
            if immediate.fingerprint != accepted.fingerprint:
                raise ValueError
        except ValueError:
            raise TailscaleFailure(TailscaleErrorCode.SPAWN) from None
        argv = (str(immediate.path), *TAILSCALE_STATUS_ARGS)
        try:
            output = await self._runner(argv, TAILSCALE_STATUS_TIMEOUT)
        except asyncio.CancelledError:
            raise
        except TimeoutError:
            raise TailscaleFailure(TailscaleErrorCode.TIMEOUT) from None
        except (ProcessSpawnError, OSError):
            raise TailscaleFailure(TailscaleErrorCode.SPAWN) from None
        except ProcessOutputLimitError:
            raise TailscaleFailure(TailscaleErrorCode.OUTPUT_LIMIT) from None
        except Exception:
            raise TailscaleFailure(TailscaleErrorCode.PROCESS) from None
        if output.returncode != 0:
            raise TailscaleFailure(TailscaleErrorCode.STATUS_FAILED)
        return output

    def authorize_http(self, node_id: str, base_url: str) -> AuthorizedHttpEndpoint:
        policy, peer = self._authorization_context(node_id)
        try:
            parsed = urlsplit(base_url)
            port = parsed.port
            host = parsed.hostname
        except ValueError:
            raise TailscaleFailure(TailscaleErrorCode.ENDPOINT_NOT_ALLOWED) from None
        if (
            not base_url.isascii()
            or any(character.isspace() for character in base_url)
            or "?" in base_url
            or "#" in base_url
            or "%" in base_url
            or "\\" in base_url
            or parsed.scheme not in {"http", "https"}
            or not parsed.netloc
            or parsed.username is not None
            or parsed.password is not None
            or parsed.query
            or parsed.fragment
            or parsed.path not in {"", "/"}
            or host is None
        ):
            raise TailscaleFailure(TailscaleErrorCode.ENDPOINT_NOT_ALLOWED)
        if port is None:
            port = 80 if parsed.scheme == "http" else 443
        if port not in policy.allowed_http_ports:
            raise TailscaleFailure(TailscaleErrorCode.ENDPOINT_NOT_ALLOWED)
        canonical_host, is_v6 = _authorize_host(host, policy, peer)
        rendered_host = f"[{canonical_host}]" if is_v6 else canonical_host
        return AuthorizedHttpEndpoint(
            node_id=node_id,
            port=port,
            url=f"{parsed.scheme}://{rendered_host}:{port}/",
            host=canonical_host,
        )

    def authorize_ssh(self, node_id: str, target: str) -> AuthorizedSshTarget:
        policy, peer = self._authorization_context(node_id)
        if (
            not target.isascii()
            or any(character.isspace() for character in target)
            or target.startswith("-")
            or target.count("@") != 1
        ):
            raise TailscaleFailure(TailscaleErrorCode.ENDPOINT_NOT_ALLOWED)
        user, host = target.split("@", 1)
        if not _SSH_USER.fullmatch(user) or user not in policy.allowed_ssh_users or not host:
            raise TailscaleFailure(TailscaleErrorCode.ENDPOINT_NOT_ALLOWED)

        bracketed = host.startswith("[") and host.endswith("]")
        if bracketed:
            raw_host = host[1:-1]
            try:
                address = ipaddress.ip_address(raw_host)
            except ValueError:
                raise TailscaleFailure(TailscaleErrorCode.ENDPOINT_NOT_ALLOWED) from None
            if address.version != 6:
                raise TailscaleFailure(TailscaleErrorCode.ENDPOINT_NOT_ALLOWED)
        else:
            if "[" in host or "]" in host or ":" in host:
                raise TailscaleFailure(TailscaleErrorCode.ENDPOINT_NOT_ALLOWED)
            raw_host = host
        canonical_host, is_v6 = _authorize_host(raw_host, policy, peer)
        rendered_host = f"[{canonical_host}]" if is_v6 else canonical_host
        return AuthorizedSshTarget(node_id=node_id, target=f"{user}@{rendered_host}")

    def _authorization_context(
        self, node_id: str
    ) -> tuple[TailscaleNodePolicy, TailscaleNodeSnapshot]:
        snapshot = self._snapshot
        refresh_monotonic = self._snapshot_monotonic
        if self._authorization_freshness is _AuthorizationFreshness.UNKNOWN:
            raise TailscaleFailure(TailscaleErrorCode.UNKNOWN_NODE)
        if self._authorization_freshness is not _AuthorizationFreshness.FRESH:
            raise TailscaleFailure(TailscaleErrorCode.STALE)
        if snapshot is None or refresh_monotonic is None:
            self._authorization_freshness = _AuthorizationFreshness.STALE
            raise TailscaleFailure(TailscaleErrorCode.STALE)
        try:
            elapsed = self._monotonic_clock() - refresh_monotonic
        except Exception:
            self._authorization_freshness = _AuthorizationFreshness.STALE
            raise TailscaleFailure(TailscaleErrorCode.STALE) from None
        if not math.isfinite(elapsed) or elapsed < 0 or elapsed > self._snapshot_ttl_seconds:
            self._authorization_freshness = _AuthorizationFreshness.STALE
            raise TailscaleFailure(TailscaleErrorCode.STALE)
        policies = [policy for policy in self._policies if policy.node_id == node_id]
        nodes = [node for node in snapshot.nodes if node.node_id == node_id]
        if len(policies) != 1 or len(nodes) != 1:
            raise TailscaleFailure(TailscaleErrorCode.UNKNOWN_NODE)
        peer = nodes[0]
        if not peer.online:
            raise TailscaleFailure(TailscaleErrorCode.OFFLINE)
        return policies[0], peer

    def _validate_policy_conflicts(self) -> None:
        node_ids: set[str] = set()
        peer_ids: set[str] = set()
        public_keys: set[str] = set()
        dns_names: set[str] = set()
        ips: set[str] = set()
        for policy in self._policies:
            if (
                policy.node_id in node_ids
                or policy.expected_peer_id in peer_ids
                or policy.expected_public_key in public_keys
                or policy.magic_dns_name in dns_names
                or not ips.isdisjoint(policy.allowed_ips)
            ):
                raise TailscaleFailure(TailscaleErrorCode.IDENTITY_CONFLICT)
            node_ids.add(policy.node_id)
            peer_ids.add(policy.expected_peer_id)
            public_keys.add(policy.expected_public_key)
            dns_names.add(policy.magic_dns_name)
            ips.update(policy.allowed_ips)


def _json_document(value: str) -> Mapping[str, object]:
    try:
        parsed = cast(
            object,
            json.loads(
                value,
                object_pairs_hook=_reject_duplicate_keys,
                parse_constant=_reject_json_constant,
            ),
        )
    except _DuplicateJsonKey:
        raise TailscaleFailure(TailscaleErrorCode.INVALID_SNAPSHOT) from None
    except (json.JSONDecodeError, UnicodeDecodeError, _InvalidJsonConstant):
        raise TailscaleFailure(TailscaleErrorCode.INVALID_JSON) from None
    if not isinstance(parsed, dict):
        raise TailscaleFailure(TailscaleErrorCode.INVALID_SNAPSHOT)
    raw = cast(dict[object, object], parsed)
    if any(not isinstance(key, str) for key in raw):
        raise TailscaleFailure(TailscaleErrorCode.INVALID_SNAPSHOT)
    return cast(Mapping[str, object], parsed)


def _reject_duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    document: dict[str, object] = {}
    for key, item in pairs:
        if key in document:
            raise _DuplicateJsonKey
        document[key] = item
    return document


def _reject_json_constant(value: str) -> object:
    del value
    raise _InvalidJsonConstant


def _parse_document(document: Mapping[str, object]) -> tuple[_Peer, tuple[_Peer, ...]]:
    self_row = document.get("Self")
    peer_rows = document.get("Peer")
    if not isinstance(self_row, dict) or not isinstance(peer_rows, dict):
        raise TailscaleFailure(TailscaleErrorCode.INVALID_SNAPSHOT)
    self_peer = _parse_peer(cast(Mapping[object, object], self_row))
    peers: list[_Peer] = []
    for raw_key, raw_row in cast(Mapping[object, object], peer_rows).items():
        if not isinstance(raw_key, str) or not isinstance(raw_row, dict):
            raise TailscaleFailure(TailscaleErrorCode.INVALID_SNAPSHOT)
        peer = _parse_peer(cast(Mapping[object, object], raw_row))
        if raw_key != peer.public_key:
            raise TailscaleFailure(TailscaleErrorCode.INVALID_SNAPSHOT)
        peers.append(peer)
    return self_peer, tuple(peers)


def _parse_peer(row: Mapping[object, object]) -> _Peer:
    values = {str(key): value for key, value in row.items() if isinstance(key, str)}
    required = {"ID", "PublicKey", "HostName", "DNSName", "TailscaleIPs", "Online", "OS"}
    if not required.issubset(values):
        raise TailscaleFailure(TailscaleErrorCode.INVALID_SNAPSHOT)
    peer_id = values["ID"]
    public_key = values["PublicKey"]
    host_name = values["HostName"]
    dns_name = values["DNSName"]
    raw_ips = values["TailscaleIPs"]
    online = values["Online"]
    os_name = values["OS"]
    if (
        not isinstance(peer_id, str)
        or not _PEER_ID.fullmatch(peer_id)
        or not isinstance(public_key, str)
        or not _PUBLIC_KEY.fullmatch(public_key)
        or not isinstance(host_name, str)
        or not host_name
        or not isinstance(dns_name, str)
        or not isinstance(raw_ips, list)
        or not raw_ips
        or not isinstance(online, bool)
        or not isinstance(os_name, str)
        or not os_name
    ):
        raise TailscaleFailure(TailscaleErrorCode.INVALID_SNAPSHOT)
    try:
        normalized_dns = _normalize_dns(dns_name)
        ip_values = cast(list[object], raw_ips)
        ips = frozenset(_tailscale_ip(value) for value in ip_values if isinstance(value, str))
    except ValueError:
        raise TailscaleFailure(TailscaleErrorCode.INVALID_SNAPSHOT) from None
    if len(ips) != len(ip_values):
        raise TailscaleFailure(TailscaleErrorCode.INVALID_SNAPSHOT)
    return _Peer(
        peer_id=peer_id,
        public_key=public_key,
        host_name=host_name,
        dns_name=normalized_dns,
        tailscale_ips=ips,
        online=online,
        os=os_name,
    )


def _validate_global_identity_uniqueness(peers: tuple[_Peer, ...]) -> None:
    peer_ids: set[str] = set()
    public_keys: set[str] = set()
    dns_names: set[str] = set()
    ips: set[str] = set()
    for peer in peers:
        if (
            peer.peer_id in peer_ids
            or peer.public_key in public_keys
            or peer.dns_name in dns_names
            or not ips.isdisjoint(peer.tailscale_ips)
        ):
            raise TailscaleFailure(TailscaleErrorCode.IDENTITY_CONFLICT)
        peer_ids.add(peer.peer_id)
        public_keys.add(peer.public_key)
        dns_names.add(peer.dns_name)
        ips.update(peer.tailscale_ips)


def _full_match(peer: _Peer, policy: TailscaleNodePolicy) -> bool:
    return (
        peer.peer_id == policy.expected_peer_id
        and peer.public_key == policy.expected_public_key
        and peer.dns_name == policy.magic_dns_name
        and peer.tailscale_ips.issubset(policy.allowed_ips)
    )


def _partial_match(peer: _Peer, policy: TailscaleNodePolicy) -> bool:
    return (
        peer.peer_id == policy.expected_peer_id
        or peer.public_key == policy.expected_public_key
        or peer.dns_name == policy.magic_dns_name
        or not peer.tailscale_ips.isdisjoint(policy.allowed_ips)
    )


def _authorized_snapshot(node_id: str, peer: _Peer) -> TailscaleNodeSnapshot:
    return TailscaleNodeSnapshot(
        node_id=node_id,
        online=peer.online,
        os=peer.os,
        peer_id=peer.peer_id,
        public_key=peer.public_key,
        host_name=peer.host_name,
        dns_name=peer.dns_name,
        tailscale_ips=peer.tailscale_ips,
    )


def _authorize_host(
    host: str, policy: TailscaleNodePolicy, peer: TailscaleNodeSnapshot
) -> tuple[str, bool]:
    if host.lower() == "localhost":
        raise TailscaleFailure(TailscaleErrorCode.ENDPOINT_NOT_ALLOWED)
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        try:
            dns_name = _normalize_dns(host)
        except ValueError:
            raise TailscaleFailure(TailscaleErrorCode.ENDPOINT_NOT_ALLOWED) from None
        if dns_name != policy.magic_dns_name or dns_name != peer.dns_name:
            raise TailscaleFailure(TailscaleErrorCode.ENDPOINT_NOT_ALLOWED) from None
        return dns_name, False
    canonical_ip = str(address)
    if canonical_ip not in policy.allowed_ips or canonical_ip not in peer.tailscale_ips:
        raise TailscaleFailure(TailscaleErrorCode.ENDPOINT_NOT_ALLOWED)
    return canonical_ip, address.version == 6


def _normalize_dns(value: str) -> str:
    if not value.isascii() or not value or value.endswith(".."):
        raise ValueError("MagicDNS name is invalid")
    normalized = value[:-1] if value.endswith(".") else value
    normalized = normalized.lower()
    if (
        len(normalized) > 253
        or "." not in normalized
        or normalized == "localhost"
        or any(not _DNS_LABEL.fullmatch(label) for label in normalized.split("."))
    ):
        raise ValueError("MagicDNS name is invalid")
    return normalized


def _tailscale_ip(value: object) -> str:
    if not isinstance(value, str):
        raise ValueError("Tailscale IP is invalid")
    address = ipaddress.ip_address(value)
    if address not in _TAILSCALE_V4 and address not in _TAILSCALE_V6:
        raise ValueError("IP is outside Tailscale ranges")
    return str(address)


def _validate_trusted_executable(path: object) -> _TrustedExecutable:
    message = "trusted Tailscale executable is invalid"
    if not isinstance(path, Path) or not path.is_absolute():
        raise ValueError(message)
    fingerprints: list[_PathFingerprint] = []
    try:
        for candidate in (path.parent, *path.parent.parents):
            metadata = candidate.lstat()
            root_owned_sticky_directory = (
                metadata.st_uid == 0 and bool(metadata.st_mode & stat.S_ISVTX)
            )
            if (
                stat.S_ISLNK(metadata.st_mode)
                or not stat.S_ISDIR(metadata.st_mode)
                or metadata.st_uid not in {0, os.geteuid()}
                or (metadata.st_mode & 0o022 and not root_owned_sticky_directory)
            ):
                raise ValueError(message)
            fingerprints.append(_path_fingerprint(candidate, metadata))
        metadata = path.lstat()
    except OSError:
        raise ValueError(message) from None
    if (
        not stat.S_ISREG(metadata.st_mode)
        or metadata.st_uid not in {0, os.geteuid()}
        or metadata.st_mode & 0o022
        or not metadata.st_mode & 0o111
    ):
        raise ValueError(message)
    fingerprints.append(_path_fingerprint(path, metadata))
    try:
        resolved = path.resolve(strict=True)
    except OSError:
        raise ValueError(message) from None
    if resolved != path:
        raise ValueError(message)
    return _TrustedExecutable(path=resolved, fingerprint=tuple(fingerprints))


def _path_fingerprint(path: Path, metadata: os.stat_result) -> _PathFingerprint:
    return _PathFingerprint(
        path=str(path),
        device=metadata.st_dev,
        inode=metadata.st_ino,
        mode=metadata.st_mode,
        uid=metadata.st_uid,
    )


def _validate_snapshot_ttl(value: object) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 1 or value > 300:
        raise ValueError("snapshot TTL must be an integer from 1 to 300 seconds")
    return value
