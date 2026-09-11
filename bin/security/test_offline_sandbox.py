#!/usr/bin/env python3
"""Offline sandbox test for the Local Secure Vault (BET-Y1Q4-T10-05, batch 1).

Run from the workspace root with ``bin`` on the import path::

    PYTHONPATH=bin uv run python -m security.test_offline_sandbox

NOTE: ledger verify currently spells this as
``security.vault.test_offline_sandbox``; ``vault`` is a module file
(``bin/security/vault.py`` per write_surfaces), so the runnable spelling is
``security.test_offline_sandbox``. Batch 2 either repackages ``vault/`` or
amends the ledger verify command to this spelling.
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

from security.vault import AuthError, LocalSecureVault, VaultLocked

SECRET = b"offline-signing-key-batch1"
PASSPHRASE = "test-passphrase"


def test_roundtrip(tmp: Path) -> None:
    v = LocalSecureVault(tmp / "v.sealed", max_failed=5)
    v.seal(SECRET, PASSPHRASE)
    assert v.reveal(PASSPHRASE) == SECRET


def test_zero_plaintext_on_disk(tmp: Path) -> None:
    store = tmp / "v.sealed"
    LocalSecureVault(store, max_failed=5).seal(SECRET, PASSPHRASE)
    raw = store.read_bytes()
    assert SECRET not in raw
    assert PASSPHRASE.encode() not in raw


def test_wrong_passphrase_rejected(tmp: Path) -> None:
    v = LocalSecureVault(tmp / "v.sealed", max_failed=5)
    v.seal(SECRET, PASSPHRASE)
    try:
        v.reveal("wrong-passphrase")
    except AuthError:
        return
    raise AssertionError("wrong passphrase accepted")


def test_lockout_breaker(tmp: Path) -> None:
    v = LocalSecureVault(tmp / "v.sealed", max_failed=3)
    v.seal(SECRET, PASSPHRASE)
    for _ in range(3):
        try:
            v.reveal("wrong")
        except (AuthError, VaultLocked):
            pass
    try:
        v.reveal(PASSPHRASE)
    except VaultLocked:
        pass
    else:
        raise AssertionError("breaker did not lock the store")


def test_vault_selftest_entry() -> None:
    vault_py = Path(__file__).with_name("vault.py")
    proc = subprocess.run(
        [sys.executable, str(vault_py), "selftest"],
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "SELFTEST OK" in proc.stdout


def main() -> int:
    cases = [
        ("roundtrip", test_roundtrip),
        ("zero_plaintext_on_disk", test_zero_plaintext_on_disk),
        ("wrong_passphrase_rejected", test_wrong_passphrase_rejected),
        ("lockout_breaker", test_lockout_breaker),
    ]
    failed = 0
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        for name, fn in cases:
            case_dir = tmp / name
            case_dir.mkdir(parents=True, exist_ok=True)
            try:
                fn(case_dir)
            except Exception as exc:  # noqa: BLE001
                failed += 1
                print(f"FAIL offline_sandbox.{name}: {exc}")
            else:
                print(f"PASS offline_sandbox.{name}")
    try:
        test_vault_selftest_entry()
    except Exception as exc:  # noqa: BLE001
        failed += 1
        print(f"FAIL offline_sandbox.vault_selftest_entry: {exc}")
    else:
        print("PASS offline_sandbox.vault_selftest_entry")
    total = len(cases) + 1
    if failed:
        print(f"OFFLINE_SANDBOX FAILED: {failed}/{total}")
        return 1
    print(f"OFFLINE_SANDBOX OK: {total}/{total}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
