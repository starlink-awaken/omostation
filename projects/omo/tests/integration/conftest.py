"""Integration test fixtures and hooks.

Provides automatic skip logic for tests that require live agora downstream
services (minerva, ontoderive, iris, etc.).
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

AGORA_ROOT = Path("/Users/xiamingxing/Workspace/projects/agora")


def _agora_services_available() -> bool:
    """Probe whether agora downstream services are reachable via stdio."""
    try:
        code = (
            "import json; "
            "from agora.mcp.bos_resolver import invoke_stdio; "
            "r = invoke_stdio('bos://analysis/minerva/research', 'research', args=['probe']); "
            "print(json.dumps(r, ensure_ascii=False, default=str))"
        )
        r = subprocess.run(
            ["uv", "run", "--directory", str(AGORA_ROOT), "python", "-c", code],
            capture_output=True,
            text=True,
            timeout=15,
        )
        if r.returncode != 0:
            return False
        out = r.stdout.strip()
        lines = [ln for ln in out.splitlines() if ln.startswith("{")]
        if not lines:
            return False
        payload = json.loads(lines[-1])
        return payload.get("status") == "ok"
    except Exception:
        return False


# Cache the probe result once per session
_AGORA_LIVE = _agora_services_available()


def pytest_collection_modifyitems(
    config: pytest.Config, items: list[pytest.Item]
) -> None:
    """Skip integration-markered tests when agora downstream is unavailable."""
    for item in items:
        if item.get_closest_marker("integration") and not _AGORA_LIVE:
            item.add_marker(
                pytest.mark.skip(reason="agora downstream services not available")
            )
