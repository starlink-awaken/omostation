from __future__ import annotations

"""
---
Type: Module
Status: ACTIVE
Version: 1.0.0
Authority: nucleus/Z-Core/L0-Genome/R0-ACT-SYS-AX01-10_holographic_metadata_axiom.md
Layer: L3
---
"""
# =============================================================================
# 0. 形式化摘要 ≝
# =============================================================================
# Credentials ≡ Module
# 内涵 ≝ {Credentials}
# 外延 ≝ {e | e ∈ Organs ∧ implements(e, Credentials)}
# 功能 ⊢ {Init_Credentials, Execute_Credentials, Validate_Credentials}
# =============================================================================

# ---
# domain: D-Harvest
# layer: organ
# status: active
# ---

"""
Runtime credential injection for dynamic source authentication

Provides secure runtime credential management for sources that require
dynamic authentication (e.g., OAuth tokens, API keys with expiration).
Credentials are never stored in YAML configuration files.
"""
import importlib
import json
import logging
import os
import stat
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from cryptography.fernet import InvalidToken

_log = logging.getLogger(__name__)


def _get_secret_shield() -> Any | None:
    """Load the optional SecretShield singleton without a static cross-organ import."""
    try:
        secret_shield_module = importlib.import_module("organs.D_Immunity.organs.secret_shield")
    except (ImportError, ModuleNotFoundError):
        return None
    return getattr(secret_shield_module, "Shield", None)


def _write_private_json(path: Path, payload: dict[str, Any]) -> None:
    """Persist credential material with owner-only permissions."""
    temp_path = path.with_suffix(f"{path.suffix}.tmp")
    fd = os.open(
        temp_path,
        os.O_WRONLY | os.O_CREAT | os.O_TRUNC,
        stat.S_IRUSR | stat.S_IWUSR,
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2)
        os.replace(temp_path, path)
    except (OSError, TypeError, ValueError):
        temp_path.unlink(missing_ok=True)
        raise


def _looks_like_sealed_value(value: Any) -> bool:
    """Best-effort discriminator for Fernet-sealed values."""
    return isinstance(value, str) and value.startswith("gAAAA")


