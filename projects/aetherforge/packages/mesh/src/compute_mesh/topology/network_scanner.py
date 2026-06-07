"""NetworkScanner — 多后端网络拓扑发现。

扫描策略:
  - mDNS: 发现局域网 `*.local` 设备 (Ollama/LM Studio/Samba 等)
  - Tailscale: `tailscale status` 发现虚拟 LAN 节点
  - Proxy: 检测本地代理服务 (ClashX/Surge/Sing-box)
  - Static: 从 L0 MOF YAML 加载 (已有)

用法::

    from compute_mesh.topology.network_scanner import NetworkScanner

    scanner = NetworkScanner()
    nodes = scanner.scan_all()
    for n in nodes:
        print(f'  {n.node_id} ({n.engine_type.value}) zone={n.network_zone}')
"""

from __future__ import annotations

import json
import logging
import os
import re
import socket
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any

from .node import ComputeNode, NodeEngineType, NodeStatus, TopologyLabels

_log = logging.getLogger(__name__)

# Common proxy config paths
PROXY_CONFIG_PATHS = [
    Path.home() / ".config" / "clash" / "config.yaml",
    Path.home() / ".config" / "clash" / "settings.yaml",
    Path.home() / "Library" / "Application Support" / "ClashX" / "config.yaml",
    Path.home() / "Library" / "Application Support" / "ClashX Meta" / "config.yaml",
    Path.home() / "Library" / "Application Support" / "io.github.clashr" / "config.yaml",
    Path.home() / "Library" / "Preferences" / "com.metacubex.ClashX" / "config.yaml",
    Path.home() / ".config" / "sing-box" / "config.json",
    Path.home() / ".config" / "surge" / "conf.conf",
    # iCloud ClashX (用户配置)
    Path.home() / "Library" / "Mobile Documents" / "iCloud~com~west2online~ClashX" / "Documents" / "config.yaml",
]

# iCloud ClashX config paths
ICLOUD_BASE = Path.home() / "Library" / "Mobile Documents" / "com~apple~CloudDocs"

CLASHX_ICLOUD_PATH = Path.home() / "Library" / "Mobile Documents" / "iCloud~com~west2online~ClashX" / "Documents" / "config.yaml"

# ClashX iCloud path (from user)
# Proxy server for outbound scans
PROXY_HOST = "127.0.0.1"
PROXY_PORT = 7890  # mixed-port from ClashX config


