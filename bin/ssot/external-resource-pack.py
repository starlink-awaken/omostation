#!/usr/bin/env python3
"""Validate an external-resource extension pack without loading its provider.

The checker is a static boundary for third-party and future connector packs. It
reads a manifest, reuses Agora's credential-free descriptor parser, and emits a
safe preview. It never installs packages, imports entry points, probes health,
calls a provider, writes OMO state, or activates a resource.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any

SCHEMA = "external-resource-pack/v1"
DESCRIPTOR_SCHEMA = "external-resource/v1"
ENTRY_POINT_GROUP = "external.resources"
PROVIDER_METHOD = "external_descriptor"
HEALTH_PROBE_METHOD = "health_probe"
_SECRET_KEYS = {
    "access_token",
    "authorization",
    "cookie",
    "dsn",
    "password",
    "private_key",
    "refresh_token",
    "secret",
    "token",
}
_RAW_CONTENT_KEYS = {
    "content",
    "input_data",
    "output_data",
    "raw_content",
    "raw_input",
    "raw_output",
    "sample_data",
}


class ExternalResourcePackError(ValueError):
    """Raised when a pack cannot be safely checked."""


def _reject_forbidden(value: Any, path: str = "pack") -> None:
    if isinstance(value, Mapping):
        for key, nested in value.items():
            key_text = str(key).lower()
            if key_text in _SECRET_KEYS:
                raise ExternalResourcePackError(
                    f"secret field is forbidden: {path}.{key}"
                )
            if key_text in _RAW_CONTENT_KEYS:
                raise ExternalResourcePackError(
                    f"raw content field is forbidden: {path}.{key}"
                )
            _reject_forbidden(nested, f"{path}.{key}")
    elif isinstance(value, list):
        for index, nested in enumerate(value):
            _reject_forbidden(nested, f"{path}[{index}]")


def _text(value: Any, field_name: str) -> str:
    result = str(value or "").strip()
    if not result:
        raise ExternalResourcePackError(f"missing required field: {field_name}")
    return result


def _load_agora_descriptor_parser(root: Path):
    module_path = root / "projects/agora/src/agora/external_connections.py"
    if not module_path.exists():
        raise ExternalResourcePackError(
            f"Agora external connection boundary is unavailable: {module_path}"
        )
    spec = importlib.util.spec_from_file_location(
        "agora_external_connection_pack_parser", module_path
    )
    if spec is None or spec.loader is None:
        raise ExternalResourcePackError("cannot load Agora descriptor parser")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module.ExternalResourceDescriptor, module.RESOURCE_KINDS


def _load_resource_kinds(root: Path) -> dict[str, set[str]]:
    """Read capability ownership from the external fabric registry SSOT."""
    registry_path = root / ".omo/_truth/registry/external-connection-fabric.yaml"
    try:
        import yaml
    except ImportError as exc:
        raise ExternalResourcePackError("PyYAML is required to read the fabric registry") from exc
    try:
        documents = list(yaml.safe_load_all(registry_path.read_text(encoding="utf-8")))
    except (OSError, yaml.YAMLError) as exc:
        raise ExternalResourcePackError(
            f"cannot read external fabric registry: {registry_path}"
        ) from exc
    for document in documents:
        if isinstance(document, Mapping) and isinstance(
            document.get("resource_kinds"), Mapping
        ):
            return {
                str(kind): set(details.get("allowed_capabilities", []))
                for kind, details in document["resource_kinds"].items()
                if isinstance(details, Mapping)
            }
    raise ExternalResourcePackError("external fabric registry has no resource_kinds")


def _safe_descriptor(parsed: Any) -> dict[str, Any]:
    """Keep the preview to descriptor fields; pack metadata never escapes."""
    return {
        "id": parsed.id,
        "kind": parsed.kind,
        "provider": parsed.provider,
        "protocol": parsed.protocol,
        "capabilities": list(parsed.capabilities),
        "data_classification": parsed.data_classification,
        "provenance": dict(parsed.provenance),
        "lifecycle": parsed.lifecycle,
        "health": dict(parsed.health),
        "owner": parsed.owner,
        "version": parsed.version,
        "permission_ref": parsed.permission_ref,
        "mode": parsed.mode,
        "expires_at": parsed.expires_at,
        "review_at": parsed.review_at,
        "rollback_plan": bool(parsed.rollback_plan),
    }


def check_external_resource_pack(root: Path, pack: Mapping[str, Any]) -> dict[str, Any]:
    """Return a deterministic, activation-forbidden conformance projection."""
    if not isinstance(pack, Mapping):
        raise ExternalResourcePackError("pack must be an object")
    _reject_forbidden(pack)
    reasons: list[str] = []

    if pack.get("schema") != SCHEMA:
        reasons.append("pack_schema_mismatch")
    pack_id = str(pack.get("pack_id") or "").strip()
    pack_version = str(pack.get("pack_version") or "").strip()
    if not pack_id:
        reasons.append("missing_pack_id")
    if not pack_version:
        reasons.append("missing_pack_version")

    extension = pack.get("extension")
    if not isinstance(extension, Mapping):
        extension = {}
        reasons.append("missing_extension_contract")
    if extension.get("entry_point_group") != ENTRY_POINT_GROUP:
        reasons.append("entry_point_group_must_be_external_resources")
    if not str(extension.get("entry_point") or "").strip():
        reasons.append("missing_entry_point")
    if extension.get("provider_method") != PROVIDER_METHOD:
        reasons.append("provider_method_must_be_external_descriptor")
    health_probe = extension.get("health_probe")
    if not isinstance(health_probe, Mapping):
        reasons.append("missing_health_probe_contract")
    else:
        if health_probe.get("method") != HEALTH_PROBE_METHOD:
            reasons.append("health_probe_method_must_be_health_probe")
        if health_probe.get("side_effect") != "read_only":
            reasons.append("health_probe_must_be_read_only")
        if health_probe.get("required") is not True:
            reasons.append("health_probe_must_be_required")

    descriptor = pack.get("descriptor")
    parsed = None
    safe_descriptor: dict[str, Any] | None = None
    if not isinstance(descriptor, Mapping):
        reasons.append("missing_descriptor")
    else:
        if descriptor.get("protocol") != DESCRIPTOR_SCHEMA:
            reasons.append("descriptor_schema_mismatch")
        try:
            descriptor_type, resource_kinds = _load_agora_descriptor_parser(root)
            parsed = descriptor_type.from_mapping(descriptor)
            safe_descriptor = _safe_descriptor(parsed)
            if not parsed.permission_ref:
                reasons.append("missing_permission_ref")
            if not parsed.rollback_plan:
                reasons.append("missing_rollback_plan")
            if parsed.lifecycle not in {"discovered", "sandbox"}:
                reasons.append("lifecycle_must_start_discovered_or_sandbox")
            allowed = _load_resource_kinds(root).get(parsed.kind, set())
            if not set(parsed.capabilities).issubset(allowed):
                reasons.append("capability_not_allowed_for_kind")
            if parsed.kind not in resource_kinds:
                reasons.append("unknown_resource_kind")
        except (ExternalResourcePackError, ValueError):
            reasons.append("descriptor_invalid")

    if pack.get("activation") not in (None, "forbidden"):
        reasons.append("activation_must_be_forbidden")

    status = "blocked"
    if not reasons and parsed is not None:
        status = "proposal_only" if parsed.mode == "proposal_only" else "ready_for_catalog_preview"
    return {
        "schema": "external-resource-pack-check/v1",
        "mode": "read_only_conformance",
        "activation": "forbidden",
        "status": status,
        "reason_codes": sorted(set(reasons)),
        "pack": {
            "pack_id": pack_id or None,
            "pack_version": pack_version or None,
            "provider": str(pack.get("provider") or "").strip() or None,
        },
        "descriptor": safe_descriptor,
        "extension": {
            "entry_point_group": extension.get("entry_point_group"),
            "entry_point": str(extension.get("entry_point") or "").strip() or None,
            "provider_method": extension.get("provider_method"),
            "health_probe": {
                "method": health_probe.get("method") if isinstance(health_probe, Mapping) else None,
                "side_effect": health_probe.get("side_effect") if isinstance(health_probe, Mapping) else None,
                "required": health_probe.get("required") if isinstance(health_probe, Mapping) else None,
            },
        },
        "execution_policy": {
            "install": "forbidden",
            "provider_import": "forbidden",
            "health_probe": "forbidden",
            "omo_write": "forbidden",
            "business_invoke": "forbidden",
        },
    }


def _read_pack(path: Path | None) -> Mapping[str, Any]:
    text = sys.stdin.read() if path is None else path.read_text(encoding="utf-8")
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        try:
            import yaml
        except ImportError as exc:
            raise ExternalResourcePackError("input must be valid JSON or YAML") from exc
        try:
            payload = yaml.safe_load(text)
        except yaml.YAMLError as exc:
            raise ExternalResourcePackError("input must be valid JSON or YAML") from exc
    if not isinstance(payload, Mapping):
        raise ExternalResourcePackError("input must contain one pack object")
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--input", type=Path, help="JSON/YAML pack manifest; stdin when omitted")
    args = parser.parse_args(argv)
    try:
        payload = check_external_resource_pack(args.root.resolve(), _read_pack(args.input))
    except (ExternalResourcePackError, OSError, ValueError) as exc:
        print(f"external-resource-pack: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
