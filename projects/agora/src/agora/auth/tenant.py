"""Multi-tenant access control — tenant.yaml + API Token + rate limiting.

Structure:
```yaml
# ~/.config/agora/tenants.yaml
tenants:
  - name: personal
    token_hash: pbkdf2:sha256:600000$salt$hash
    services: [minerva, ontoderive, sophia]
    rate_limit: 100  # req/min
  - name: team
    token_hash: pbkdf2:sha256:600000$salt$hash
    services: [minerva, kos]
    rate_limit: 300
```

Usage:
    from agora.auth.tenant import TenantManager
    tm = TenantManager()
    tenant = tm.authenticate("sk-personal-xxx")  # → Tenant or None
    tm.check_rate_limit("personal")               # → True/False
"""

from __future__ import annotations

import hashlib
import os
import secrets
import time
from dataclasses import dataclass, field
from pathlib import Path

import yaml

# PBKDF2 settings
_PBKDF2_ITERATIONS = 600_000
_PBKDF2_HASH_LENGTH = 32
_PBKDF2_PREFIX = "pbkdf2:sha256"


@dataclass
class Tenant:
    name: str
    token_hash: str = ""
    services: list[str] = field(default_factory=list)
    rate_limit: int = 60  # requests per minute
    created: str = ""


class TenantManager:
    """Multi-tenant access control with token auth + rate limiting.

    Tenants are configured in ~/.config/agora/tenants.yaml.
    Tokens are stored as PBKDF2 hashes, never in plaintext.
    Falls back to a single 'default' tenant if no config exists.
    """

    DEFAULT_TOKEN_ENV = "AGORA_TOKEN"  # noqa: S105

    def __init__(self, config_path: str | None = None):
        self._path = Path(config_path or os.path.expanduser("~/.config/agora/tenants.yaml"))
        self._tenants: dict[str, Tenant] = {}  # name → Tenant
        self._token_map: dict[str, str] = {}  # token_hash → tenant_name
        self._rate_windows: dict[str, list[float]] = {}  # name → [timestamps]
        self._load()

    # ── PBKDF2 helpers ────────────────────────────────────────────────────

    @staticmethod
    def _hash_token(token: str) -> str:
        """Hash a token using PBKDF2-SHA256. Returns formatted string for storage."""
        salt = secrets.token_hex(16)
        dk = hashlib.pbkdf2_hmac("sha256", token.encode(), salt.encode(), _PBKDF2_ITERATIONS, _PBKDF2_HASH_LENGTH)
        return f"{_PBKDF2_PREFIX}:{_PBKDF2_ITERATIONS}:{salt}:{dk.hex()}"

    @staticmethod
    def _verify_token(token: str, stored: str) -> bool:
        """Verify a token against a stored PBKDF2 hash string."""
        if not stored.startswith(_PBKDF2_PREFIX + ":"):
            # Legacy plain-text token — constant-time compare
            return secrets.compare_digest(token, stored)
        try:
            parts = stored.split(":")
            # Format: pbkdf2:sha256:{iterations}:{salt}:{hex_hash}
            if len(parts) != 5:
                return False
            _, _, iterations_str, salt, expected_hex = parts
            iterations = int(iterations_str)
            dk = hashlib.pbkdf2_hmac("sha256", token.encode(), salt.encode(), iterations, _PBKDF2_HASH_LENGTH)
            return secrets.compare_digest(dk.hex(), expected_hex)
        except (ValueError, AttributeError):
            return False

    # ── Loading / saving ──────────────────────────────────────────────────

    def _load(self):
        """Load tenants from YAML config. Migrate legacy plain-text tokens to hashed."""
        if not self._path.exists():
            self._create_default()
            return

        try:
            data = yaml.safe_load(self._path.read_text())
            if not data or "tenants" not in data:
                return

            needs_save = False
            for t in data["tenants"]:
                token_field = t.get("token_hash") or t.get("token", "")
                if "token" in t and "token_hash" not in t:
                    # Legacy plain-text token — hash it now
                    token_field = self._hash_token(t["token"])
                    needs_save = True

                tenant = Tenant(
                    name=t.get("name", "unknown"),
                    token_hash=token_field,
                    services=t.get("services", []),
                    rate_limit=t.get("rate_limit", 60),
                    created=t.get("created", ""),
                )
                self._tenants[tenant.name] = tenant
                self._token_map[tenant.token_hash] = tenant.name

            if needs_save:
                self._save()
        except Exception:
            pass

    def _create_default(self):
        """Create default tenant config with a hashed auto-generated token."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        raw_token = os.environ.get(self.DEFAULT_TOKEN_ENV, f"sk-{secrets.token_hex(16)}")
        token_hash = self._hash_token(raw_token)

        self._tenants["default"] = Tenant(
            name="default",
            token_hash=token_hash,
            services=[],
            rate_limit=100,
            created=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        )
        self._token_map[token_hash] = "default"

        # Store hash only — token was printed to console or returned once
        self._save()

        # Log the raw token so the user can capture it (this is the only time it's visible)
        import logging
        logging.getLogger(__name__).warning(
            "Generated new default tenant token: %s  (save this — it will not be shown again)", raw_token
        )

    def _save(self):
        """Persist tenants to YAML config. Only token hashes are stored, never plain tokens."""
        data = {
            "tenants": [
                {
                    "name": t.name,
                    "token_hash": t.token_hash,
                    "services": t.services,
                    "rate_limit": t.rate_limit,
                    "created": t.created,
                }
                for t in self._tenants.values()
            ]
        }
        self._path.write_text(yaml.dump(data, default_flow_style=False))

    # ── Public API ─────────────────────────────────────────────────────────

    def authenticate(self, token: str) -> Tenant | None:
        """Authenticate a token and return the tenant, or None if invalid."""
        for tenant_hash, name in self._token_map.items():
            if self._verify_token(token, tenant_hash):
                return self._tenants.get(name)
        return None

    def check_rate_limit(self, tenant_name: str) -> bool:
        """Check if tenant has exceeded rate limit.

        Returns True if request is allowed, False if rate limited.
        Uses sliding window of 60 seconds.
        """
        tenant = self._tenants.get(tenant_name)
        if not tenant:
            return False

        now = time.monotonic()
        window = 60.0  # 1 minute window
        max_reqs = tenant.rate_limit

        if tenant_name not in self._rate_windows:
            self._rate_windows[tenant_name] = []

        # Prune old entries
        window_start = now - window
        self._rate_windows[tenant_name] = [ts for ts in self._rate_windows[tenant_name] if ts > window_start]

        if len(self._rate_windows[tenant_name]) >= max_reqs:
            return False

        self._rate_windows[tenant_name].append(now)
        return True

    def has_service_access(self, tenant_name: str, service_name: str) -> bool:
        """Check if tenant has access to a specific service.
        Empty services list = access to all.
        """
        tenant = self._tenants.get(tenant_name)
        if not tenant:
            return False
        if not tenant.services:
            return True  # empty = all access
        return service_name in tenant.services

    def list_tenants(self) -> list[dict]:
        """List all tenants (without exposing tokens or hashes)."""
        return [
            {
                "name": t.name,
                "services": t.services,
                "rate_limit": t.rate_limit,
                "created": t.created,
            }
            for t in self._tenants.values()
        ]

    def add_tenant(self, name: str, services: list[str] | None = None, rate_limit: int = 60) -> str:
        """Add a new tenant. Returns the **raw token** (only time it is visible)."""
        raw_token = f"sk-{secrets.token_hex(16)}"
        token_hash = self._hash_token(raw_token)
        tenant = Tenant(
            name=name,
            token_hash=token_hash,
            services=services or [],
            rate_limit=rate_limit,
            created=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        )
        self._tenants[name] = tenant
        self._token_map[token_hash] = name
        self._save()
        return raw_token

    def remove_tenant(self, name: str) -> bool:
        """Remove a tenant."""
        tenant = self._tenants.pop(name, None)
        if tenant:
            self._token_map.pop(tenant.token_hash, None)
            self._rate_windows.pop(name, None)
            self._save()
            return True
        return False
