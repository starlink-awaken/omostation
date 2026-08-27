#!/usr/bin/env python3
"""KOS External Tool Adapters — version-aware, resilient integrations.

Usage:
    from kos_adapters import MinervaAdapter
    adapter = MinervaAdapter.discover()
    if adapter:
        result = adapter.research("query", level="L2")
    else:
        # graceful fallback
"""

from __future__ import annotations

import json
import os
import re
import subprocess as sp
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# ── Minerva Adapter ──────────────────────────────────────


@dataclass(frozen=True)
class MinervaVersion:
    major: int
    minor: int
    patch: int
    raw: str

    @classmethod
    def parse(cls, text: str) -> MinervaVersion | None:
        """Parse version from text like 'minerva 1.2.3' or '1.2.3'."""
        m = re.search(r"(\d+)\.(\d+)\.(\d+)", text)
        if not m:
            return None
        return cls(int(m.group(1)), int(m.group(2)), int(m.group(3)), text.strip())

    def __ge__(self, other: tuple[int, int, int]) -> bool:
        return (self.major, self.minor, self.patch) >= other

    def __lt__(self, other: tuple[int, int, int]) -> bool:
        return (self.major, self.minor, self.patch) < other


class MinervaAdapter:
    """Version-aware Minerva CLI adapter with dynamic discovery.

    Supports multiple Minerva installation layouts:
      - ~/Workspace/minerva/.venv/bin/minerva
      - /usr/local/bin/minerva
      - ~/.local/bin/minerva
      - pip-installed module (python -m minerva)
      - MINERVA_EXE env var override
      - MINERVA_HOME env var base directory
    """

    # CLI argument compatibility matrix by version
    # (major, minor, patch) -> arg builder
    _ARG_BUILDERS: dict[tuple[int, int, int], Callable] = {}  # type: ignore[type-arg]

    def __init__(self, exe: Path, version: MinervaVersion, via_module: bool = False) -> None:
        self.exe = exe
        self.version = version
        self.via_module = via_module
        self._checked = False

    def __repr__(self) -> str:  # type: ignore[override]
        src = "module" if self.via_module else str(self.exe)
        return f"<MinervaAdapter {self.version.raw} via {src}>"  # type: ignore[return-value]

    # ── Discovery ─────────────────────────────────────────

    @classmethod
    def discover(cls) -> MinervaAdapter | None:
        """Probe all known installation methods and return best match."""
        candidates = []

        # 1. Env override (highest priority)
        env_exe = os.environ.get("MINERVA_EXE")
        if env_exe:
            p = Path(env_exe)
            if p.exists():
                v = cls._probe_exe(p)
                if v:
                    candidates.append((p, v, False))

        # 2. Env home directory
        env_home = os.environ.get("MINERVA_HOME")
        if env_home:
            p = Path(env_home) / ".venv" / "bin" / "minerva"
            if p.exists() and p not in [c[0] for c in candidates]:
                v = cls._probe_exe(p)
                if v:
                    candidates.append((p, v, False))

        # 3. Standard paths
        for p in [
            Path.home() / "Workspace" / "minerva" / ".venv" / "bin" / "minerva",
            Path("/usr/local/bin/minerva"),
            Path.home() / ".local" / "bin" / "minerva",
        ]:
            if p.exists() and p not in [c[0] for c in candidates]:
                v = cls._probe_exe(p)
                if v:
                    candidates.append((p, v, False))

        # 4. pip module fallback
        module_version = cls._probe_module()
        if module_version:
            candidates.append((Path(sys.executable), module_version, True))

        if not candidates:
            return None

        # Pick newest version; tie-break: non-module over module
        candidates.sort(key=lambda c: (c[1].major, c[1].minor, c[1].patch, not c[2]))
        best = candidates[-1]
        return cls(best[0], best[1], via_module=best[2])

    @classmethod
    def _probe_exe(cls, path: Path) -> MinervaVersion | None:
        """Try to get version from executable."""
        for flag in ["--version", "-V", "version"]:
            try:
                r = sp.run([str(path), flag], capture_output=True, text=True, timeout=5)
                if r.returncode in (0, 1):  # some CLIs print version even on exit 1
                    v = MinervaVersion.parse(r.stdout + r.stderr)
                    if v:
                        return v
            except Exception:  # defensive fallback  # noqa: S112
                continue
        return None

    @classmethod
    def _probe_module(cls) -> MinervaVersion | None:
        """Try to detect minerva as an importable module."""
        try:
            r = sp.run([sys.executable, "-m", "minerva", "--version"], capture_output=True, text=True, timeout=5)
            if r.returncode in (0, 1):
                v = MinervaVersion.parse(r.stdout + r.stderr)
                if v:
                    return v
        except Exception:
            pass

        # fallback: pip show
        try:
            r = sp.run([sys.executable, "-m", "pip", "show", "minerva"], capture_output=True, text=True, timeout=5)
            if r.returncode == 0:
                for line in r.stdout.splitlines():
                    if line.startswith("Version:"):
                        v = MinervaVersion.parse(line)
                        if v:
                            return v
        except Exception:
            pass
        return None

    # ── Health check ──────────────────────────────────────

    def health(self) -> dict:  # type: ignore[type-arg]
        """Return health status dict."""
        return {
            "available": True,
            "version": self.version.raw,
            "path": str(self.exe),
            "via_module": self.via_module,
        }

    # ── Command builders ──────────────────────────────────

    def _build_research_args(self, query: str, level: str = "L2", max_cost: float = 1.0) -> list[str]:
        """Build research command args adapted to detected version."""
        # Future-proof: if Minerva ever changes CLI args, add version branches here
        # e.g. if self.version >= (2, 0, 0): return [...new args...]
        if self.via_module:
            args = [sys.executable, "-m", "minerva", "research", query]
        else:
            args = [str(self.exe), "research", query]
        args.extend(["--level", level])
        # Only add --max-cost if version supports it (assumed >= 1.0.0)
        if self.version >= (1, 0, 0):
            args.extend(["--max-cost", str(max_cost)])
        return args

    # ── Operations ────────────────────────────────────────

    def research(
        self, query: str, level: str = "L2", max_cost: float = 1.0, timeout: int = 600, cwd: str | None = None
    ) -> dict:  # type: ignore[type-arg]
        """Execute Minerva research with fallback-aware result."""
        args = self._build_research_args(query, level, max_cost)
        try:
            r = sp.run(
                args,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=cwd or str(Path.home() / "Workspace" / "minerva"),
            )
            return {
                "query": query,
                "level": level,
                "backend": "minerva",
                "version": self.version.raw,
                "success": r.returncode == 0,
                "output": r.stdout[-5000:] if r.stdout else "",
                "errors": r.stderr[-500:] if r.stderr else "",
            }
        except sp.TimeoutExpired:
            return {"error": f"Minerva research timed out (>{timeout}s)", "query": query}
        except Exception as e:
            return {"error": str(e), "query": query}

    def quick_llm(self, prompt: str, timeout: int = 60) -> str | None:
        """Fire a quick L0 research prompt and return raw text."""
        args = self._build_research_args(prompt, level="L0", max_cost=0.1)
        try:
            r = sp.run(args, capture_output=True, text=True, timeout=timeout)
            if r.returncode == 0:
                return r.stdout.strip()
        except Exception:
            pass
        return None


