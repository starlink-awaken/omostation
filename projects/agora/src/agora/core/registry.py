"""Service Registry — the single source of truth for all connected services."""

from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path

from agora.core.circuit_breaker import CircuitBreaker  # type: ignore[import-not-found]
from agora.core.service_base import (  # type: ignore[import-not-found]
    KNOWN_PROTOCOLS,
    Service,
    ServiceConfig,  # noqa: F401 — re-exported for mcp.py
    is_safe_url,
)
from agora.core.transition_log import TransitionLog  # type: ignore[import-not-found]


class ServiceRegistry:
    """Central registry for all Agora-connected services.

    Services register themselves (or are configured statically).
    The registry is the only place that knows the full topology.
    Supports health alert firing via optional EventBus callback or webhook URL.
    """

    _MAX_SERVICES = 50
    _HEALTH_COOLDOWN = 10.0
    _MAX_CONCURRENT_CHECKS = 10

    def __init__(
        self,
        storage_path: str | None = None,
        cb_max_failures: int = 3,
        cb_cooldown: float = 60.0,
        cb_success_threshold: int = 2,
        alert_callback=None,
        alert_webhook: str = "",
    ):
        self._services: dict[str, Service] = {}
        self._last_health_check: float = 0.0
        self._storage_path = storage_path or str(Path(__file__).parent.parent.parent / "agora-services.json")
        self._transitions = TransitionLog()
        self._circuit_breaker = CircuitBreaker(
            max_failures=cb_max_failures,
            cooldown=cb_cooldown,
            success_threshold=cb_success_threshold,
            alert_callback=alert_callback,
            alert_webhook=alert_webhook,
        )
        self._load()

    # ── Persistence ───────────────────────────────────────────────

    def _load(self):
        """Load persisted services from storage (SQLite with JSON fallback)."""
        from agora.persistence_db import json_load as _db_load  # type: ignore[import-not-found]

        data = _db_load(Path(self._storage_path))
        if not data:
            from agora.persistence import json_load  # type: ignore[import-not-found]

            data = json_load(Path(self._storage_path))
        if not isinstance(data, dict):
            data = {}
        services = data.get("services", [])
        if not isinstance(services, list):
            services = []
        for s in services:
            if not isinstance(s, dict):
                continue
            svc = Service(**{k: v for k, v in s.items() if k in Service.__dataclass_fields__})
            self._services[svc.name] = svc

    def _save(self):
        """Persist services to storage (SQLite + JSON fallback)."""
        from agora.persistence import json_save as _file_save
        from agora.persistence_db import json_save as _db_save

        payload = {
            "services": [
                {
                    "name": s.name,
                    "description": s.description,
                    "protocol": s.protocol,
                    "protocol_config": s.protocol_config,
                    "mcp_endpoint": s.mcp_endpoint,
                    "health_endpoint": s.health_endpoint,
                    "port": s.port,
                    "tags": s.tags,
                    "instances": s.instances,
                    "provider_info": s.provider_info,
                    "healthy": s.healthy,
                    "last_health_check": s.last_health_check,
                }
                for s in self._services.values()
            ]
        }
        _db_save(Path(self._storage_path), payload)
        _file_save(Path(self._storage_path), payload)

    # ── CRUD ──────────────────────────────────────────────────────

    def register(self, service: Service):
        if len(self._services) >= self._MAX_SERVICES:
            raise ValueError(f"Service limit reached ({self._MAX_SERVICES})")
        if service.health_endpoint and not is_safe_url(service.health_endpoint):
            raise ValueError(f"Health endpoint URL blocked: {service.health_endpoint}")
        if service.mcp_endpoint and service.mcp_endpoint.startswith("http") and not is_safe_url(service.mcp_endpoint):
            raise ValueError(f"Endpoint URL blocked: {service.mcp_endpoint}")
        if service.protocol not in KNOWN_PROTOCOLS:
            raise ValueError(f"Unknown protocol: {service.protocol}. Known: {sorted(KNOWN_PROTOCOLS)}")
        self._services[service.name] = service
        self._save()
        self._transitions.add(service.name, "", "registered", "Service registered", "register")
        try:
            from agora.audit import AuditLogger  # type: ignore[import-not-found]

            AuditLogger().log("service.register", "system", service.name)
        except Exception:
            pass

    def unregister(self, name: str):
        svc = self._services.get(name)
        state = svc.circuit_state if svc else "UNKNOWN"
        self._services.pop(name, None)
        self._save()
        self._transitions.add(name, state, "unregistered", "Service unregistered", "unregister")

    def clear_all(self) -> int:
        """Remove all services. Returns count removed. Single disk write."""
        count = len(self._services)
        self._services.clear()
        self._save()
        return count

    def get(self, name: str) -> Service | None:
        return self._services.get(name)

    def list_all(self) -> list[Service]:
        return list(self._services.values())

    def list_healthy(self) -> list[Service]:
        return [s for s in self._services.values() if s.is_available]

    # ── Heartbeat / cache runtime ─────────────────────────

    def register_heartbeat(self, name: str, identity: dict | None = None, now: float | None = None) -> dict:
        """Record a runtime heartbeat for a registered service."""
        svc = self._services.get(name)
        if svc is None:
            raise ValueError(f"Unknown service: {name}")
        timestamp = time.time() if now is None else now
        svc.last_health_check = timestamp
        svc.healthy = True
        if identity is not None:
            svc.provider_info = identity
        self._save()
        self._transitions.add(name, svc.circuit_state, "heartbeat", "Service heartbeat registered", "heartbeat")
        return {"name": name, "status": "heartbeat_registered", "last_heartbeat": timestamp}

    def stale_heartbeats(self, max_age_seconds: float, now: float | None = None) -> list[dict]:
        """Return services whose last heartbeat is older than max_age_seconds."""
        current = time.time() if now is None else now
        stale = []
        for svc in self._services.values():
            if svc.last_health_check <= 0:
                continue
            age = current - svc.last_health_check
            if age > max_age_seconds:
                stale.append({"name": svc.name, "age_seconds": age, "last_heartbeat": svc.last_health_check})
        return sorted(stale, key=lambda item: item["name"])

    def save_cache_snapshot(self, cache_path: str) -> dict:
        """Persist a last-known-good service snapshot for registry outage fallback."""
        payload = {"timestamp": time.time(), "services": self.to_dict()}
        path = Path(cache_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return {"status": "saved", "service_count": len(payload["services"]), "path": str(path)}

    @staticmethod
    def load_cache_snapshot(cache_path: str, max_age_seconds: float, now: float | None = None) -> list[Service]:
        """Load services from a fresh local cache snapshot."""
        path = Path(cache_path)
        if not path.exists():
            return []
        data = json.loads(path.read_text(encoding="utf-8"))
        current = time.time() if now is None else now
        if current - data.get("timestamp", 0) > max_age_seconds:
            return []
        services = []
        for item in data.get("services", []):
            if not isinstance(item, dict):
                continue
            services.append(
                Service(
                    name=item.get("name", ""),
                    description=item.get("description", ""),
                    protocol=item.get("protocol", "mcp"),
                    protocol_config=item.get("protocol_config", {}),
                    mcp_endpoint=item.get("endpoint", ""),
                    port=item.get("port", 0),
                    tags=item.get("tags", []),
                    provider_info=item.get("provider_info"),
                    healthy=bool(item.get("healthy", True)),
                )
            )
        return [svc for svc in services if svc.name]

    # ── Circuit breaker ──────────────────────────────────────────

    def mark_failure(self, name: str):
        svc = self._services.get(name)
        if svc:
            self._circuit_breaker.mark_failure(svc, name, self._transitions.add)

    def mark_success(self, name: str):
        svc = self._services.get(name)
        if svc:
            self._circuit_breaker.mark_success(svc, name, self._transitions.add)

    def get_circuit_status(self, name: str) -> dict:
        svc = self._services.get(name)
        if not svc:
            return {}
        return self._circuit_breaker.get_status(svc, name)

    # ── Transition log ───────────────────────────────────────────

    def get_transitions(self, service: str = "", since: str = "", limit: int = 50) -> list[dict]:
        return self._transitions.query(service, since, limit)

    def clear_transitions(self):
        self._transitions.clear()

    # ── Health ────────────────────────────────────────────────────

    def to_dict(self) -> list[dict]:
        return [s.to_dict() for s in self._services.values()]

    async def health_check_all(self):
        """Probe all registered services' health endpoints with rate limiting."""
        now = time.monotonic()
        if now - self._last_health_check < self._HEALTH_COOLDOWN:
            return
        self._last_health_check = now

        for svc in self._services.values():
            self._circuit_breaker.try_half_open(svc)

        import httpx

        semaphore = asyncio.Semaphore(self._MAX_CONCURRENT_CHECKS)

        async def _check_one(svc: Service):
            async with semaphore:
                if svc.health_endpoint:
                    if not is_safe_url(svc.health_endpoint):
                        svc.healthy = False
                        return
                    try:
                        async with httpx.AsyncClient(timeout=5) as c:
                            r = await c.get(svc.health_endpoint)
                            svc.healthy = r.status_code == 200
                            svc.last_health_check = time.monotonic()
                            if svc.healthy:
                                self.mark_success(svc.name)
                            else:
                                self.mark_failure(svc.name)
                    except Exception:
                        self.mark_failure(svc.name)
                    return

                if (
                    svc.protocol in ("mcp", "stdio")
                    and svc.mcp_endpoint
                    and not svc.mcp_endpoint.startswith(("http", "https", "proxy:", "stdio:"))
                ):
                    proc = None
                    try:
                        proc = await asyncio.create_subprocess_exec(
                            svc.mcp_endpoint,
                            stdin=asyncio.subprocess.PIPE,
                            stdout=asyncio.subprocess.PIPE,
                            stderr=asyncio.subprocess.PIPE,
                        )
                        if proc.stdin is None or proc.stdout is None:
                            self.mark_failure(svc.name)
                            return
                        init = json.dumps(
                            {
                                "jsonrpc": "2.0",
                                "id": 1,
                                "method": "initialize",
                                "params": {
                                    "protocolVersion": "2024-11-05",
                                    "capabilities": {},
                                    "clientInfo": {"name": "agora-health", "version": "1.0"},
                                },
                            }
                        )
                        proc.stdin.write(init.encode() + b"\n")
                        await proc.stdin.drain()
                        deadline = asyncio.get_event_loop().time() + 3.0
                        ok = False
                        while asyncio.get_event_loop().time() < deadline:
                            try:
                                line = await asyncio.wait_for(proc.stdout.readline(), timeout=0.5)
                                if not line:
                                    break
                                try:
                                    response = json.loads(line)
                                    if response.get("id") == 1 and "result" in response:
                                        ok = True
                                        break
                                except json.JSONDecodeError:
                                    continue
                            except TimeoutError:
                                continue
                        svc.healthy = ok
                        svc.last_health_check = time.monotonic()
                        if ok:
                            self.mark_success(svc.name)
                        else:
                            self.mark_failure(svc.name)
                    except Exception:
                        self.mark_failure(svc.name)
                    finally:
                        if proc is not None:
                            try:
                                proc.terminate()
                                await asyncio.wait_for(proc.wait(), timeout=1.0)
                            except Exception:
                                proc.kill()
                                await proc.wait()
                    return

        tasks = [_check_one(svc) for svc in self._services.values()]
        await asyncio.gather(*tasks)

    @staticmethod
    def _parse_grpc_endpoint(endpoint: str) -> tuple[str, int] | None:
        """Extract (host, port) from an MCP endpoint string.

        Handles both ``host:port`` and ``http://host:port`` formats.
        Returns ``None`` when parsing fails.
        """
        from urllib.parse import urlparse

        if "://" not in endpoint:
            endpoint = "http://" + endpoint
        parsed = urlparse(endpoint)
        host = parsed.hostname
        port = parsed.port
        if host and port:
            return host, port
        return None

    def grpc_health_check(self, name: str) -> bool:
        """Check gRPC service health via TCP port probe.

        Attempts a TCP connection to the service endpoint.  Falls back to
        the cached ``svc.healthy`` flag when the connection cannot be
        established (e.g. the service process is down).
        """
        svc = self._services.get(name)
        if not svc or svc.protocol != "grpc":
            return False

        endpoint = svc.mcp_endpoint or ""
        if not endpoint:
            return False

        parsed = self._parse_grpc_endpoint(endpoint)
        if parsed is None:
            return svc.healthy

        host, port = parsed
        try:
            import socket

            with socket.create_connection((host, port), timeout=5):
                return True
        except Exception:
            return svc.healthy
