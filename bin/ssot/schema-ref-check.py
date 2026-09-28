#!/usr/bin/env python3
"""Schema Reference Integrity Checker — verify all schema references are valid.

Usage:
    python bin/ssot/schema-ref-check.py --registry .omo/standards/content-schemas/index.yaml
"""
import argparse
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    print("PyYAML required: uv run --with pyyaml python bin/ssot/schema-ref-check.py")
    sys.exit(1)


def load_registry(registry_path: str) -> dict:
    """Load schema registry index."""
    with open(registry_path) as f:
        return yaml.safe_load(f)


def check_schema_exists(schema: dict, base_path: Path) -> bool:
    """Check if schema file/directory exists."""
    schema_path = base_path / schema["path"]
    return schema_path.exists()


def check_source_exists(schema: dict, base_path: Path) -> bool:
    """Check if source file/directory exists."""
    source = schema.get("source", "")
    if not source:
        return True  # No source to check
    source_path = Path(source)
    return source_path.exists()


def main():
    parser = argparse.ArgumentParser(description="Schema Reference Integrity Checker")
    parser.add_argument("--registry", default=".omo/standards/content-schemas/index.yaml",
                        help="Path to schema registry index")
    args = parser.parse_args()

    registry = load_registry(args.registry)
    schemas = registry.get("schemas", [])
    base_path = Path(args.registry).parent

    print(f"Loaded {len(schemas)} schemas from {args.registry}")

    violations = []
    for schema in schemas:
        schema_id = schema.get("id", "unknown")

        if schema.get("reference_only"):
            # Registered by reference — no local schema file expected
            if check_source_exists(schema, base_path):
                print(f"  ✅ {schema_id}: OK (reference_only)")
            else:
                violations.append(f"  ⚠️  {schema_id}: source not found: {schema.get('source', '')}")
        elif not check_schema_exists(schema, base_path):
            violations.append(f"  ❌ {schema_id}: registry path not found: {schema['path']}")
        elif not check_source_exists(schema, base_path):
            violations.append(f"  ⚠️  {schema_id}: source not found: {schema.get('source', '')}")
        else:
            print(f"  ✅ {schema_id}: OK")

    if violations:
        print(f"\n❌ {len(violations)} violations found:")
        for v in violations:
            print(v)
        sys.exit(1)
    else:
        print(f"\n✅ All {len(schemas)} schemas passed reference integrity check")


if __name__ == "__main__":
    main()