@dataclass
class Credential:
    """Runtime credential with metadata"""

    credential_type: str  # e.g., "api_key", "oauth_token", "basic_auth"
    value: str
    expires_at: str | None = None  # ISO timestamp
    metadata: dict[str, Any] | None = None

    def is_valid(self) -> bool:
        """Check if credential is still valid"""
        if not self.value:
            return False

        if self.expires_at:
            try:
                expiry = datetime.fromisoformat(self.expires_at)
                return datetime.now(UTC) < expiry
            except ValueError:
                return False

        return True

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization"""
        return {
            "credential_type": self.credential_type,
            "value": self.value,
            "expires_at": self.expires_at,
            "metadata": self.metadata or {},
        }


class CredentialInjector:
    """
    Runtime credential injection manager

    Provides secure runtime credential management for dynamic sources.
    Credentials are stored separately from source configuration and
    injected at harvest time.
    """

    def __init__(self, credential_dir: Path | None = None) -> None:
        """
        Initialize credential injector

        Args:
            credential_dir: Directory for credential files (default: .omc/credentials/)
        """
        self.credential_dir = credential_dir or Path(".omc/credentials")
        self.credential_dir.mkdir(parents=True, exist_ok=True)
        self._memory_cache: dict[str, Credential] = {}

    def _get_credential_path(self, source_id: str) -> Path:
        """Get credential file path for a source"""
        return self.credential_dir / f"{source_id}.json"

    def set_credential(self, source_id: str, credential: Credential) -> bool:
        """
        Store credential for a source

        Args:
            source_id: Source identifier
            credential: Credential to store

        Returns:
            True if credential stored successfully
        """
        try:
            # Store in memory cache
            self._memory_cache[source_id] = credential

            # Store to disk (encrypted via SecretShield)
            credential_path = self._get_credential_path(source_id)
            cred_dict = credential.to_dict()
            shield = _get_secret_shield()
            if shield is not None:
                cred_dict["value"] = shield.seal(cred_dict["value"])
            _write_private_json(credential_path, cred_dict)

            _log.info(f"Credential stored for source {source_id}")
            return True

        except (OSError, TypeError, ValueError, json.JSONDecodeError) as e:
            _log.error(f"Failed to store credential for {source_id}: {e}")
            return False

    def get_credential(self, source_id: str) -> Credential | None:
        """
        Retrieve credential for a source

        Args:
            source_id: Source identifier

        Returns:
            Credential if found and valid, None otherwise
        """
        # Check memory cache first
        if source_id in self._memory_cache:
            credential = self._memory_cache[source_id]
            if credential.is_valid():
                return credential
            else:
                # Remove expired credential
                del self._memory_cache[source_id]

        # Load from disk
        credential_path = self._get_credential_path(source_id)

        if not credential_path.exists():
            return None

        try:
            with open(credential_path, encoding="utf-8") as f:
                data = json.load(f)

            raw_value = data["value"]
            shield = _get_secret_shield()
            legacy_plaintext = False
            if shield is not None:
                if _looks_like_sealed_value(raw_value):
                    try:
                        raw_value = shield.reveal(raw_value)
                    except InvalidToken:
                        _log.error(
                            "Credential for %s has invalid sealed token — Fernet decryption failed",
                            source_id,
                        )
                        return None
                else:
                    legacy_plaintext = True

            credential = Credential(
                credential_type=data["credential_type"],
                value=raw_value,
                expires_at=data.get("expires_at"),
                metadata=data.get("metadata", {}),
            )

            if credential.is_valid():
                if legacy_plaintext and shield is not None:
                    migrated_payload = dict(data)
                    migrated_payload["value"] = shield.seal(credential.value)
                    _write_private_json(credential_path, migrated_payload)
                # Cache in memory
                self._memory_cache[source_id] = credential
                return credential
            else:
                _log.warning(f"Credential for {source_id} is expired")
                return None

        except (OSError, TypeError, json.JSONDecodeError, KeyError) as e:
            _log.error(f"Failed to load credential for {source_id}: {e}")
            return None

    def inject_credentials(self, source_config: dict) -> dict:
        """
        Inject runtime credentials into source configuration

        Args:
            source_config: Source configuration dict

        Returns:
            Configuration with injected credentials (original not modified)
        """
        source_id = source_config.get("id")

        if not source_id:
            return source_config

        credential = self.get_credential(source_id)

        if not credential:
            _log.warning(f"No credentials found for source {source_id}")
            return source_config

        # Clone config to avoid modifying original
        config = source_config.copy()

        # Inject credentials based on type
        if credential.credential_type == "api_key":
            config["headers"] = config.get("headers", {})
            config["headers"]["Authorization"] = f"Bearer {credential.value}"

        elif credential.credential_type == "basic_auth":
            config["auth"] = {
                "username": (credential.metadata or {}).get("username", ""),
                "password": credential.value,
            }

        elif credential.credential_type == "oauth_token":
            config["headers"] = config.get("headers", {})
            config["headers"]["Authorization"] = f"OAuth {credential.value}"

        elif credential.credential_type == "custom_header":
            header_name = (credential.metadata or {}).get("header_name", "X-API-Key")
            config["headers"] = config.get("headers", {})
            config["headers"][header_name] = credential.value

        _log.info(f"Credentials injected for source {source_id}")
        return config

    def revoke_credential(self, source_id: str) -> bool:
        """
        Revoke credential for a source

        Args:
            source_id: Source identifier

        Returns:
            True if credential revoked successfully
        """
        try:
            # Remove from memory cache
            if source_id in self._memory_cache:
                del self._memory_cache[source_id]

            # Remove from disk
            credential_path = self._get_credential_path(source_id)
            if credential_path.exists():
                credential_path.unlink()

            _log.info(f"Credential revoked for source {source_id}")
            return True

        except OSError as e:
            _log.error(f"Failed to revoke credential for {source_id}: {e}")
            return False
