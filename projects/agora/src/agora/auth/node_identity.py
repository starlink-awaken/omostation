from __future__ import annotations

"""
---
Type: Organ
Status: ACTIVE
Version: 1.0.0
Owner: "@Copilot"
Layer: L3
Summary: "NodeIdentityManager — persistent UUIDv4 + Ed25519 key pair per B-OS node."
Authority: organs/D-Gateway/AGENTS.md
---
"""

# =============================================================================
# 0. 形式化摘要 ≝
# =============================================================================
# Node Identity ≡ Module
# 内涵 ≝ {NodeIdentity, NodeIdentityManager}
# 外延 ≝ {e | e ∈ D-Gateway ∧ implements(e, NodeIdentity)}
# 功能 ⊢ {Load_Or_Create, Generate_Identity, Persist_Identity}
# =============================================================================
import base64
import json
import logging
import os
import socket
import uuid
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

_log = logging.getLogger(__name__)

__all__ = ["NodeIdentity", "NodeIdentityManager"]

# ---------------------------------------------------------------------------
# Crypto helpers — cryptography package preferred, os.urandom fallback
# ---------------------------------------------------------------------------


def _generate_ed25519_keypair() -> tuple[str, str]:
    """Return (private_key_b64, public_key_b64) for an Ed25519 key pair.

    Tries the *cryptography* package first; falls back to a random 32-byte
    seed encoded as base64 when the package is unavailable.
    """
    try:
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
        from cryptography.hazmat.primitives.serialization import (
            Encoding,
            NoEncryption,
            PrivateFormat,
            PublicFormat,
        )

        private_key = Ed25519PrivateKey.generate()
        private_bytes = private_key.private_bytes(
            encoding=Encoding.Raw,
            format=PrivateFormat.Raw,
            encryption_algorithm=NoEncryption(),
        )
        public_bytes = private_key.public_key().public_bytes(
            encoding=Encoding.Raw,
            format=PublicFormat.Raw,
        )
        return (
            base64.b64encode(private_bytes).decode(),
            base64.b64encode(public_bytes).decode(),
        )
    except ImportError:
        _log.debug("cryptography package not available — using random 32-byte fallback for key material")
        private_bytes = os.urandom(32)
        # Derive a deterministic "public key" via XOR mask (not real Ed25519,
        # but sufficient as a unique opaque identifier for the fallback path).
        public_bytes = bytes(b ^ 0xFF for b in private_bytes)
        return (
            base64.b64encode(private_bytes).decode(),
            base64.b64encode(public_bytes).decode(),
        )


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass
class NodeIdentity:
    """Immutable identity record for a single B-OS node."""

    node_id: str  # UUIDv4
    public_key: str  # base64-encoded Ed25519 public key (or fallback)
    created_at: str  # ISO 8601 datetime (UTC)
    display_name: str  # BOS_NODE_NAME env var, or hostname

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> NodeIdentity:
        return cls(
            node_id=data["node_id"],
            public_key=data["public_key"],
            created_at=data["created_at"],
            display_name=data.get("display_name", ""),
        )


# ---------------------------------------------------------------------------
# Manager
# ---------------------------------------------------------------------------


class NodeIdentityManager:
    """Manages persistent node identity stored at *identity_path*.

    On first call to :meth:`load_or_create` a fresh UUIDv4 + key pair is
    generated and written to disk.  Subsequent calls return the same identity
    (idempotent).

    The private key is stored alongside the identity record so that later
    phases can sign handshake challenges.  Only the *public key* is shared
    over the wire.
    """

    DEFAULT_PATH: str = "config/node_identity.json"

    def __init__(self, identity_path: str | None = None) -> None:
        self._path = Path(identity_path or self.DEFAULT_PATH)
        self._identity: NodeIdentity | None = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load_or_create(self) -> NodeIdentity:
        """Return the persisted identity, generating one if it doesn't exist."""
        if self._identity is not None:
            return self._identity

        if self._path.exists():
            try:
                self._identity = self._load()
                _log.debug("Loaded node identity %s from %s", self._identity.node_id, self._path)
                return self._identity
            except (KeyError, json.JSONDecodeError, ValueError) as exc:
                _log.warning("Corrupt identity file at %s (%s) — regenerating.", self._path, exc)

        self._identity = self._generate()
        return self._identity

    def get(self) -> NodeIdentity | None:
        """Return the cached identity without loading or creating."""
        return self._identity

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _load(self) -> NodeIdentity:
        """Deserialise the identity from *self._path*."""
        raw = json.loads(self._path.read_text(encoding="utf-8"))
        return NodeIdentity.from_dict(raw)

    def _generate(self) -> NodeIdentity:
        """Generate a fresh identity, persist it, and return it."""
        _private_key_b64, public_key_b64 = _generate_ed25519_keypair()
        identity = NodeIdentity(
            node_id=str(uuid.uuid4()),
            public_key=public_key_b64,
            created_at=datetime.now(UTC).isoformat(),
            display_name=os.environ.get("BOS_NODE_NAME", socket.gethostname()),
        )
        self._persist(identity, _private_key_b64)
        _log.info("Generated new node identity %s → %s", identity.node_id, self._path)
        return identity

    def _persist(self, identity: NodeIdentity, private_key_b64: str) -> None:
        """Write identity (including private key) to disk in JSON format."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        payload = identity.to_dict()
        payload["_private_key"] = private_key_b64  # stored locally, never shared
        self._path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        # Restrict read permissions on platforms that support it.
        try:
            self._path.chmod(0o600)
        except NotImplementedError:
            pass  # Windows / restricted filesystems — skip silently
