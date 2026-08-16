"""Optional live KOS / gbrain backends (ADR-0372 Phase 10).

Gated by env — never hard-fail the control plane:

  MOS_LIVE_KOS=1       → HTTP search against KOS REST (KOS_API_URL)
  MOS_LIVE_GBRAIN=1    → subprocess `gbrain search` / `gbrain query`
  MOS_LIVE_GBRAIN_WRITE=1 → on semantic write, best-effort `gbrain put`

When flags are off or backends unavailable, callers keep fixture/InMemory paths.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


def _flag(name: str, default: str = "0") -> bool:
    val = (os.environ.get(name) or default).strip().lower()
    return val not in {"0", "false", "off", "no", ""}


def live_kos_enabled() -> bool:
    return _flag("MOS_LIVE_KOS")


def live_gbrain_enabled() -> bool:
    return _flag("MOS_LIVE_GBRAIN")


def live_gbrain_write_enabled() -> bool:
    return _flag("MOS_LIVE_GBRAIN_WRITE")


def kos_api_url() -> str:
    return (os.environ.get("KOS_API_URL") or "http://localhost:8766").rstrip("/")


def _workspace() -> Path:
    env = os.environ.get("ECOS_WORKSPACE") or os.environ.get("WORKSPACE_ROOT")
    if env:
        return Path(env)
    # packages/mos/src/mos/adapters/live_backends.py → parents[6] ≈ workspace
    return Path(__file__).resolve().parents[6]


@dataclass
class LiveKosSearchBackend:
    """HTTP GET KOS REST /api/v1/search when MOS_LIVE_KOS=1."""

    name: str = "kos"
    base_url: str | None = None
    timeout_sec: float = 5.0
    # injectable for tests: (path, params) -> dict/list
    http_get: Callable[[str, dict[str, str]], Any] | None = None
    last_error: str | None = field(default=None, init=False)

    def available(self) -> bool:
        if not live_kos_enabled():
            return False
        try:
            hits = self.search("__mos_probe__", limit=1)
            _ = hits
            return self.last_error is None
        except Exception as exc:
            self.last_error = str(exc)
            return False

    def search(
        self,
        query: str,
        *,
        limit: int = 10,
        scope: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        _ = scope
        self.last_error = None
        if not live_kos_enabled():
            return []
        base = (self.base_url or kos_api_url()).rstrip("/")
        params = {"q": query or "", "limit": str(int(limit))}
        path = f"{base}/api/v1/search"
        try:
            if self.http_get is not None:
                raw = self.http_get(path, params)
            else:
                raw = self._http_get(path, params)
        except Exception as exc:
            self.last_error = str(exc)
            return []
        return self._normalize(raw, limit=limit)

    def _http_get(self, url: str, params: dict[str, str]) -> Any:
        qs = urllib.parse.urlencode(params)
        full = f"{url}?{qs}" if qs else url
        req = urllib.request.Request(full, headers={"Accept": "application/json"}, method="GET")  # noqa: S310
        try:
            with urllib.request.urlopen(req, timeout=self.timeout_sec) as resp:  # noqa: S310
                body = resp.read().decode("utf-8", errors="replace")
        except urllib.error.URLError as exc:
            self.last_error = f"kos_unreachable:{exc}"
            raise
        try:
            return json.loads(body)
        except json.JSONDecodeError:
            return {"raw": body}

    def _normalize(self, raw: Any, *, limit: int) -> list[dict[str, Any]]:
        items: list[Any]
        if isinstance(raw, list):
            items = raw
        elif isinstance(raw, dict):
            items = raw.get("results") or raw.get("hits") or raw.get("items") or raw.get("data") or []
            if not items and raw.get("error"):
                self.last_error = str(raw.get("error"))
                return []
        else:
            items = []
        out: list[dict[str, Any]] = []
        for it in items[:limit]:
            if not isinstance(it, dict):
                continue
            out.append(
                {
                    "id": it.get("id") or it.get("doc_id") or it.get("canonical_path") or it.get("path"),
                    "title": it.get("title") or it.get("name") or it.get("id") or "kos",
                    "snippet": it.get("snippet") or it.get("content") or it.get("text") or "",
                    "path": it.get("path") or it.get("canonical_path"),
                    "backend": self.name,
                    "score": float(it.get("score") or it.get("rank") or 0.5),
                    "live": True,
                }
            )
        return out


@dataclass
class LiveGbrainSearchBackend:
    """Subprocess gbrain search/query when MOS_LIVE_GBRAIN=1."""

    name: str = "gbrain"
    workspace: Path | None = None
    timeout_sec: float = 30.0
    use_query: bool = False  # True → hybrid `query`; False → keyword `search`
    # injectable: (cmd list) -> stdout str
    run_cmd: Callable[[list[str]], str] | None = None
    last_error: str | None = field(default=None, init=False)

    def available(self) -> bool:
        if not live_gbrain_enabled():
            return False
        ws = self.workspace or _workspace()
        cli = ws / "projects" / "gbrain" / "src" / "cli.ts"
        return cli.is_file() and shutil.which("bun") is not None

    def search(
        self,
        query: str,
        *,
        limit: int = 10,
        scope: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        _ = scope
        self.last_error = None
        if not live_gbrain_enabled():
            return []
        if not self.available() and self.run_cmd is None:
            self.last_error = "gbrain_cli_or_bun_missing"
            return []
        ws = self.workspace or _workspace()
        cli = ws / "projects" / "gbrain" / "src" / "cli.ts"
        bun = shutil.which("bun") or "bun"
        op = "query" if self.use_query else "search"
        cmd = [bun, "run", str(cli), op, query or "", "--limit", str(int(limit))]
        try:
            if self.run_cmd is not None:
                stdout = self.run_cmd(cmd)
            else:
                proc = subprocess.run(
                    cmd,
                    cwd=str(ws / "projects" / "gbrain"),
                    capture_output=True,
                    text=True,
                    timeout=self.timeout_sec,
                    check=False,
                )
                if proc.returncode != 0:
                    self.last_error = (proc.stderr or proc.stdout or "gbrain_failed")[:300]
                    return []
                stdout = proc.stdout or ""
        except Exception as exc:
            self.last_error = str(exc)
            return []
        return self._parse_output(stdout, limit=limit)

    def _parse_output(self, stdout: str, *, limit: int) -> list[dict[str, Any]]:
        text = (stdout or "").strip()
        if not text:
            return []
        # Prefer JSON array / object
        try:
            data = json.loads(text)
            if isinstance(data, list):
                return LiveKosSearchBackend(name=self.name)._normalize(data, limit=limit)
            if isinstance(data, dict):
                return LiveKosSearchBackend(name=self.name)._normalize(data, limit=limit)
        except json.JSONDecodeError:
            pass
        # JSONL
        hits: list[dict[str, Any]] = []
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
                if isinstance(obj, dict):
                    hits.extend(LiveKosSearchBackend(name=self.name)._normalize([obj], limit=limit))
                    continue
            except json.JSONDecodeError:
                pass
            # Markdown / plain: "- slug: title" or "slug — snippet"
            m = re.match(r"^[-*]?\s*([^\s:]+)[:\s—-]+(.+)$", line)
            if m:
                hits.append(
                    {
                        "id": m.group(1),
                        "title": m.group(1),
                        "snippet": m.group(2).strip(),
                        "backend": self.name,
                        "score": 0.5,
                        "live": True,
                    }
                )
            elif line and not line.startswith("#"):
                hits.append(
                    {
                        "id": f"gbrain_{len(hits)}",
                        "title": line[:80],
                        "snippet": line,
                        "backend": self.name,
                        "score": 0.4,
                        "live": True,
                    }
                )
            if len(hits) >= limit:
                break
        return hits[:limit]


def gbrain_put_page(
    slug: str,
    content: str,
    *,
    workspace: Path | None = None,
    timeout_sec: float = 60.0,
    run_cmd: Callable[[list[str]], tuple[int, str, str]] | None = None,
) -> dict[str, Any]:
    """Best-effort gbrain put for dual-write theta enrichment."""
    if not live_gbrain_write_enabled():
        return {"ok": False, "skipped": True, "reason": "live_gbrain_write_off"}
    ws = workspace or _workspace()
    cli = ws / "projects" / "gbrain" / "src" / "cli.ts"
    bun = shutil.which("bun") or "bun"
    # frontmatter-light body
    body = content if content.lstrip().startswith("---") else f"---\ntitle: {slug}\n---\n\n{content}\n"
    cmd = [bun, "run", str(cli), "put", slug, "--content", body]
    try:
        if run_cmd is not None:
            code, out, err = run_cmd(cmd)
        else:
            if not cli.is_file() or not shutil.which("bun"):
                return {"ok": False, "skipped": True, "reason": "gbrain_cli_or_bun_missing"}
            proc = subprocess.run(
                cmd,
                cwd=str(ws / "projects" / "gbrain"),
                capture_output=True,
                text=True,
                timeout=timeout_sec,
                check=False,
            )
            code, out, err = proc.returncode, proc.stdout or "", proc.stderr or ""
        if code != 0:
            return {"ok": False, "error": (err or out or "put_failed")[:300], "slug": slug}
        return {"ok": True, "slug": slug, "store": "gbrain"}
    except Exception as exc:
        return {"ok": False, "error": str(exc), "slug": slug}


def live_status_snapshot() -> dict[str, Any]:
    """Honest adapter posture for mos.status()."""
    _kos = LiveKosSearchBackend()
    gbrain = LiveGbrainSearchBackend()
    return {
        "kos": {
            "flag": live_kos_enabled(),
            "url": kos_api_url() if live_kos_enabled() else None,
            "status": ("live_enabled" if live_kos_enabled() else "fixture_or_partial"),
        },
        "gbrain": {
            "flag": live_gbrain_enabled(),
            "write_flag": live_gbrain_write_enabled(),
            "cli_available": gbrain.available() if live_gbrain_enabled() else False,
            "status": ("live_enabled" if live_gbrain_enabled() else "fixture_or_partial"),
        },
    }
