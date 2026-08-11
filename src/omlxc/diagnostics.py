"""Read-only direct diagnostics used when the daemon is unavailable."""

from __future__ import annotations

import asyncio
import os
import stat
from pathlib import Path
from typing import Any

from omlxc.config import AppConfig
from omlxc.daemon.composition import (
    build_configured_adapter,
    build_configured_tailscale,
    is_loopback_url,
)
from omlxc.service import LaunchdPaths


async def run_direct_doctor(config: AppConfig) -> dict[str, Any]:
    """Inspect configured surfaces without creating state or mutating services."""
    checks: list[dict[str, object]] = [{"name": "config", "ok": True}]
    paths = LaunchdPaths.for_home(Path.home())
    checks.append(_private_path_check("launchd_plist", paths.plist_path, expected_mode=0o600))
    checks.append(
        _private_path_check("daemon_socket", config.daemon.socket_path, expected_mode=0o600)
    )

    tailscale = build_configured_tailscale(config)
    if config.tailscale is not None:
        if tailscale is None:
            checks.append({"name": "tailscale", "ok": False, "detail": "configuration unavailable"})
        else:
            try:
                await tailscale.snapshot()
                checks.append({"name": "tailscale", "ok": True})
            except asyncio.CancelledError:
                raise
            except Exception:
                checks.append({"name": "tailscale", "ok": False, "detail": "identity check failed"})

    nodes = {node.id: node for node in config.nodes}
    for backend in config.backends:
        adapter = None
        try:
            try:
                adapter = build_configured_adapter(backend)
                if not is_loopback_url(backend.base_url):
                    node = nodes[backend.node_id]
                    if node.tailscale is None or tailscale is None:
                        raise PermissionError
                    tailscale.authorize_http(node.id, backend.base_url)
                await adapter.discover()
                checks.append({"name": f"backend:{backend.id}", "ok": True})
            except asyncio.CancelledError:
                raise
            except Exception:
                checks.append(
                    {
                        "name": f"backend:{backend.id}",
                        "ok": False,
                        "detail": "read-only probe failed",
                    }
                )
        finally:
            close = getattr(adapter, "aclose", None) if adapter is not None else None
            if close is not None:
                await asyncio.gather(close(), return_exceptions=True)
    healthy = all(bool(check["ok"]) for check in checks)
    return {"status": "healthy" if healthy else "degraded", "checks": checks}


def _private_path_check(name: str, path: Path, *, expected_mode: int) -> dict[str, object]:
    try:
        metadata = path.lstat()
    except FileNotFoundError:
        return {"name": name, "ok": False, "detail": "missing"}
    except OSError:
        return {"name": name, "ok": False, "detail": "unreadable"}
    mode = stat.S_IMODE(metadata.st_mode)
    ok = not stat.S_ISLNK(metadata.st_mode) and metadata.st_uid == os.geteuid()
    if name == "daemon_socket":
        ok = ok and stat.S_ISSOCK(metadata.st_mode)
    else:
        ok = ok and stat.S_ISREG(metadata.st_mode)
    ok = ok and mode == expected_mode
    return {"name": name, "ok": ok, "detail": "ok" if ok else "unsafe permissions or type"}
