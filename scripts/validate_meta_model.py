#!/usr/bin/env python3
"""
ecOS Meta-Model Validator — Validate L0-registry.yaml against ecos-meta-model.yaml constraints.

Validates:
1. All protocols have a valid usage field (active|partial|planned|legacy)
2. All protocols have a transport field
3. No duplicate protocol names

Usage:
    uv run python3 scripts/validate_meta_model.py
"""

import sys
from pathlib import Path

import yaml

SCRIPT_DIR = Path(__file__).resolve().parent
PROTOCOLS_DIR = SCRIPT_DIR.parent / "protocols"

L0_REGISTRY_PATH = PROTOCOLS_DIR / "L0-registry.yaml"
META_MODEL_PATH = PROTOCOLS_DIR / "ecos-meta-model.yaml"

VALID_USAGES = {"active", "partial", "planned", "legacy"}


def load_yaml(path: Path) -> dict:
    if not path.exists():
        print(f"ERROR: File not found: {path}")
        sys.exit(1)
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not data:
        print(f"ERROR: Empty or invalid YAML: {path}")
        sys.exit(1)
    return data


def validate_usage(protocol: dict, errors: list[str]) -> None:
    """Check that protocol has a valid usage field."""
    usage = protocol.get("usage")
    if not usage:
        errors.append(
            f"  [{protocol['name']}] Missing 'usage' field "
            f"(required: one of {sorted(VALID_USAGES)})"
        )
    elif usage not in VALID_USAGES:
        errors.append(
            f"  [{protocol['name']}] Invalid usage '{usage}' — "
            f"must be one of {sorted(VALID_USAGES)}"
        )


def validate_transport(protocol: dict, errors: list[str]) -> None:
    """Check that protocol has a transport field."""
    transport = protocol.get("transport")
    if transport is None:
        errors.append(f"  [{protocol['name']}] Missing 'transport' field")
    elif isinstance(transport, list) and len(transport) == 0:
        errors.append(
            f"  [{protocol['name']}] 'transport' is empty list — "
            f"should specify at least one transport mechanism"
        )


def validate_no_duplicates(protocols: list[dict], errors: list[str]) -> None:
    """Check for duplicate protocol names."""
    seen: dict[str, list[int]] = {}
    for i, proto in enumerate(protocols):
        name = proto.get("name")
        if not name:
            errors.append(f"  [index {i}] Protocol missing 'name' field")
            continue
        if name in seen:
            seen[name].append(i)
        else:
            seen[name] = [i]

    for name, indices in seen.items():
        if len(indices) > 1:
            positions = ", ".join(f"index {i}" for i in indices)
            errors.append(f"  [{name}] Duplicate protocol name at {positions}")


def main() -> int:
    print("=" * 60)
    print("ecOS Meta-Model Validator")
    print("=" * 60)
    print()

    # Load meta-model reference
    print(f"1. Loading meta-model: {META_MODEL_PATH}")
    meta_model = load_yaml(META_MODEL_PATH)
    constraints = []
    for layer in meta_model.get("layers", []):
        for c in layer.get("constraints", []):
            constraints.append(c)
    print(f"   Found {len(constraints)} meta-model constraints")
    print()

    # Load L0 registry
    print(f"2. Loading L0 registry: {L0_REGISTRY_PATH}")
    registry = load_yaml(L0_REGISTRY_PATH)
    protocols = registry.get("protocols", [])
    print(f"   Found {len(protocols)} protocols in L0-registry.yaml")
    print()

    # Validate
    print("3. Running validations...")
    print()
    errors: list[str] = []

    # 3a. Valid usage field
    print("   3a. Checking usage field (active|partial|planned|legacy)...")
    for proto in protocols:
        validate_usage(proto, errors)

    # 3b. Transport field
    print("   3b. Checking transport field...")
    for proto in protocols:
        validate_transport(proto, errors)

    # 3c. No duplicate names
    print("   3c. Checking for duplicate protocol names...")
    validate_no_duplicates(protocols, errors)

    # Summary
    print()
    if errors:
        print(f"❌ FAILED — {len(errors)} validation error(s) found:")
        print()
        for err in errors:
            print(err)
        return 1
    else:
        print("✅ ALL CHECKS PASSED")
        print(f"   - {len(protocols)} protocols validated")
        print("   - All have valid usage fields")
        print("   - All have transport fields")
        print("   - No duplicate names")
        print()
        print("Protocol summary:")
        print(f"   {'Name':<22} {'Usage':<10} {'Transport':<25}")
        print(f"   {'─' * 22} {'─' * 10} {'─' * 25}")
        for proto in protocols:
            name = proto.get("name", "?")
            usage = proto.get("usage", "?")
            transport = ", ".join(proto.get("transport", [])) or "?"
            print(f"   {name:<22} {usage:<10} {transport:<25}")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
