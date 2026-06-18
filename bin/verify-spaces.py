#!/usr/bin/env python3
import json
import os
import sys
import yaml
try:
    import jsonschema
except ImportError:
    print("jsonschema not found. Please run: uv pip install jsonschema")
    sys.exit(1)

def load_yaml(path):
    with open(path, "r") as f:
        return yaml.safe_load(f)

def validate_files(schema_path, file_pattern):
    print(f"Validating {file_pattern} against {schema_path}...")
    schema = load_yaml(schema_path)
    import glob
    files = glob.glob(file_pattern)
    errors = 0
    for f in files:
        if "schema" in f:
            continue
        data = load_yaml(f)
        if not data:
            continue
        try:
            jsonschema.validate(instance=data, schema=schema)
            print(f"  ✓ {f} is valid")
        except jsonschema.exceptions.ValidationError as e:
            print(f"  ✗ {f} is invalid: {e.message}")
            errors += 1
    return errors

def main():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    os.chdir(root)
    
    total_errors = 0
    total_errors += validate_files("spaces/_schema/json/space-manifest.schema.json", "spaces/*-space.yaml")
    total_errors += validate_files("spaces/_schema/json/space-identity-admission.schema.json", "spaces/*-identity-admission.yaml")
    
    if total_errors > 0:
        print(f"\n❌ {total_errors} validation errors found.")
        sys.exit(1)
    else:
        print("\n✅ All spaces configurations passed schema validation.")

if __name__ == "__main__":
    main()
