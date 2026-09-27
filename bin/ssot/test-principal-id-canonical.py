#!/usr/bin/env python3
"""test-principal-id-canonical.py — unit tests for bin/ssot/_principal_id.

BET-Y2Q4-SH-7: covers the boundary cases the recorder (SH-5) and
canonicalizer (SH-5.1) must handle.  Includes explicit ``prefix``
detection so callers passing ``role:foo`` are not double-prefixed.

Usage:
    python3 bin/ssot/test-principal-id-canonical.py
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

_spec = importlib.util.spec_from_file_location(
    "_principal_id", str(HERE / "_principal_id.py"),
)
_pid = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(_pid)


CASES = [
    # (raw, expected, note)
    ("xiamingxing", "principal:xiamingxing", "bare id → prefixed"),
    ("principal:xiamingxing", "principal:xiamingxing", "already prefixed → preserved"),
    ("PRINCIPAL:xiamingxing", "PRINCIPAL:xiamingxing", "case-sensitive prefix is preserved (sovereignty uses lowercase)"),
    ("role:foo", "role:foo", "non-principal prefix → preserved as-is"),
    ("responsibility:bar", "responsibility:bar", "another kind prefix → preserved"),
    ("", "", "empty string → empty string"),
    ("   ", "", "whitespace-only → empty string"),
    (None, "", "None → empty string"),
    ("x", "principal:x", "single-char bare → prefixed"),
    ("xiamingxing\n", "principal:xiamingxing", "trailing whitespace stripped then prefixed"),
]


def test_canonical_principal_id() -> tuple[bool, str]:
    """All canonical_principal_id cases."""
    failed = []
    for raw, expected, note in CASES:
        got = _pid.canonical_principal_id(raw)
        if got != expected:
            failed.append(f"  {note!r}: raw={raw!r} expected={expected!r} got={got!r}")
    if failed:
        return False, f"{len(failed)}/{len(CASES)} cases failed:\n" + "\n".join(failed)
    return True, f"{len(CASES)}/{len(CASES)} cases passed"


def test_principal_id_from_env_default() -> tuple[bool, str]:
    """Empty env falls back to canonical 'principal:xiamingxing'."""
    got = _pid.principal_id_from_env(env={})
    return (got == "principal:xiamingxing", f"got={got!r}")


def test_principal_id_from_env_passthrough() -> tuple[bool, str]:
    """Prefixed values are preserved."""
    got = _pid.principal_id_from_env(env={"OMO_PRINCIPAL_ID": "principal:alice"})
    return (got == "principal:alice", f"got={got!r}")


def test_principal_id_from_env_bare() -> tuple[bool, str]:
    """Bare values get canonical prefix."""
    got = _pid.principal_id_from_env(env={"OMO_PRINCIPAL_ID": "bob"})
    return (got == "principal:bob", f"got={got!r}")


def main() -> int:
    tests = [
        ("canonical-id-cases", test_canonical_principal_id),
        ("from-env-default", test_principal_id_from_env_default),
        ("from-env-passthrough", test_principal_id_from_env_passthrough),
        ("from-env-bare", test_principal_id_from_env_bare),
    ]
    passed = 0
    failed = 0
    for name, fn in tests:
        try:
            ok, info = fn()
        except Exception as exc:
            ok, info = False, f"exception: {type(exc).__name__}: {exc}"
        marker = "PASS" if ok else "FAIL"
        print(f"  [{marker}] {name}: {info}")
        if ok:
            passed += 1
        else:
            failed += 1
    print(f"\n=== principal-id-canonical test: {passed}/{passed + failed} passed ===")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())