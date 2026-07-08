#!/usr/bin/env python3
"""P77 Phase 7e — Batch migrate remaining hardcoded ports to env vars.

Targets submodules: agora, cockpit, kairon, ecos
Ports: 8090→COCKPIT_DASHBOARD_PORT, 7431→AGORA_MCP_SSE_PORT, 9190→OMO_DASHBOARD_PORT,
       9876→RUNTIME_L1_PORT, 8080→ONTODERIVE_WEB_PORT, 7420→BOS_API_PORT
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENV = {
    8090: "COCKPIT_DASHBOARD_PORT",
    7431: "AGORA_MCP_SSE_PORT",
    9190: "OMO_DASHBOARD_PORT",
    9876: "RUNTIME_L1_PORT",
    8080: "ONTODERIVE_WEB_PORT",
    7420: "BOS_API_PORT",
}

# {(submodule, relative_path): [(old, new), ...]}
REPLACEMENTS: dict[tuple[str, str], list[tuple[str, str]]] = {
    # --- agora ---
    ("agora", "src/agora/web/dashboard.py"): [
        ('COCKPIT_DASHBOARD_URL = "http://localhost:8090"',
         'COCKPIT_DASHBOARD_URL = os.environ.get("COCKPIT_DASHBOARD_URL", f"http://localhost:{os.environ.get(\'COCKPIT_DASHBOARD_PORT\', \'8090\')}")'),
    ],
    ("agora", "src/agora/server/tools_proxy.py"): [
        ("http://localhost:7420/mcp'",
         "http://localhost:{os.environ.get('BOS_API_PORT', '7420')}/mcp'"),
    ],
    # --- cockpit ---
    ("cockpit", "src/cockpit/commands/base.py"): [
        ('"AGORA_ENDPOINT", "http://localhost:7430"',
         '"AGORA_ENDPOINT", f"http://localhost:{os.environ.get(\'AGORA_INTERNAL_PORT\', \'7430\')}"'),
    ],
    ("cockpit", "src/cockpit/dashboard/constants.py"): [
        ('"url": "http://localhost:7431/v1/health", "port": 7431',
         '"url": f"http://localhost:{os.environ.get(\'AGORA_MCP_SSE_PORT\', \'7431\')}/v1/health", "port": int(os.environ.get("AGORA_MCP_SSE_PORT", "7431"))'),
        ('"url": "http://localhost:9190/api/v1/status", "port": 9190',
         '"url": f"http://localhost:{os.environ.get(\'OMO_DASHBOARD_PORT\', \'9190\')}/api/v1/status", "port": int(os.environ.get("OMO_DASHBOARD_PORT", "9190"))'),
        ('"url": "http://localhost:9876/api/v1/status", "port": 9876',
         '"url": f"http://localhost:{os.environ.get(\'RUNTIME_L1_PORT\', \'9876\')}/api/v1/status", "port": int(os.environ.get("RUNTIME_L1_PORT", "9876"))'),
        ('<a href="http://localhost:7430">&#x2197; Agora (I0)</a>',
         '<a href="http://localhost:{os.environ.get(\'AGORA_INTERNAL_PORT\', \'7430\')}">&#x2197; Agora (I0)</a>'),
        ('<a href="http://localhost:9876">&#x2197; Runtime (L1)</a>',
         '<a href="http://localhost:{os.environ.get(\'RUNTIME_L1_PORT\', \'9876\')}">&#x2197; Runtime (L1)</a>'),
    ],
    # --- kairon ---
    ("kairon", "packages/eidos/src/eidos/adapters/eidos_to_bos.py"): [
        ('"AGORA_MCP_ENDPOINT", "http://localhost:7422"',
         '"AGORA_MCP_ENDPOINT", f"http://localhost:{os.environ.get(\'AGORA_MCP_HTTP_PORT\', \'7422\')}"'),
    ],
    ("kairon", "packages/forge/src/forge/entropy/healing_trigger.py"): [
        ('"AGORA_ENDPOINT", "http://localhost:7430"',
         '"AGORA_ENDPOINT", f"http://localhost:{os.environ.get(\'AGORA_INTERNAL_PORT\', \'7430\')}"'),
    ],
    ("kairon", "packages/kairon-observability/src/kairon_observability/vibeops.py"): [
        ('os.environ.get("AGORA_HTTP_PORT", "http://localhost:8080")',
         'os.environ.get("AGORA_HTTP_PORT", f"http://localhost:{os.environ.get(\'ONTODERIVE_WEB_PORT\', \'8080\')}")'),
    ],
    ("kairon", "packages/minerva/src/minerva/cli.py"): [
        ('httpx.get("http://localhost:8080/health", timeout=5)',
         'httpx.get(f"http://localhost:{os.environ.get(\'ONTODERIVE_WEB_PORT\', \'8080\')}/health", timeout=5)'),
        ('print("  ✅ SearXNG running (localhost:8080)")',
         'print(f"  ✅ SearXNG running (localhost:{os.environ.get(\'ONTODERIVE_WEB_PORT\', \'8080\')})" )'),
    ],
    ("kairon", "packages/minerva/src/minerva/search/engine.py"): [
        ('"searxng_url", "http://localhost:8080"',
         '"searxng_url", f"http://localhost:{os.environ.get(\'ONTODERIVE_WEB_PORT\', \'8080\')}"'),
    ],
    ("kairon", "packages/minerva/src/minerva/search/backends.py"): [
        ('base_url: str = "http://localhost:8080"',
         'base_url: str = f"http://localhost:{os.environ.get(\'ONTODERIVE_WEB_PORT\', \'8080\')}"'),
    ],
    # --- ecos ---
    ("ecos", "src/ecos/cli/dashboard.py"): [
        ('"Web dashboard: http://localhost:8090/api/ecos/status"',
         '"Web dashboard: http://localhost:{COCKPIT_DASHBOARD_PORT}/api/ecos/status"'),
    ],
}

for (submodule, filepath), replacements in REPLACEMENTS.items():
    fp = ROOT / "projects" / submodule / filepath
    text = fp.read_text(encoding="utf-8")
    for old, new in replacements:
        if old in text:
            text = text.replace(old, new)
            print(f"  ✅ {submodule}/{filepath}")
        else:
            print(f"  ⚠️  {submodule}/{filepath}: not found: {old[:50]}")
    fp.write_text(text, encoding="utf-8")

print("\nDone.")
