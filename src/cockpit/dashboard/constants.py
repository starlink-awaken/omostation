"""Paths, config, HTML templates for the Cockpit Dashboard."""

from __future__ import annotations

import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent  # cockpit/src/cockpit/
WORKSPACE_ROOT = Path.home() / "Workspace"
OMO_ROOT = Path.home() / "Workspace/projects/omo"
RUNTIME_HOME = Path(os.environ.get("RUNTIME_HOME", str(Path.home() / "runtime")))
M0_SNAPSHOT_PATH = Path.home() / "Workspace/projects/ecos/src/ecos/ssot/mof/m0/snapshot.yaml"
COCKPIT_UI_DIST = Path.home() / "Workspace/projects/cockpit-ui/dist"
PROVIDER_PLANE_PATH = WORKSPACE_ROOT / ".omo" / "state" / "provider-plane.yaml"
LLM_QUOTA_SUMMARY_PATH = RUNTIME_HOME / "data" / "llm_quota_summary.json"
LLM_COST_LOG_PATH = RUNTIME_HOME / "data" / "llm_cost.jsonl"
BOS_METRICS_PATH = WORKSPACE_ROOT / ".omo" / "_knowledge" / "bos-metrics.jsonl"

# ─── Layer sources (I0, L2, L1, L0) ────────────────────────
LAYER_SOURCES: list[dict] = [
    {"layer": "I0", "name": "agora", "url": "http://localhost:7431/v1/health", "port": 7431},
    {"layer": "L2", "name": "omo", "url": "http://localhost:9190/api/v1/status", "port": 9190},
    {"layer": "L1", "name": "runtime", "url": "http://localhost:9876/api/v1/status", "port": 9876},
    {"layer": "L0", "name": "ecos", "url": "file://m0_snapshot", "port": None, "source": "m0_snapshot"},
]

DEFAULT_COMPUTE_TOPOLOGY = [
    {"id": "local-mac", "label": "Local-Mac", "kind": "local", "role": "Cockpit / Agent host"},
    {"id": "macmini-ollama", "label": "MacMini (Ollama)", "kind": "local", "role": "Local inference"},
    {"id": "y7000p-lmstudio", "label": "Y7000P (LMStudio)", "kind": "local", "role": "GPU workstation"},
    {"id": "cloud-cc-switch", "label": "Cloud (cc-switch)", "kind": "cloud", "role": "Remote provider relay"},
]

PORT = int(os.environ.get("COCKPIT_DASHBOARD_PORT", "8090"))
DASHBOARD_TOKEN = os.environ.get("COCKPIT_DASHBOARD_TOKEN", "")
DASHBOARD_CORS_ORIGIN = os.environ.get("COCKPIT_DASHBOARD_CORS_ORIGIN", "http://localhost:8090")
DASHBOARD_RATE_LIMIT = int(os.environ.get("COCKPIT_DASHBOARD_RATE_LIMIT", "60"))


# ─── HTML Templates removed as part of UI convergence ───
