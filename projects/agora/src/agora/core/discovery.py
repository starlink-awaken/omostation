"""Auto-discovery engine — scan workspace for MCP-capable services.

Phase 2 strategies:
1. Known projects (.venv confirmation)
2. pyproject.toml script/dependency scan
3. Port probe: scan localhost ranges for .well-known/mcp
4. docker-compose.yml port mapping extraction
"""

from __future__ import annotations

import asyncio
import socket
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

import structlog

logger = structlog.get_logger(__name__)

if TYPE_CHECKING:
    from agora.core.registry import ServiceRegistry  # type: ignore[import-not-found]


@dataclass
class DiscoveredService:
    name: str
    description: str = ""
    mcp_endpoint: str = ""
    health_endpoint: str = ""
    port: int = 0
    tags: list[str] = field(default_factory=list)
    source: str = ""
    confidence: float = 1.0


class DiscoveryEngine:
    """Auto-discover MCP services in the workspace.

    Uses four strategies:
    1. Known projects with .venv confirmation
    2. pyproject.toml metadata analysis
    3. Port probe on localhost ranges
    4. docker-compose.yml extraction
    """

    # Known MCP-capable projects with extended metadata
    KNOWN_PROJECTS: dict[str, dict] = {
        "minerva": {
            "description": "Local-first deep research system — 5 Super Tools (Dropbox Dash pattern)",
            "mcp_endpoint": "stdio://minerva",
            "health_port": 8765,
            "tags": ["research", "knowledge", "llm"],
        },
        "ontoderive": {
            "description": "Fact-driven knowledge engineering — ToolForge + derive + check",
            "mcp_endpoint": "stdio://ontoderive",
            "health_port": 0,
            "tags": ["knowledge-engineering", "derivation", "ontology"],
        },
        "sophia": {
            "description": "Symbolic research paradigm compiler — state machine formalism",
            "mcp_endpoint": "stdio://sophia",
            "health_port": 0,
            "tags": ["paradigm", "compiler", "state-machine"],
        },
        "agora": {
            "description": "MCP service convergence hub — registry, routing, pipeline",
            "mcp_endpoint": "stdio://agora",
            "health_port": 0,
            "tags": ["gateway", "registry", "pipeline"],
        },
        "agentmesh": {
            "description": "Multi-agent gateway scheduler — unified agent orchestration",
            "mcp_endpoint": "",
            "health_port": 3000,
            "tags": ["agent", "gateway", "scheduler"],
        },
        "honeycomb": {
            "description": "Multi-agent collaboration engine — DSL compiler + agent pool",
            "mcp_endpoint": "",
            "health_port": 0,
            "tags": ["agent", "dsl", "collaboration"],
        },
        "bos-skill-cli": {
            "description": "Skill discovery and staged activation CLI",
            "mcp_endpoint": "",
            "health_port": 0,
            "tags": ["skill", "discovery", "cli"],
        },
    }

    # Default port ranges to probe
    PORT_RANGES = [
        (7420, 7430),  # Agora convention
        (8765, 8766),  # Minerva
        (9000, 9005),  # Common MCP services
        (3000, 3002),  # AgentMesh / web apps
    ]

    def __init__(self, workspace_root: str | None = None):
        self.root = Path(workspace_root or self._find_workspace())

    @staticmethod
    def _find_workspace() -> str:
        cwd = Path.cwd()
        for ancestor in [cwd] + list(cwd.parents):
            # 新布局: eCOS v5 5+3+1 architecture
            if (ancestor / "projects" / "agora").is_dir() and (ancestor / "projects" / "kairon").is_dir():
                return str(ancestor)
            # monorepo 结构优先（packages/*/agora）
            pkgs = ancestor / "packages"
            if pkgs.is_dir() and (pkgs / "agora").is_dir() and (pkgs / "minerva").is_dir():
                return str(ancestor)
            # 传统扁平结构
            if (ancestor / "agora").is_dir() and (ancestor / "minerva").is_dir():
                return str(ancestor)
        return str(cwd)

    def scan_known_projects(self) -> list[DiscoveredService]:
        """Scan for known projects with .venv confirmation."""
        found = []
        for proj_name, info in self.KNOWN_PROJECTS.items():
            proj_dir = self.root / proj_name
            venv_bin = proj_dir / ".venv" / "bin"

            # 1. First check eCOS v5 layout (projects/*)
            if (self.root / "projects").is_dir():
                if (self.root / "projects" / proj_name).is_dir():
                    proj_dir = self.root / "projects" / proj_name
                    venv_bin = proj_dir / ".venv" / "bin"
                elif (self.root / "projects" / "kairon" / "packages" / proj_name).is_dir():
                    proj_dir = self.root / "projects" / "kairon" / "packages" / proj_name
                    venv_bin = self.root / "projects" / "kairon" / ".venv" / "bin"
            
            # 2. Fallbacks for old structures
            if not proj_dir.is_dir():
                proj_dir = self.root / "packages" / proj_name  # monorepo 结构
                venv_bin = proj_dir / ".venv" / "bin"
                if not venv_bin.is_dir():
                    venv_bin = proj_dir.parent.parent / ".venv" / "bin"

            if not proj_dir.is_dir():
                continue

            if not venv_bin.is_dir():
                if not (proj_dir / "node_modules").is_dir() and not (proj_dir.parent.parent / "node_modules").is_dir():
                    continue

            service = DiscoveredService(
                name=proj_name,
                description=info.get("description", proj_name),
                mcp_endpoint=info.get("mcp_endpoint", ""),
                health_endpoint=f"http://localhost:{info['health_port']}/health" if info.get("health_port") else "",
                port=info.get("health_port", 0),
                tags=info.get("tags", []),
                source=f"known-project:{proj_dir}",
                confidence=0.85,
            )
            found.append(service)
        return found

    def scan_pyproject_scripts(self) -> list[DiscoveredService]:
        """Scan pyproject.toml for MCP-related project.scripts entries."""
        found = []
        scanned_dirs = set()

        search_dirs = [self.root]
        if (self.root / "projects").is_dir():
            search_dirs.append(self.root / "projects")
            if (self.root / "projects" / "kairon" / "packages").is_dir():
                search_dirs.append(self.root / "projects" / "kairon" / "packages")

        for search_dir in search_dirs:
            for project_dir in search_dir.iterdir():
                if not project_dir.is_dir() or project_dir.name.startswith("."):
                    continue
                if str(project_dir) in scanned_dirs:
                    continue
                scanned_dirs.add(str(project_dir))

                pyproject = project_dir / "pyproject.toml"
                if not pyproject.exists():
                    continue
                try:
                    data = tomllib.loads(pyproject.read_text())
                except Exception:
                    try:
                        content = pyproject.read_text()
                    except Exception:  # noqa: S112
                        continue
                    if "mcp" not in content.lower() and "fastmcp" not in content.lower():
                        continue
                    name = project_dir.name
                    found.append(
                        DiscoveredService(
                            name=name,
                            description=f"MCP project: {name}",
                            source=f"pyproject:{pyproject}",
                            confidence=0.65,
                        )
                    )
                    continue

                scripts = data.get("project", {}).get("scripts", {})
                if not scripts:
                    continue

                # Check if any script has mcp-related name or value
                has_mcp = any("mcp" in k.lower() or "mcp" in str(v).lower() for k, v in scripts.items())
                # Also check dependencies for fastmcp
                deps = data.get("project", {}).get("dependencies", [])
                has_fastmcp = any("fastmcp" in str(d).lower() for d in deps)

                if has_mcp or has_fastmcp:
                    name = data.get("project", {}).get("name", project_dir.name)
                    desc = data.get("project", {}).get("description", "")
                    found.append(
                        DiscoveredService(
                            name=name,
                            description=desc or f"MCP service: {name}",
                            mcp_endpoint=f"stdio://{name}" if has_mcp else "",
                            source=f"pyproject:{pyproject}",
                            confidence=0.75 if has_mcp else 0.60,
                            tags=data.get("project", {}).get("keywords", []),
                        )
                    )
        return found

    def scan_docker_compose(self) -> list[DiscoveredService]:
        """Scan docker-compose.yml files for MCP-capable services."""
        found = []
        for compose_file in self.root.rglob("docker-compose*.yml"):
            try:
                data = tomllib.loads(compose_file.read_text()) if compose_file.suffix == ".toml" else None
                if data is None:
                    try:
                        import yaml
                    except ImportError:
                        continue
                    data = yaml.safe_load(compose_file.read_text())
                if not data or "services" not in data:
                    continue
                for svc_name, svc_config in data["services"].items():
                    # Skip if no ports exposed
                    ports = svc_config.get("ports", [])
                    if not ports:
                        continue
                    # Look for MCP-related images or labels
                    image = svc_config.get("image", "")
                    labels = svc_config.get("labels", {})
                    is_mcp = "mcp" in str(svc_config).lower() or "mcp" in image.lower() or labels.get("mcp") == "true"
                    if not is_mcp:
                        continue

                    port_info = str(ports[0]).split(":")
                    host_port = int(port_info[-1]) if port_info[-1].isdigit() else 0
                    found.append(
                        DiscoveredService(
                            name=svc_name,
                            description=f"Docker MCP service: {image or svc_name}",
                            mcp_endpoint=f"http://localhost:{host_port}/mcp" if host_port else "",
                            health_endpoint=f"http://localhost:{host_port}/health" if host_port else "",
                            port=host_port,
                            tags=["docker", "mcp"],
                            source=f"compose:{compose_file}",
                            confidence=0.70,
                        )
                    )
            except Exception:  # noqa: S112
                continue
        return found

    async def _probe_port(self, host: str, port: int, timeout: float = 2.0) -> bool:
        """Check if a port is open."""
        try:
            _, _, _, _, sockaddr = socket.getaddrinfo(host, port, socket.AF_INET, socket.SOCK_STREAM)[0]
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.settimeout(timeout)
                result = sock.connect_ex(sockaddr)
                return result == 0
        except Exception:
            return False

    async def _probe_mcp_endpoint(self, host: str, port: int, timeout: float = 2.0) -> str:
        """Probe a port for MCP .well-known endpoint. Returns endpoint URL or empty string."""
        import httpx

        candidates = [
            f"http://{host}:{port}/mcp",
            f"http://{host}:{port}/sse",
            f"http://{host}:{port}/.well-known/mcp",
            f"http://{host}:{port}/mcp/sse",
        ]
        for url in candidates:
            try:
                async with httpx.AsyncClient(timeout=timeout) as client:
                    r = await client.get(url)
                    if r.status_code < 500:
                        return url
            except Exception:  # noqa: S112
                continue
        return ""

    async def scan_port_range(self, hosts: list[str] | None = None) -> list[DiscoveredService]:
        """Scan port ranges for MCP-capable services listening on given hosts.

        Probes each host:port in the configured ranges, then checks
        for common MCP endpoints on open ports.
        """
        if hosts is None:
            hosts = ["localhost", "127.0.0.1", "0.0.0.0"]  # noqa: S104

        found: list[DiscoveredService] = []

        for host in hosts:
            for start, end in self.PORT_RANGES:
                for port in range(start, end + 1):
                    if not await self._probe_port(host, port, timeout=1.0):
                        continue
                    # Port is open — probe for MCP endpoint
                    mcp_url = await self._probe_mcp_endpoint(host, port, timeout=1.0)
                    if not mcp_url:
                        continue
                    found.append(
                        DiscoveredService(
                            name=f"service-{port}",
                            description=f"Auto-detected MCP service on port {port}",
                            mcp_endpoint=mcp_url,
                            health_endpoint=f"http://{host}:{port}/health",
                            port=port,
                            tags=["auto-detected", "port-probe"],
                            source=f"port-probe:{host}:{port}",
                            confidence=0.50,
                        )
                    )
        return found

    def discover_all(self, enable_port_probe: bool = False) -> list[DiscoveredService]:
        """Run all synchronous discovery strategies and deduplicate by confidence.

        Args:
            enable_port_probe: If True, includes async port probing
                               (caller must run within an event loop).
        """
        all_found: dict[str, DiscoveredService] = {}

        for svc in self.scan_known_projects():
            all_found[svc.name] = svc

        for svc in self.scan_pyproject_scripts():
            if svc.name not in all_found or svc.confidence > all_found[svc.name].confidence:
                all_found[svc.name] = svc

        for svc in self.scan_docker_compose():
            if svc.name not in all_found or svc.confidence > all_found[svc.name].confidence:
                all_found[svc.name] = svc

        return sorted(all_found.values(), key=lambda s: s.confidence, reverse=True)

    async def discover_all_async(self) -> list[DiscoveredService]:
        """Run all discovery strategies including async port probing."""
        sync_result = self.discover_all(enable_port_probe=False)
        all_found: dict[str, DiscoveredService] = {s.name: s for s in sync_result}

        # Port probe
        port_services = await self.scan_port_range()
        for svc in port_services:
            if svc.name not in all_found or svc.confidence > all_found[svc.name].confidence:
                all_found[svc.name] = svc

        return sorted(all_found.values(), key=lambda s: s.confidence, reverse=True)

    async def watch(self, registry: ServiceRegistry, interval: int = 30):
        """Watch for new services continuously. Yields discovery events."""
        import asyncio as _asyncio

        print(f"👁️  Watching for new services (interval: {interval}s). Ctrl+C to stop.")
        seen = {s.name for s in registry.list_all()}
        try:
            while True:
                await _asyncio.sleep(interval)
                count = self.auto_register(registry)
                if count > 0:
                    new = [s for s in registry.list_all() if s.name not in seen]
                    for s in new:
                        print(f"  🆕 Discovered: {s.name} ({s.mcp_endpoint or 'no endpoint'})")
                        yield s
                    seen = {s.name for s in registry.list_all()}
        except asyncio.CancelledError:
            print("\n👁️  Watch stopped.")

    def auto_register(self, registry: ServiceRegistry) -> int:
        """Discover and auto-register new services. Returns count registered."""
        from agora.core.registry import Service

        count = 0
        for svc in self.discover_all():
            if svc.name not in {s.name for s in registry.list_all()}:
                # Handle duplicate port
                port = svc.port or 0
                registry.register(
                    Service(
                        name=svc.name,
                        description=svc.description,
                        mcp_endpoint=svc.mcp_endpoint,
                        health_endpoint=svc.health_endpoint,
                        port=port,
                        tags=svc.tags,
                    )
                )
                count += 1
        return count
