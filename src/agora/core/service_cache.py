"""Local service cache — persists last-known service list for degrade mode.

When Agora Registry is unreachable, the Router falls back to this cache
so that Agent-to-Agent (A2A) direct communication can still function.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import structlog

logger = structlog.get_logger(__name__)

CACHE_DIR = Path.home() / ".agora"
CACHE_FILE = CACHE_DIR / "service_cache.json"
CACHE_TTL = 3600  # seconds (1 hour) — cache is considered stale after this


def load_service_cache() -> dict:
    """Load the last-known service list from disk cache.

    Returns a dict in the same format as registry.discover() output:
        {"services": [...], "timestamp": <float>}
    Returns empty dict if cache file is missing or corrupted.
    """
    try:
        if not CACHE_FILE.exists():
            logger.info("service_cache_missing", path=str(CACHE_FILE))
            return {}
        data = json.loads(CACHE_FILE.read_text())
        if not isinstance(data, dict):
            logger.warning("service_cache_invalid_format")
            return {}
        services = data.get("services", [])
        if not isinstance(services, list):
            logger.warning("service_cache_services_not_list")
            return {}
        age = time.time() - data.get("timestamp", 0)
        logger.info(
            "service_cache_loaded",
            service_count=len(services),
            age_seconds=round(age, 1),
        )
        return data
    except json.JSONDecodeError as e:
        logger.warning("service_cache_corrupted", error=str(e))
        return {}
    except OSError as e:
        logger.warning("service_cache_io_error", error=str(e))
        return {}


def save_service_cache(services: list[dict]) -> bool:
    """Persist the current service list to disk cache.

    Args:
        services: List of service dicts from the registry.

    Returns:
        True on success, False on failure.
    """
    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        payload = {
            "services": services,
            "timestamp": time.time(),
        }
        CACHE_FILE.write_text(json.dumps(payload, indent=2))
        logger.info(
            "service_cache_saved",
            service_count=len(services),
            path=str(CACHE_FILE),
        )
        return True
    except OSError as e:
        logger.warning("service_cache_save_failed", error=str(e))
        return False


def clear_service_cache() -> bool:
    """Remove the local service cache file.

    Returns True if the cache was removed successfully,
    False if it didn't exist or removal failed.
    """
    try:
        if CACHE_FILE.exists():
            CACHE_FILE.unlink()
            logger.info("service_cache_cleared")
            return True
        return False
    except OSError as e:
        logger.warning("service_cache_clear_failed", error=str(e))
        return False


def is_cache_stale() -> bool:
    """Check if the cached service list is older than CACHE_TTL."""
    try:
        if not CACHE_FILE.exists():
            return True
        data = json.loads(CACHE_FILE.read_text())
        age = time.time() - data.get("timestamp", 0)
        return age > CACHE_TTL
    except (json.JSONDecodeError, OSError):
        return True
