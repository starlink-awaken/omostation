#!/usr/bin/env python3
"""YAML syntax validator for ci-local-fast.

Validates all .github/workflows/*.yml and protocols/*.yaml files.
Exits 1 on any parse error.
"""
from __future__ import annotations

import glob
import sys

import yaml


def main() -> int:
    patterns = [
        ".github/workflows/*.yml",
        ".github/workflows/*.yaml",
        "protocols/*.yaml",
        "protocols/*.yml",
    ]
    files: list[str] = []
    for pat in patterns:
        files.extend(sorted(glob.glob(pat)))

    if not files:
        print("  no YAML files found")
        return 0

    ok = 0
    fail = 0
    for f in files:
        try:
            with open(f, encoding="utf-8") as fh:
                yaml.safe_load(fh)
            ok += 1
        except yaml.YAMLError as e:
            print(f"  FAIL {f}: {e}")
            fail += 1
        except OSError as e:
            print(f"  FAIL {f}: {e}")
            fail += 1

    print(f"  {ok} valid, {fail} invalid ({len(files)} total)")
    return 1 if fail else 0


if __name__ == "__main__":
    sys.exit(main())
