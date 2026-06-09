"""MCP Tool Market — discover, install, and register third-party MCP services.

Usage:
    agora market list                          # List available MCP services
    agora market search "filesystem"           # Search by keyword
    agora market install starlink-awaken/minerva  # Install from GitHub
    agora market install <url> --name custom   # Install from any URL
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import structlog

logger = structlog.get_logger(__name__)


# Built-in MCP service registry
BUILTIN_MARKET: dict[str, dict] = {
    "minerva": {
        "name": "minerva",
        "description": "Local-first deep research system — web + academic + code search",
        "repo": "starlink-awaken/minerva",
        "type": "python",
        "entry": "mcp_server.py",
        "tags": ["research", "llm", "knowledge"],
        "port": 8765,
    },
    "ontoderive": {
        "name": "ontoderive",
        "description": "Fact-driven derivation engine — ToolForge + consistency check",
        "repo": "starlink-awaken/ontoderive",
        "type": "python",
        "entry": "engine/mcp-server.py",
        "tags": ["knowledge", "ontology", "derivation"],
        "port": 0,
    },
    "sophia": {
        "name": "sophia",
        "description": "Symbolic research paradigm compiler — state machine formalism",
        "repo": "starlink-awaken/sophia",
        "type": "python",
        "entry": "cli.py",
        "tags": ["paradigm", "compiler", "state-machine"],
        "port": 0,
    },
    "kos": {
        "name": "kos",
        "description": "Knowledge OS — cross-domain semantic search + entity graph",
        "repo": "starlink-awaken/kos",
        "type": "python",
        "entry": "kos-mcp-server.py",
        "tags": ["knowledge", "search", "graph"],
        "port": 0,
    },
    "filesystem": {
        "name": "filesystem",
        "description": "Local filesystem MCP — read, write, search, patch files",
        "repo": "modelcontextprotocol/servers",
        "subdir": "src/filesystem",
        "type": "node",
        "entry": "dist/index.js",
        "tags": ["filesystem", "local"],
        "port": 0,
    },
    "fetch": {
        "name": "fetch",
        "description": "HTTP fetch MCP — web scraping and API calls",
        "repo": "modelcontextprotocol/servers",
        "subdir": "src/fetch",
        "type": "node",
        "entry": "dist/index.js",
        "tags": ["web", "http", "scraping"],
        "port": 0,
    },
    "puppeteer": {
        "name": "puppeteer",
        "description": "Browser automation MCP — headless Chrome control",
        "repo": "modelcontextprotocol/servers",
        "subdir": "src/puppeteer",
        "type": "node",
        "entry": "dist/index.js",
        "tags": ["browser", "automation", "scraping"],
        "port": 0,
    },
    "github": {
        "name": "github",
        "description": "GitHub API MCP — issues, PRs, repos, code review",
        "repo": "modelcontextprotocol/servers",
        "subdir": "src/github",
        "type": "node",
        "entry": "dist/index.js",
        "tags": ["github", "git", "code-review"],
        "port": 0,
    },
    "sequential-thinking": {
        "name": "sequential-thinking",
        "description": "Sequential thinking MCP — structured reasoning steps",
        "repo": "modelcontextprotocol/servers",
        "subdir": "src/sequentialthinking",
        "type": "node",
        "entry": "dist/index.js",
        "tags": ["reasoning", "thinking"],
        "port": 0,
    },
    "brave-search": {
        "name": "brave-search",
        "description": "Brave Search MCP — web and local search API",
        "repo": "modelcontextprotocol/servers",
        "subdir": "src/brave-search",
        "type": "node",
        "entry": "dist/index.js",
        "tags": ["search", "web"],
        "port": 0,
    },
    "memory": {
        "name": "memory",
        "description": "Knowledge graph memory MCP — persistent entity + relation storage",
        "repo": "modelcontextprotocol/servers",
        "subdir": "src/memory",
        "type": "node",
        "entry": "dist/index.js",
        "tags": ["memory", "graph", "knowledge"],
        "port": 0,
    },
    "sqlite": {
        "name": "sqlite",
        "description": "SQLite MCP — query and manage local SQLite databases",
        "repo": "modelcontextprotocol/servers",
        "subdir": "src/sqlite",
        "type": "node",
        "entry": "dist/index.js",
        "tags": ["database", "sql", "local"],
        "port": 0,
    },
    "postgres": {
        "name": "postgres",
        "description": "PostgreSQL MCP — schema inspection + query execution",
        "repo": "modelcontextprotocol/servers",
        "subdir": "src/postgres",
        "type": "node",
        "entry": "dist/index.js",
        "tags": ["database", "sql", "postgres"],
        "port": 0,
    },
    "slack": {
        "name": "slack",
        "description": "Slack MCP — channel management, messaging, search",
        "repo": "modelcontextprotocol/servers",
        "subdir": "src/slack",
        "type": "node",
        "entry": "dist/index.js",
        "tags": ["slack", "messaging", "team"],
        "port": 0,
    },
    "google-drive": {
        "name": "google-drive",
        "description": "Google Drive MCP — file listing, search, read/write",
        "repo": "anthropics/superpowers",
        "subdir": "skills/superpowers/mcp-drive",
        "type": "node",
        "entry": "dist/index.js",
        "tags": ["google", "drive", "files"],
        "port": 0,
    },
    "everart": {
        "name": "everart",
        "description": "EverArt MCP — AI image generation and editing",
        "repo": "modelcontextprotocol/servers",
        "subdir": "src/everart",
        "type": "node",
        "entry": "dist/index.js",
        "tags": ["image", "ai", "generation"],
        "port": 0,
    },
    "aws-kb-retrieval": {
        "name": "aws-kb-retrieval",
        "description": "AWS Knowledge Base MCP — Bedrock retrieval augmented generation",
        "repo": "modelcontextprotocol/servers",
        "subdir": "src/aws-kb-retrieval",
        "type": "node",
        "entry": "dist/index.js",
        "tags": ["aws", "rag", "bedrock"],
        "port": 0,
    },
    "google-maps": {
        "name": "google-maps",
        "description": "Google Maps MCP — geocoding, directions, places search",
        "repo": "modelcontextprotocol/servers",
        "subdir": "src/google-maps",
        "type": "node",
        "entry": "dist/index.js",
        "tags": ["maps", "location", "google"],
        "port": 0,
    },
}


class Market:
    """MCP tool marketplace — discover, install, and register services."""

    INSTALL_DIR = Path.home() / ".agora" / "market"

    def _get_market(self) -> dict[str, dict]:
        """Get market registry either from bos://forge or fallback to BUILTIN_MARKET."""
        try:
            import httpx

            # Try to read the dynamic registry from Agora gateway
            resp = httpx.post(
                "http://127.0.0.1:8080/v1/resources/read",
                json={"uri": "bos://forge/market/list"},
                timeout=2.0,
            )
            if resp.status_code == 200:
                import json

                data = resp.json().get("content", [{}])[0].get("text", "{}")
                forge_market = json.loads(data)
                if forge_market:
                    return {**BUILTIN_MARKET, **forge_market}
        except Exception as e:
            logger.debug(
                "Failed to fetch dynamic market from bos://forge, using builtin",
                error=str(e),
            )
        return BUILTIN_MARKET

    def search(self, query: str) -> list[dict]:
        """Search the market by keyword."""
        q = query.lower()
        results = []
        market_data = self._get_market()
        for info in market_data.values():
            if (
                q in info["name"].lower()
                or q in info["description"].lower()
                or any(q in t.lower() for t in info.get("tags", []))
            ):
                results.append(info)
        return results

    def list_all(self) -> list[dict]:
        """List all available MCP services in the market."""
        return list(self._get_market().values())

    def install(self, name_or_url: str) -> dict:
        """Install an MCP service from the market or GitHub URL.

        Returns metadata for registration.
        """
        market_data = self._get_market()
        if name_or_url in market_data:
            info = market_data[name_or_url]
            repo = info["repo"]
            subdir = info.get("subdir", "")
        else:
            # Treat as GitHub repo URL or shorthand
            repo = name_or_url.replace("https://github.com/", "").rstrip("/")
            # Look for metadata
            info = self._fetch_repo_metadata(repo)
            subdir = ""

        install_path = self.INSTALL_DIR / repo.replace("/", "__")
        if not install_path.exists():
            # Clone repo
            url = f"https://github.com/{repo}.git"
            self._run_cmd(["git", "clone", "--depth", "1", url, str(install_path)])

        # Build / install based on type
        svc_type = info.get("type", "python")
        entry_path = install_path
        if subdir:
            entry_path = install_path / subdir

        if svc_type == "node":
            self._run_cmd(["npm", "install", "--production"], cwd=str(entry_path))
        elif svc_type == "python":
            pip = Path(sys.prefix) / "bin" / "pip"
            if not pip.exists():
                pip = Path(sys.prefix) / "bin" / "pip3"
            self._run_cmd([str(pip), "install", "-e", "."], cwd=str(entry_path))

        return {
            "name": info["name"],
            "description": info["description"],
            "entry": str(entry_path / info["entry"]),
            "type": svc_type,
            "port": info.get("port", 0),
            "tags": info.get("tags", []),
        }

    def _fetch_repo_metadata(self, repo: str) -> dict:
        """Fetch repo metadata from GitHub API."""
        import httpx

        try:
            r = httpx.get(f"https://api.github.com/repos/{repo}", timeout=10)
            if r.status_code == 200:
                data = r.json()
                return {
                    "name": data.get("name", repo.split("/")[-1]),
                    "description": data.get("description", ""),
                    "type": "python",  # default
                    "entry": "server.py",
                    "tags": ["github", "mcp"],
                }
        except Exception:
            pass
        return {
            "name": repo.split("/")[-1],
            "description": "",
            "type": "python",
            "entry": "server.py",
            "tags": [],
        }

    def publish(
        self,
        name: str,
        repo: str,
        description: str = "",
        entry: str = "server.py",
        svc_type: str = "python",
        tags: list[str] | None = None,
    ) -> dict:
        """Publish an MCP service to the market.

        Returns metadata for registration.
        """
        entry_data = {
            "name": name,
            "description": description or f"MCP service: {name}",
            "repo": repo,
            "type": svc_type,
            "entry": entry,
            "tags": tags or [],
            "port": 0,
        }
        # Persist to local market registry
        from agora.persistence import json_load, json_save  # type: ignore[import-not-found]

        market_path = self.INSTALL_DIR / "published.json"
        existing = json_load(market_path, default={})
        existing[name] = entry_data
        if not json_save(market_path, existing):
            logger.warning("market_publish_failed", name=name)
            raise RuntimeError(f"Failed to publish {name}")
        return entry_data

    def _load_published(self) -> dict:
        """Load all published services from local registry."""
        from agora.persistence import json_load

        return json_load(self.INSTALL_DIR / "published.json", default={})

    @staticmethod
    def _run_cmd(cmd: list[str], cwd: str | None = None):
        """Run a shell command, raise on failure."""
        result = subprocess.run(
            cmd, cwd=cwd, capture_output=True, text=True, timeout=120
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"Command failed: {' '.join(cmd)}\n{result.stderr[:500]}"
            )