# ── Sentinel / Null Adapter ──────────────────────────────


class _NullMinerva:
    """Drop-in null object when Minerva is absent."""

    version = None
    via_module = False

    def health(self) -> dict[str, Any]:
        return {"available": False}  # type: ignore[return-value]

    def research(self, query, **kw) -> None:  # type: ignore[no-untyped-def]
        return {"error": "Minerva not available. Install: pip install minerva", "query": query}  # type: ignore[return-value]

    def quick_llm(self, prompt, **kw) -> None:  # type: ignore[no-untyped-def]
        return None


NullMinerva = _NullMinerva()


# ── MCP Protocol Helpers ─────────────────────────────────

SUPPORTED_MCP_VERSIONS = ["2024-11-05"]


def negotiate_mcp_protocol(client_version: str | None) -> str:
    """Negotiate a mutually compatible MCP protocol version.

    If client requests a version we don't support, fall back to the newest
    version we do support. MCP spec guarantees backward compatibility within
    major versions.
    """
    if not client_version:
        return SUPPORTED_MCP_VERSIONS[0]
    if client_version in SUPPORTED_MCP_VERSIONS:
        return client_version
    client_major = client_version.rsplit(".", 1)[0] if "." in client_version else client_version
    for v in SUPPORTED_MCP_VERSIONS:
        if v.startswith(client_major):
            return v
    return SUPPORTED_MCP_VERSIONS[0]


