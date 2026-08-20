#!/usr/bin/env python3
"""Compatibility CLI for the canonical capability registry.

The sole registry writer is ``bin/cockpit/gen-capability-registry.py``.  This
module delegates sync/check to that writer and provides read-only discovery.
Discovery never invokes a capability: it emits a privacy-safe resolution
receipt that requires a native adapter and an admission decision.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

try:
    import yaml
except ImportError:  # pragma: no cover - exercised by the CLI environment
    yaml = None


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REGISTRY = ROOT / "docs" / "generated" / "capability-registry.yaml"
CANONICAL_GENERATOR = ROOT / "bin" / "cockpit" / "gen-capability-registry.py"
SUPPORTED_SCHEMA_MAJOR = 1


class RegistryError(ValueError):
    """The registry is missing, malformed, or uses an unsupported schema."""


@dataclass(frozen=True)
class Resolution:
    """Fail-closed resolution result; never an invocation authorization."""

    status: str
    capability: Optional[dict[str, Any]]  # noqa: UP045 -- Python 3.9 contract
    candidate_ids: tuple[str, ...]
    match_count: int


def load_registry(path: Path) -> dict[str, Any]:
    """Load canonical v1 and pre-metadata v1 registries."""
    if yaml is None:
        raise RegistryError("pyyaml_not_installed")
    if not path.is_file():
        raise RegistryError("registry_not_found")
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, yaml.YAMLError) as exc:
        raise RegistryError("registry_unreadable") from exc
    if not isinstance(data, dict):
        raise RegistryError("registry_not_mapping")

    version = str(data.get("version") or "1.0.0")
    try:
        major = int(version.split(".", 1)[0])
    except (TypeError, ValueError) as exc:
        raise RegistryError("registry_version_invalid") from exc
    if major != SUPPORTED_SCHEMA_MAJOR:
        raise RegistryError("registry_schema_unsupported")

    canonical_shape = all(key in data for key in ("mcp_servers", "bos_services", "cli_commands"))
    legacy_shape = isinstance(data.get("capabilities"), list)
    if not canonical_shape and not legacy_shape:
        raise RegistryError("registry_shape_unsupported")
    return data


def _add(
    index: dict[str, list[dict[str, Any]]],
    capability_id: str,
    kind: str,
    name: str,
    description: str,
    adapter_kind: str,
    target: str,
) -> None:
    if not capability_id:
        return
    index.setdefault(capability_id, []).append(
        {
            "id": capability_id,
            "kind": kind,
            "name": name,
            "description": description,
            "adapter": {"kind": adapter_kind, "target": target},
        }
    )


def build_capability_index(registry: Mapping[str, Any]) -> dict[str, list[dict[str, Any]]]:
    """Project the registry into stable, exact discovery IDs."""
    index: dict[str, list[dict[str, Any]]] = {}

    for raw_server in registry.get("mcp_servers", []) or []:
        if not isinstance(raw_server, dict):
            continue
        server_id = str(raw_server.get("id") or "")
        server_name = str(raw_server.get("name") or server_id)
        _add(
            index,
            "mcp-server:" + server_id,
            "mcp_server",
            server_name,
            server_name,
            "mcp_native",
            server_id,
        )
        for raw_tool in raw_server.get("tools", []) or []:
            tool = str(raw_tool)
            _add(
                index,
                "mcp-tool:" + server_id + ":" + tool,
                "mcp_tool",
                tool,
                server_name + " " + tool,
                "mcp_native",
                server_id + "/" + tool,
            )

    bos = registry.get("bos_services") or {}
    domains = bos.get("domains") if isinstance(bos, dict) else {}
    if isinstance(domains, dict):
        for services in domains.values():
            if not isinstance(services, list):
                continue
            for raw_service in services:
                if not isinstance(raw_service, dict):
                    continue
                uri = str(raw_service.get("uri") or "")
                _add(
                    index,
                    "bos-service:" + uri,
                    "bos_service",
                    uri,
                    str(raw_service.get("description") or ""),
                    "bos_native",
                    uri,
                )

    for raw_command in registry.get("cli_commands", []) or []:
        if not isinstance(raw_command, dict):
            continue
        name = str(raw_command.get("name") or "")
        _add(
            index,
            "cli-command:" + name,
            "cli_command",
            name,
            str(raw_command.get("description") or ""),
            "cockpit_native",
            name,
        )

    # Legacy flat registries remain discoverable but their stored invoke strings
    # are deliberately ignored.  They cannot regain a direct execution path.
    for raw_capability in registry.get("capabilities", []) or []:
        if not isinstance(raw_capability, dict):
            continue
        capability_id = str(raw_capability.get("id") or "")
        _add(
            index,
            capability_id,
            "legacy_capability",
            str(raw_capability.get("name") or capability_id),
            str(raw_capability.get("description") or ""),
            "legacy_discovery_only",
            capability_id,
        )

    return index


def resolve_capability(
    registry: Mapping[str, Any],
    capability_id: Optional[str] = None,  # noqa: UP045 -- Python 3.9 contract
    query: Optional[str] = None,  # noqa: UP045 -- Python 3.9 contract
) -> Resolution:
    """Resolve exactly one capability or reject ambiguity/not-found."""
    if bool(capability_id) == bool(query):
        return Resolution("invalid_selector", None, (), 0)

    index = build_capability_index(registry)
    if capability_id:
        matches = list(index.get(capability_id, []))
    else:
        needle = str(query).casefold()
        matches = []
        for entries in index.values():
            for entry in entries:
                haystack = " ".join(
                    (str(entry["id"]), str(entry["name"]), str(entry["description"]))
                ).casefold()
                if needle in haystack:
                    matches.append(entry)

    candidate_ids = tuple(sorted({str(entry["id"]) for entry in matches}))
    if not matches:
        return Resolution("not_found", None, (), 0)
    if len(matches) != 1:
        return Resolution("ambiguous", None, candidate_ids, len(matches))
    return Resolution("resolved", matches[0], candidate_ids, 1)


def _digest(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def build_resolution_receipt(
    result: Resolution,
    registry_content: bytes,
    selector: Mapping[str, Any],
) -> dict[str, Any]:
    """Build a redacted, resolution-only receipt with no execution grant."""
    selector_bytes = json.dumps(selector, sort_keys=True, separators=(",", ":")).encode("utf-8")
    receipt: dict[str, Any] = {
        "schema": "capability-resolution-receipt/v1",
        "status": result.status,
        "registry_digest": _digest(registry_content),
        "selector_digest": _digest(selector_bytes),
        "match_count": result.match_count,
        "candidate_id_digests": [_digest(value.encode("utf-8")) for value in result.candidate_ids],
        "admission": {"required": True, "decision": "not_evaluated"},
        "invocation": {
            "allowed": False,
            "route": "native_adapter_only",
            "reason": "admission_not_evaluated",
        },
    }
    if result.capability is not None:
        receipt["capability_id"] = result.capability["id"]
        receipt["adapter"] = dict(result.capability["adapter"])
    return receipt


def _delegate_to_writer(action: str, registry_path: Path) -> int:
    command = [sys.executable, str(CANONICAL_GENERATOR), "--quiet", "--output", str(registry_path)]
    if action == "check":
        command.append("--check")
    return subprocess.run(command, check=False).returncode


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Capability registry compatibility and discovery CLI")
    commands = parser.add_subparsers(dest="command", required=True)

    sync_parser = commands.add_parser("sync", help="delegate generation to the canonical writer")
    sync_parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)

    check_parser = commands.add_parser("check", help="delegate read-only drift check")
    check_parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)

    find_parser = commands.add_parser("find", help="resolve one capability without invoking it")
    selector = find_parser.add_mutually_exclusive_group(required=True)
    selector.add_argument("--id", dest="capability_id", help="exact capability ID")
    selector.add_argument("--query", help="compatibility search; ambiguity is rejected")
    find_parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:  # noqa: UP045 -- Python 3.9 contract
    args = _parser().parse_args(argv)
    if args.command in {"sync", "check"}:
        return _delegate_to_writer(args.command, args.registry)

    selector: dict[str, Any] = {}
    if args.capability_id:
        selector["capability_id"] = args.capability_id
    else:
        selector["query"] = args.query

    try:
        content = args.registry.read_bytes()
        registry = load_registry(args.registry)
        result = resolve_capability(registry, **selector)
    except (OSError, RegistryError):
        content = b""
        result = Resolution("invalid_registry", None, (), 0)

    receipt = build_resolution_receipt(result, content, selector)
    print(json.dumps(receipt, ensure_ascii=False, sort_keys=True))
    return {
        "resolved": 0,
        "not_found": 2,
        "ambiguous": 3,
        "invalid_selector": 4,
        "invalid_registry": 4,
    }[result.status]


if __name__ == "__main__":
    sys.exit(main())
