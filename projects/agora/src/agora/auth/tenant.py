"""Multi-tenant access control — tenant.yaml + API Token + rate limiting.

Structure:
```yaml
# ~/.config/agora/tenants.yaml
tenants:
  - name: personal
    token: sk-personal-xxx
    services: [minerva, ontoderive, sophia]
    rate_limit: 100  # req/min
  - name: team
    token: sk-team-yyy
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

import os
import secrets
import time
from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass
class Tenant:
    name: str
    token: str
    services: list[str] = field(default_factory=list)
    rate_limit: int = 60  # requests per minute
    created: str = ""


class TenantManager:
    """Multi-tenant access control with token auth + rate limiting.

    Tenants are configured in ~/.config/agora/tenants.yaml.
    Falls back to a single 'default' tenant if no config exists.
    """

    DEFAULT_TOKEN_ENV = "AGORA_TOKEN"  # noqa: S105

    def __init__(self, config_path: str | None = None):
        self._path = Path(config_path or os.path.expanduser("~/.config/agora/tenants.yaml"))
        self._tenants: dict[str, Tenant] = {}  # name → Tenant
        self._token_map: dict[str, str] = {}  # token → tenant_name
        self._rate_windows: dict[str, list[float]] = {}  # name → [timestamps]
        self._load()

    def _load(self):
        """Load tenants from YAML config."""
        if not self._path.exists():
            # Create default config with auto-generated token
            self._path.parent.mkdir(parents=True, exist_ok=True)
            default_token = os.environ.get(self.DEFAULT_TOKEN_ENV, f"sk-{secrets.token_hex(16)}")
            default = {
                "tenants": [
                    {
                        "name": "default",
                        "token": default_token,
                        "services": [],
                        "rate_limit": 100,
                        "created": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    }
                ]
            }
            self._path.write_text(yaml.dump(default, default_flow_style=False))
            self._tenants["default"] = Tenant(
                name="default",
                token=default_token,
                services=[],
                rate_limit=100,
                created=default["tenants"][0]["created"],
            )
            self._token_map[default_token] = "default"
            return

        try:
            data = yaml.safe_load(self._path.read_text())
            if not data or "tenants" not in data:
                return
            for t in data["tenants"]:
                tenant = Tenant(
                    name=t.get("name", "unknown"),
                    token=t.get("token", ""),
                    services=t.get("services", []),
                    rate_limit=t.get("rate_limit", 60),
                    created=t.get("created", ""),
                )
                self._tenants[tenant.name] = tenant
                self._token_map[tenant.token] = tenant.name
        except Exception:
            pass

    def authenticate(self, token: str) -> Tenant | None:
        """Authenticate a token and return the tenant, or None if invalid."""
        name = self._token_map.get(token)
        if not name:
            return None
        return self._tenants.get(name)

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
        """List all tenants (without exposing tokens)."""
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
        """Add a new tenant. Returns the generated token."""
        token = f"sk-{secrets.token_hex(16)}"
        tenant = Tenant(
            name=name,
            token=token,
            services=services or [],
            rate_limit=rate_limit,
            created=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        )
        self._tenants[name] = tenant
        self._token_map[token] = name
        self._save()
        return token

    def remove_tenant(self, name: str) -> bool:
        """Remove a tenant."""
        tenant = self._tenants.pop(name, None)
        if tenant:
            self._token_map.pop(tenant.token, None)
            self._rate_windows.pop(name, None)
            self._save()
            return True
        return False

    def _save(self):
        """Persist tenants to YAML config."""
        data = {
            "tenants": [
                {
                    "name": t.name,
                    "token": t.token,
                    "services": t.services,
                    "rate_limit": t.rate_limit,
                    "created": t.created,
                }
                for t in self._tenants.values()
            ]
        }
        self._path.write_text(yaml.dump(data, default_flow_style=False))