# ── Semantic Scholar Adapter ─────────────────────────────


class SemanticScholarAdapter:
    """Rate-limited, schema-validated Semantic Scholar API client."""

    BASE = "https://api.semanticscholar.org/graph/v1"
    DEFAULT_FIELDS = "title,abstract,year,authors,externalIds,url,citationCount"

    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = api_key or os.environ.get("S2_API_KEY", "")
        self.headers = {"User-Agent": "eCOS-KOS/1.1"}
        if self.api_key:
            self.headers["x-api-key"] = self.api_key
        self._last_call = 0.0
        self._rate_limit = 0.1 if self.api_key else 1.0

    def _wait_rate_limit(self) -> None:
        import time

        elapsed = time.time() - self._last_call
        if elapsed < self._rate_limit:
            time.sleep(self._rate_limit - elapsed)

    def search(self, query: str, limit: int = 5) -> dict:  # type: ignore[type-arg]
        """Search papers with validated response."""
        import urllib.error
        import urllib.parse
        import urllib.request

        self._wait_rate_limit()
        url = f"{self.BASE}/paper/search"
        params = {"query": query, "limit": limit, "fields": self.DEFAULT_FIELDS}
        url += "?" + urllib.parse.urlencode(params)
        req = urllib.request.Request(url, headers=self.headers)
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                self._last_call = __import__("time").time()
                data = json.loads(resp.read())
        except urllib.error.HTTPError as e:
            if e.code == 429:
                # Retry once after backoff
                __import__("time").sleep(2.0)
                with urllib.request.urlopen(req, timeout=15) as resp:
                    data = json.loads(resp.read())
            else:
                return {"error": f"HTTP {e.code}", "detail": str(e)}
        except Exception as e:
            return {"error": str(e)}

        # Schema validation / defensive parsing
        if not isinstance(data, dict):
            return {"error": "Unexpected response type", "papers": [], "count": 0}

        raw_papers = data.get("data")
        if raw_papers is None:
            # API may have changed: check for alternative keys
            raw_papers = data.get("papers") or data.get("results") or []
        if not isinstance(raw_papers, list):
            return {"error": "Unexpected 'data' field type", "papers": [], "count": 0}

        papers = []
        for p in raw_papers[:limit]:
            if not isinstance(p, dict):
                continue
            authors = p.get("authors") or []
            if isinstance(authors, list):
                author_names = [a.get("name", "") if isinstance(a, dict) else str(a) for a in authors]
            else:
                author_names = []
            papers.append(
                {
                    "title": p.get("title") or "",
                    "year": p.get("year"),
                    "authors": author_names,
                    "citations": p.get("citationCount") or 0,
                    "url": p.get("url") or "",
                    "abstract": (p.get("abstract") or "")[:300],
                }
            )

        return {"papers": papers, "count": len(papers), "query": query}
