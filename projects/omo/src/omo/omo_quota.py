import json
import logging
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

_log = logging.getLogger(__name__)

CACHE_FILE = Path(os.environ.get("RUNTIME_HOME", str(Path.home() / ".runtime"))) / "cache" / "quota_rates.json"
TTL_SECONDS = 300  # 5 minutes


def get_cached_rates_and_quota() -> dict[str, Any]:
    """Reads the quota cache, triggering an async refresh if it's stale or missing."""
    _trigger_refresh_if_stale()
    
    if CACHE_FILE.exists():
        try:
            return json.loads(CACHE_FILE.read_text())
        except (json.JSONDecodeError, OSError):
            pass
    return {"rates": {}, "quota": {}}


def _trigger_refresh_if_stale() -> None:
    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    if CACHE_FILE.exists():
        mtime = CACHE_FILE.stat().st_mtime
        if time.time() - mtime < TTL_SECONDS:
            return
    
    # Touch file to prevent concurrent refreshes
    try:
        CACHE_FILE.touch()
        script_path = Path(__file__).parent / "refresh_quota_cache.py"
        subprocess.Popen([sys.executable, str(script_path)], start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except OSError:
        pass
