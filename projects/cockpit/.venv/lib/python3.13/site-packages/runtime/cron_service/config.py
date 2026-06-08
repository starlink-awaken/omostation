"""Configuration for cron-service.

Reads from ~/.cron-service/config.yaml as SSOT.
Environment variables override individual settings.
"""

import os
from pathlib import Path
from typing import Any

import yaml

# ── Config file discovery ───────────────────────────────────────────

CONFIG_FILE = Path(os.environ.get("CRON_SERVICE_CONFIG", str(Path.home() / ".cron-service" / "config.yaml")))


def _load_config() -> dict[str, Any]:
    """Load YAML config, returns empty dict on failure."""
    if not CONFIG_FILE.exists():
        return {}
    try:
        with open(CONFIG_FILE, encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except Exception:
        return {}


def load_config() -> dict[str, Any]:
    """Public compatibility wrapper for tests and legacy imports."""
    return _load_config()


_cfg: dict[str, Any] = {}


def _get(key: str, default: Any, env: str | None = None) -> Any:
    """Get config: env var > config.yaml > default."""
    if env:
        val = os.environ.get(env)
        if val is not None:
            return val
    if not _cfg:
        _cfg.update(_load_config())
    return _cfg.get(key, default)


# ── Paths ──────────────────────────────────────────────────────────

DATA_DIR = os.environ.get(
    "CRON_SERVICE_DATA_DIR",
    str(Path(_get("data_dir", "~/.cron-service")).expanduser()),
)
SCRIPTS_DIR = os.environ.get(
    "CRON_SERVICE_SCRIPTS_DIR",
    str(Path(_get("scripts_dir", "~/.hermes/scripts")).expanduser()),
)
OUTPUT_DIR = os.environ.get(
    "CRON_SERVICE_OUTPUT_DIR",
    str(Path(_get("output_dir", "~/.cron-service/output")).expanduser()),
)

# ── Scheduler ──────────────────────────────────────────────────────

TICK_INTERVAL = int(os.environ.get("CRON_SERVICE_TICK_INTERVAL", str(_get("tick_interval", 15))))
DEFAULT_TIMEOUT = int(os.environ.get("CRON_SERVICE_DEFAULT_TIMEOUT", str(_get("default_timeout", 120))))

# ── Server ─────────────────────────────────────────────────────────

HOST = os.environ.get("CRON_SERVICE_HOST", str(_get("host", "127.0.0.1")))
HTTP_PORT = int(os.environ.get("CRON_SERVICE_HTTP_PORT", str(_get("http_port", 7450))))
MCP_PORT = int(os.environ.get("CRON_SERVICE_MCP_PORT", str(_get("mcp_port", 7451))))
