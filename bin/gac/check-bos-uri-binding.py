#!/usr/bin/env python3
"""Check BOS URI bidirectional binding between registry and implementation."""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

_PATTERNS = [
    r"bos://[a-zA-Z0-9_./-]+(?:/[a-zA-Z0-9_.-]+)*",
    r"bos://[a-z][a-z0-9_-]+(?:/[a-z0-9_-]+){1,3}/?(?![a-z0-9_/-])",
]


def _extract_uris(text: str) -> set[str]:
    uris = set()
    for pattern in _PATTERNS:
        for match in re.finditer(pattern, text):
            candidate = match.group(0)
            suffix = candidate[len("bos://"):]
            if "/" not in suffix:
                continue
            if any(ch in candidate for ch in ("[", "]", "(", ")", "{", "}", "|")):
                continue
            uris.add(candidate)
    return uris


def find_registered_uris() -> set[str]:
    registered = set()
    for path in REPO.rglob("*.yaml"):
        if "_registry" not in str(path) and "_truth" not in str(path):
            continue
        if any(part in ("tests", "test", "__pycache__") for part in path.relative_to(REPO).parts):
            continue
        try:
            text = path.read_text(encoding="utf-8")
            registered.update(_extract_uris(text))
        except Exception:
            continue
    return registered


def find_implemented_uris() -> set[str]:
    implemented = set()
    for path in REPO.rglob("*.py"):
        if any(part in ("tests", "test", "__pycache__") for part in path.relative_to(REPO).parts):
            continue
        try:
            text = path.read_text(encoding="utf-8")
            implemented.update(_extract_uris(text))
        except Exception:
            continue
    return implemented


def main() -> int:
    registered = find_registered_uris()
    implemented = find_implemented_uris()

    only_registered = registered - implemented
    only_implemented = implemented - registered

    if only_registered:
        print(f"WARN: {len(only_registered)} BOS URIs registered but not implemented")
        for uri in sorted(only_registered)[:10]:
            print(f"  - {uri}")
        if len(only_registered) > 10:
            print(f"  ... and {len(only_registered) - 10} more")

    if only_implemented:
        print(f"WARN: {len(only_implemented)} BOS URIs implemented but not registered")
        for uri in sorted(only_implemented)[:10]:
            print(f"  - {uri}")
        if len(only_implemented) > 10:
            print(f"  ... and {len(only_implemented) - 10} more")

    if not only_registered and not only_implemented:
        print(f"PASS: {len(registered)} BOS URIs are bidirectionally bound")
    else:
        print(f"INFO: BOS URI binding check is currently in warning mode during transition")

    return 0


if __name__ == "__main__":
    sys.exit(main())
