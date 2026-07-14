"""OMO 状态缓存模块"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml


@dataclass
class CacheEntry:
    key: str
    value: Any
    timestamp: str
    ttl_seconds: int = 3600


class GovernanceStateCache:
    def __init__(self, cache_dir: Path):
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._cache_file = cache_dir / "state_cache.yaml"
        self._cache = self._load_cache()

    def _load_cache(self):
        if self._cache_file.exists():
            with open(self._cache_file, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
                return {
                    k: CacheEntry(
                        k,
                        v.get("value"),
                        v.get("timestamp"),
                        v.get("ttl_seconds", 3600),
                    )
                    for k, v in data.items()
                }
        return {}

    def _save_cache(self):
        data = {
            k: {
                "value": v.value,
                "timestamp": v.timestamp,
                "ttl_seconds": v.ttl_seconds,
            }
            for k, v in self._cache.items()
        }
        with open(self._cache_file, "w", encoding="utf-8") as f:
            yaml.dump(data, f, allow_unicode=True, sort_keys=False)

    def get_cached_state(self, key):
        if key not in self._cache:
            return None

        entry = self._cache[key]
        try:
            cached_time = datetime.fromisoformat(entry.timestamp)
            if (datetime.now(UTC) - cached_time).total_seconds() > entry.ttl_seconds:
                return None
        except Exception:
            return None

        return entry.value

    def cache_state(self, key, value, ttl_seconds=3600):
        self._cache[key] = CacheEntry(
            key, value, datetime.now(UTC).isoformat(), ttl_seconds
        )
        self._save_cache()

    def invalidate_all(self):
        self._cache = {}
        self._save_cache()

    def get_cache_stats(self):
        valid = 0
        for entry in self._cache.values():
            try:
                cached_time = datetime.fromisoformat(entry.timestamp)
                if (
                    datetime.now(UTC) - cached_time
                ).total_seconds() <= entry.ttl_seconds:
                    valid += 1
            except Exception:
                pass
        return {"total_entries": len(self._cache), "valid_entries": valid}