class NetworkScanner:
    """Multi-backend network topology discovery."""

    def __init__(self) -> None:
        self._nodes: list[ComputeNode] = []

    # ── Public API ───────────────────────────────────────────────────────────

    def scan_all(self) -> list[ComputeNode]:
        """Run all discovery methods and return unique nodes."""
        self._nodes = []

        # Phase 1: mDNS / Bonjour scan (local LAN)
        self._scan_mdns()

        # Phase 2: Tailscale scan (virtual LAN)
        self._scan_tailscale()

        # Phase 3: Proxy detection (ClashX / Sing-box / Surge)
        self._scan_proxy()

        # Phase 4: iCloud ClashX config
        self._scan_icloud_clashx()

        # Deduplicate
        seen: dict[str, ComputeNode] = {}
        for n in self._nodes:
            seen[n.node_id] = n
        return list(seen.values())

    # ── Phase 1: mDNS ────────────────────────────────────────────────────────

    def _scan_mdns(self) -> None:
        """Discover services via mDNS/Bonjour.

        Checks common ports on `*.local` hosts and discovers
        Ollama / LM Studio / HTTP services.
        """
        _log.info("NetworkScanner: mDNS scan...")
        local_hosts = self._discover_mdns_hosts()

        now = datetime.now().timestamp()
        for hostname in local_hosts:
            ip = self._resolve_hostname(hostname)
            if not ip:
                continue

            # Probe common LLM service ports
            services = [
                (11434, NodeEngineType.LOCAL_DAEMON, "ollama", "Ollama"),
                (1234, NodeEngineType.LOCAL_DAEMON, "lm-studio", "LM Studio"),
                (8080, NodeEngineType.LOCAL_DAEMON, "omlx", "OMLX"),
                (8000, NodeEngineType.REMOTE_WORKER, "mcp", "MCP Server"),
            ]

            for port, etype, name, label in services:
                if self._check_port(ip, port):
                    node_id = f"{name}-{hostname.split('.')[0]}"
                    self._nodes.append(ComputeNode(
                        node_id=node_id,
                        name=f"{label} @ {hostname}",
                        engine_type=etype,
                        base_url=f"http://{ip}:{port}",
                        network_zone="lan",
                        status=NodeStatus.ONLINE,
                        topology=TopologyLabels(host=hostname),
                        last_seen=now,
                        tags={"discovery": "mdns"},
                    ))
                    _log.info("  mDNS: found %s at %s:%d", label, ip, port)

    def _discover_mdns_hosts(self) -> list[str]:
        """Discover `.local` hosts via DNS resolution.

        Uses thread with timeout to avoid hanging on DNS.
        """
        import threading

        hosts = set()
        lock = threading.Lock()
        known_hosts = ["macmini.local", "y7000p.local", "imac.local", "nas.local"]

        def resolve(h: str) -> None:
            ip = self._resolve_hostname(h)
            if ip:
                with lock:
                    hosts.add(h)

        threads = []
        for h in known_hosts:
            t = threading.Thread(target=resolve, args=(h,), daemon=True)
            t.start()
            threads.append(t)

        for t in threads:
            t.join(timeout=1.0)  # max 1s per hostname

        return list(hosts)

    def _resolve_hostname(self, hostname: str) -> str | None:
        """Resolve a hostname via DNS or proxy. Returns IP or None."""
        # Quick direct DNS first (fast for localhost, fails fast for unreachable)
        try:
            return socket.gethostbyname(hostname)
        except (socket.gaierror, OSError):
            pass

        # Try via ClashX proxy DNS (can reach remote LAN/Tailscale)
        try:
            import socks
            s = socks.socksocket()
            s.set_proxy(socks.SOCKS5, PROXY_HOST, PROXY_PORT)
            s.settimeout(1.5)
            s.connect((hostname, 80))
            s.close()
            return hostname
        except Exception:
            return None

    def _check_port(self, host: str, port: int, timeout: float = 0.5) -> bool:
        """Check if a TCP port is open, trying via proxy first."""
        # Try via proxy (can reach remote LAN/Tailscale hosts)
        try:
            import socks
            s = socks.socksocket()
            s.set_proxy(socks.SOCKS5, PROXY_HOST, PROXY_PORT)
            s.settimeout(timeout)
            result = s.connect_ex((host, port))
            s.close()
            if result == 0:
                return True
        except (ImportError, OSError):
            pass

        # Fallback: direct connect
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            result = sock.connect_ex((host, port))
            sock.close()
            return result == 0
        except Exception:
            return False

    # ── Phase 2: Tailscale ───────────────────────────────────────────────────

    def _scan_tailscale(self) -> None:
        """Discover nodes via Tailscale status."""
        _log.info("NetworkScanner: Tailscale scan...")

        # Method 1: `tailscale status --json`
        try:
            result = subprocess.run(
                ["tailscale", "status", "--json"],
                capture_output=True, text=True, timeout=5,
            )
            if result.returncode == 0:
                data = json.loads(result.stdout)
                peers = data.get("Peer", {})
                self_ip = data.get("Self", {}).get("TailscaleIPs", [None])[0]
                now = datetime.now().timestamp()

                for peer_id, peer in peers.items():
                    hostname = peer.get("HostName", peer_id)
                    ip = peer.get("TailscaleIPs", [None])[0]
                    if not ip:
                        continue

                    # Check if Ollama or LM Studio is running on the peer
                    for port, etype, name in [(11434, NodeEngineType.LOCAL_DAEMON, "ollama"),
                                               (1234, NodeEngineType.LOCAL_DAEMON, "lm-studio")]:
                        if self._check_port(ip, port, timeout=1):
                            node_id = f"{name}-ts-{hostname.lower()}"
                            self._nodes.append(ComputeNode(
                                node_id=node_id,
                                name=f"{name.title()} @ {hostname} (Tailscale)",
                                engine_type=etype,
                                base_url=f"http://{ip}:{port}",
                                network_zone="tailscale",
                                status=NodeStatus.ONLINE,
                                topology=TopologyLabels(zone="tailscale", host=hostname),
                                last_seen=now,
                                tags={"discovery": "tailscale"},
                            ))
                            _log.info("  Tailscale: found %s at %s:%d", name, ip, port)

                    # Even without known services, add as generic node
                    node_id = f"ts-{hostname.lower()}"
                    if not any(n.node_id == node_id for n in self._nodes):
                        self._nodes.append(ComputeNode(
                            node_id=node_id,
                            name=f"Tailscale: {hostname}",
                            engine_type=NodeEngineType.REMOTE_WORKER,
                            network_zone="tailscale",
                            status=NodeStatus.ONLINE,
                            topology=TopologyLabels(zone="tailscale", host=hostname),
                            last_seen=now,
                            tags={"discovery": "tailscale", "tailscale_ip": ip},
                        ))
                        _log.info("  Tailscale: discovered %s (%s)", hostname, ip)
            else:
                _log.debug("tailscale status returned %d", result.returncode)
        except FileNotFoundError:
            _log.debug("  Tailscale CLI not found")
        except (subprocess.TimeoutExpired, json.JSONDecodeError, OSError) as e:
            _log.debug("  Tailscale scan failed: %s", e)

    # ── Phase 3: Proxy ───────────────────────────────────────────────────────

    def _scan_proxy(self) -> None:
        """Detect local proxy services (ClashX, Sing-box, Surge)."""
        _log.info("NetworkScanner: proxy scan...")
        now = datetime.now().timestamp()

        for config_path in PROXY_CONFIG_PATHS:
            if not config_path.exists():
                continue

            _log.info("  Found proxy config: %s", config_path)
            config = self._load_proxy_config(config_path)
            if not config:
                continue

            # Extract proxy info
            proxies = self._extract_proxies(config, config_path)
            for proxy in proxies:
                node_id = f"proxy-{proxy['name'].lower().replace(' ', '-')}"
                self._nodes.append(ComputeNode(
                    node_id=node_id,
                    name=f"Proxy: {proxy['name']}",
                    engine_type=NodeEngineType.SSH_TUNNEL,
                    base_url=proxy.get("url", ""),
                    network_zone="proxy",
                    status=NodeStatus.ONLINE,
                    topology=TopologyLabels(zone="proxy"),
                    last_seen=now,
                    tags={"discovery": "proxy", "proxy_type": proxy.get("type", "")},
                    metadata={"proxy_config": proxy},
                ))

            # Add the proxy listen address as a node
            listen = config.get("mixed-port",
                       config.get("port",
                       config.get("external-controller", "")))
            if listen:
                node_id = f"proxy-clashx"
                if not any(n.node_id == node_id for n in self._nodes):
                    self._nodes.append(ComputeNode(
                        node_id=node_id,
                        name=f"ClashX Proxy",
                        engine_type=NodeEngineType.SSH_TUNNEL,
                        base_url=f"socks5://127.0.0.1:{listen}" if isinstance(listen, int) else str(listen),
                        network_zone="proxy",
                        status=NodeStatus.ONLINE,
                        tags={"discovery": "proxy", "config_path": str(config_path)},
                    ))
                    _log.info("  Proxy: ClashX listening on %s", listen)

    def _load_proxy_config(self, path: Path) -> dict[str, Any] | None:
        """Load a proxy config file (YAML or JSON)."""
        try:
            if path.suffix in (".yaml", ".yml"):
                import yaml
                with open(path) as f:
                    return yaml.safe_load(f)
            elif path.suffix == ".json":
                with open(path) as f:
                    return json.load(f)
            elif path.suffix == ".conf":
                # Simple key=value or ini-style
                with open(path) as f:
                    content = f.read()
                return {"raw": content[:500]}
        except Exception as e:
            _log.debug("  Failed to load %s: %s", path, e)
        return None

    def _extract_proxies(self, config: dict, path: Path) -> list[dict]:
        """Extract proxy server entries from config."""
        proxies = []
        for key in ("proxies", "proxy-groups", "servers", "outbounds"):
            entries = config.get(key, [])
            if isinstance(entries, list):
                for entry in entries:
                    if isinstance(entry, dict):
                        name = entry.get("name", entry.get("tag", "unknown"))
                        server = entry.get("server", entry.get("host", ""))
                        port = entry.get("port", 0)
                        ptype = entry.get("type", "")
                        if server and port:
                            proxies.append({
                                "name": name,
                                "type": ptype,
                                "server": server,
                                "port": port,
                                "url": f"{ptype}://{server}:{port}" if ptype else f"tcp://{server}:{port}",
                            })
        return proxies

    # ── Phase 4: iCloud ClashX ───────────────────────────────────────────────

    def _scan_icloud_clashx(self) -> None:
        """Scan iCloud Drive for ClashX config files."""
        if not ICLOUD_BASE.exists():
            return

        # Common ClashX config patterns in iCloud
        icloud_patterns = [
            "ClashX*/config.yaml",
            "clash*/config.yaml",
            "Proxy*/config.yaml",
            "VPN*/config.yaml",
        ]

        for pattern in icloud_patterns:
            for path in ICLOUD_BASE.glob(pattern):
                if path.is_file():
                    config = self._load_proxy_config(path)
                    if config:
                        proxies = self._extract_proxies(config, path)
                        for proxy in proxies:
                            nid = f"icloud-proxy-{proxy['name'].lower()[:20]}"
                            self._nodes.append(ComputeNode(
                                node_id=nid,
                                name=f"iCloud Proxy: {proxy['name']}",
                                engine_type=NodeEngineType.SSH_TUNNEL,
                                base_url=proxy.get("url", ""),
                                network_zone="proxy",
                                status=NodeStatus.ONLINE,
                                tags={"discovery": "icloud", "config_path": str(path)},
                            ))
                            _log.info("  iCloud ClashX: found proxy %s", proxy['name'])

    # ── Discovery info ─────────────────────────────────────────────────────

    def get_discovery_info(self) -> dict[str, Any]:
        """Return info about available discovery methods."""
        return {
            "mdns": {"available": True, "hosts": self._discover_mdns_hosts()},
            "tailscale": {"available": self._tailscale_available()},
            "proxy_paths": [str(p) for p in PROXY_CONFIG_PATHS if p.exists()],
        }

    @staticmethod
    def _tailscale_available() -> bool:
        try:
            result = subprocess.run(["tailscale", "version"],
                                  capture_output=True, timeout=2)
            return result.returncode == 0
        except (FileNotFoundError, OSError):
            return False
