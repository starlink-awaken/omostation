#!/usr/bin/env python3
"""Local Secure Vault — offline sandbox credential store.

BET-Y1Q4-T10-05 batch 1 (minimal closed loop):
- zero-plaintext sealed envelopes on local disk (salt/nonce/ciphertext/tag only)
- stdlib-only crypto: PBKDF2-HMAC-SHA256 KDF + HMAC-SHA256-CTR stream + Encrypt-then-MAC
- circuit breaker: consecutive failed unlocks lock the store until explicit reset
- offline: this module never touches the network (no socket import)

Usage:
    python bin/security/vault.py selftest
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import hmac
import json
import sys
from pathlib import Path

MAGIC = "lsv1"
DEFAULT_ITERATIONS = 210_000
SALT_BYTES = 16
NONCE_BYTES = 16
MAX_FAILED_UNLOCKS = 5


class VaultLocked(RuntimeError):
    """Store is locked by the circuit breaker after too many failed unlocks."""


class AuthError(RuntimeError):
    """Passphrase wrong or envelope tampered."""


def _kdf(passphrase: str, salt: bytes, iterations: int) -> bytes:
    return hashlib.pbkdf2_hmac("sha256", passphrase.encode("utf-8"), salt, iterations)


def _keystream(key: bytes, nonce: bytes, length: int) -> bytes:
    out = bytearray()
    counter = 0
    while len(out) < length:
        out.extend(hmac.new(key, nonce + counter.to_bytes(8, "big"), hashlib.sha256).digest())
        counter += 1
    return bytes(out[:length])


def _b64e(raw: bytes) -> str:
    return base64.b64encode(raw).decode("ascii")


def _b64d(text: str) -> bytes:
    return base64.b64decode(text.encode("ascii"))


def seal_blob(plaintext: bytes, passphrase: str, iterations: int = DEFAULT_ITERATIONS) -> dict:
    import os

    salt = os.urandom(SALT_BYTES)
    nonce = os.urandom(NONCE_BYTES)
    key = _kdf(passphrase, salt, iterations)
    stream = _keystream(key, nonce, len(plaintext))
    ciphertext = bytes(p ^ s for p, s in zip(plaintext, stream))
    tag = hmac.new(key, MAGIC.encode() + nonce + ciphertext, hashlib.sha256).digest()
    return {
        "magic": MAGIC,
        "kdf": "PBKDF2-HMAC-SHA256",
        "iterations": iterations,
        "salt": _b64e(salt),
        "nonce": _b64e(nonce),
        "ciphertext": _b64e(ciphertext),
        "tag": _b64e(tag),
    }


def unseal_blob(envelope: dict, passphrase: str) -> bytes:
    if envelope.get("magic") != MAGIC:
        raise AuthError("unknown envelope magic")
    salt = _b64d(envelope["salt"])
    nonce = _b64d(envelope["nonce"])
    ciphertext = _b64d(envelope["ciphertext"])
    tag = _b64d(envelope["tag"])
    key = _kdf(passphrase, salt, int(envelope["iterations"]))
    expected = hmac.new(key, MAGIC.encode() + nonce + ciphertext, hashlib.sha256).digest()
    if not hmac.compare_digest(expected, tag):
        raise AuthError("authentication failed (wrong passphrase or tampered envelope)")
    stream = _keystream(key, nonce, len(ciphertext))
    return bytes(c ^ s for c, s in zip(ciphertext, stream))


class LocalSecureVault:
    """Single-file sealed secret with lockout-tracked reveals."""

    def __init__(self, store: Path, max_failed: int = MAX_FAILED_UNLOCKS) -> None:
        self.store = Path(store)
        self.attempts_file = self.store.with_suffix(self.store.suffix + ".attempts")
        self.max_failed = max_failed

    def _attempts(self) -> dict:
        if self.attempts_file.is_file():
            try:
                return json.loads(self.attempts_file.read_text(encoding="utf-8"))
            except (ValueError, OSError):
                pass
        return {"failed": 0, "locked": False}

    def _save_attempts(self, state: dict) -> None:
        self.attempts_file.write_text(json.dumps(state), encoding="utf-8")

    def seal(self, secret: bytes, passphrase: str) -> None:
        self.store.write_text(json.dumps(seal_blob(secret, passphrase)), encoding="utf-8")
        self._save_attempts({"failed": 0, "locked": False})

    def reveal(self, passphrase: str) -> bytes:
        state = self._attempts()
        if state.get("locked"):
            raise VaultLocked("store locked: too many failed unlocks, explicit reset required")
        try:
            envelope = json.loads(self.store.read_text(encoding="utf-8"))
            secret = unseal_blob(envelope, passphrase)
        except AuthError:
            state["failed"] = int(state.get("failed", 0)) + 1
            if state["failed"] >= self.max_failed:
                state["locked"] = True
            self._save_attempts(state)
            if state["locked"]:
                raise VaultLocked("store locked after %d failed unlocks" % state["failed"])
            raise
        self._save_attempts({"failed": 0, "locked": False})
        return secret

    def reset_lock(self) -> None:
        self._save_attempts({"failed": 0, "locked": False})


def selftest() -> int:
    import tempfile

    failures = []

    def check(name: str, fn) -> None:
        try:
            fn()
        except Exception as exc:  # noqa: BLE001
            failures.append((name, exc))
            print(f"FAIL {name}: {exc}")
        else:
            print(f"PASS {name}")

    def t_roundtrip() -> None:
        with tempfile.TemporaryDirectory() as tmp:
            v = LocalSecureVault(Path(tmp) / "vault.sealed", max_failed=3)
            v.seal(b"supersecret-signing-key", "correct-horse")
            assert v.reveal("correct-horse") == b"supersecret-signing-key"

    def t_zero_plaintext() -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = Path(tmp) / "vault.sealed"
            LocalSecureVault(store, max_failed=3).seal(b"supersecret-signing-key", "correct-horse")
            raw = store.read_bytes()
            assert b"supersecret-signing-key" not in raw, "plaintext leaked to disk"
            assert b"correct-horse" not in raw, "passphrase leaked to disk"

    def t_tamper_rejected() -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = Path(tmp) / "vault.sealed"
            LocalSecureVault(store, max_failed=3).seal(b"data", "pw")
            env = json.loads(store.read_text(encoding="utf-8"))
            ct = bytearray(_b64d(env["ciphertext"]))
            ct[0] ^= 0x01
            env["ciphertext"] = _b64e(bytes(ct))
            store.write_text(json.dumps(env), encoding="utf-8")
            try:
                LocalSecureVault(store, max_failed=3).reveal("pw")
            except AuthError:
                return
            raise AssertionError("tampered envelope was accepted")

    def t_lockout_breaker() -> None:
        with tempfile.TemporaryDirectory() as tmp:
            v = LocalSecureVault(Path(tmp) / "vault.sealed", max_failed=3)
            v.seal(b"data", "pw")
            for _ in range(2):
                try:
                    v.reveal("wrong")
                except AuthError:
                    pass
            try:
                v.reveal("wrong")
            except VaultLocked:
                pass
            else:
                raise AssertionError("circuit breaker did not lock")
            try:
                v.reveal("pw")
            except VaultLocked:
                pass
            else:
                raise AssertionError("locked store still reveals")
            v.reset_lock()
            assert v.reveal("pw") == b"data"

    def t_offline_no_socket() -> None:
        assert "socket" not in sys.modules, "vault must not pull in socket"

    check("roundtrip", t_roundtrip)
    check("zero_plaintext", t_zero_plaintext)
    check("tamper_rejected", t_tamper_rejected)
    check("lockout_breaker", t_lockout_breaker)
    check("offline_no_socket", t_offline_no_socket)
    if failures:
        print(f"SELFTEST FAILED: {len(failures)} failing")
        return 1
    print("SELFTEST OK: 5/5")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Local Secure Vault (offline sandbox)")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("selftest", help="run offline closed-loop self test")
    args = parser.parse_args(argv)
    if args.cmd == "selftest":
        return selftest()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
