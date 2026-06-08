"""QuotaEngine — 统一配额引擎 (异步缓存版).

架构:
  - 后台线程定时拉取 codexbar 数据 → 写缓存
  - get_quota() / get_status() 只读缓存，从不阻塞
  - 大盘 0.1s 返回

用法::

    from llm_gateway.quota_engine import QuotaEngine

    qe = QuotaEngine()
    qe.start()                     # 启动后台刷新线程
    
    # 立即返回缓存数据 (从不阻塞)
    quota = qe.get_quota("deepseek")
    status = qe.get_all_status()
    
    qe.stop()                      # 停止后台线程
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

from .credentials import CredentialsManager

_log = logging.getLogger(__name__)


class QuotaModel(Enum):
    PREPAID = "prepaid"
    MONTHLY = "monthly"
    WEEKLY = "weekly"
    RATE = "rate"
    FREE = "free"
    UNLIMITED = "unlimited"
    UNKNOWN = "unknown"


class Availability(Enum):
    AVAILABLE = "available"
    NO_CREDENTIALS = "no_credentials"
    OFFLINE = "offline"
    QUOTA_EXHAUSTED = "quota_exhausted"
    QUOTA_LOW = "quota_low"
    UNKNOWN = "unknown"
    RATE_LIMITED = "rate_limited"


@dataclass
class ProviderData:
    """Provider 完整状态 (缓存单元)。"""
    provider: str = ""
    has_credentials: bool = False
    has_key: bool = False
    online: bool = False
    quota_ok: bool = False
    available: bool = False
    status: str = "unknown"
    quota_model: str = "unknown"
    quota_pct: float = 100.0
    balance: float = 0.0
    balance_unit: str = ""
    quota_source: str = ""  # codexbar | local | unknown
    error: str = ""
    updated_at: float = 0.0
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "available": self.available,
            "status": self.status,
            "has_key": self.has_key,
            "online": self.online,
            "quota_ok": self.quota_ok,
            "quota_pct": self.quota_pct,
            "quota_source": self.quota_source,
            "balance": self.balance,
            "balance_unit": self.balance_unit,
        }


# ── codexbar supported providers ────────────────────────────────────────

CODEXBAR_PROVIDERS = {
    "deepseek": "deepseek",
    "openai": "openai",
    "anthropic": "claude",
    "gemini": "gemini",
    "azure": "azure-openai",
    "bedrock": "bedrock",
    "vertex": "vertexai",
    "minimax": "minimax",
    "openrouter": "openrouter",
    "siliconflow": "siliconflow",
    "nvidia": "nvidia",
    "kimi": "kimi",
    "zhipu": "zhipu",
}

QUOTA_MODEL_MAP: dict[str, str] = {
    "deepseek": "prepaid", "openai": "monthly", "anthropic": "weekly",
    "gemini": "free", "ollama": "unlimited", "hitl": "unlimited",
}


class QuotaEngine:
    """统一配额引擎 — 后台异步刷新 codexbar 数据。

    start() 启动后台线程，每 5 分钟刷新全部缓存。
    get_quota() / get_status() 只读缓存，从不阻塞。
    """

    def __init__(self, refresh_interval: int = 300) -> None:
        self._cache: dict[str, ProviderData] = {}
        self._lock = threading.RLock()
        self._interval = refresh_interval
        self._thread: threading.Thread | None = None
        self._running = False
        self._creds = CredentialsManager()
        self._first_batch = True
        self._ready = False

    # ── Lifecycle ───────────────────────────────────────────────────────

    def start(self) -> None:
        """启动后台刷新线程。"""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._refresh_loop, daemon=True)
        self._thread.start()
        _log.info("QuotaEngine: background refresh started (every %ds)", self._interval)

    def stop(self) -> None:
        """停止后台线程。"""
        self._running = False
        self._thread = None

    def wait_ready(self, timeout: float = 10.0) -> bool:
        """等待首次缓存完成。"""
        t0 = time.time()
        while not self._ready and (time.time() - t0) < timeout:
            time.sleep(0.1)
        return self._ready

    @property
    def ready(self) -> bool:
        return self._ready

    # ── Background refresh loop ─────────────────────────────────────────

    def _refresh_loop(self) -> None:
        """后台循环：首次全量刷新，之后增量刷新。"""
        while self._running:
            try:
                self._refresh_all()
                # Mark ready once at least one codexbar provider is cached
                if not self._ready:
                    with self._lock:
                        has_codexbar = any(
                            p.quota_source == "codexbar" for p in self._cache.values()
                        )
                    if has_codexbar or not self._first_batch:
                        self._ready = True
                if self._first_batch:
                    _log.info("QuotaEngine: first batch complete (%d providers)", len(self._cache))
                    self._first_batch = False
            except Exception as e:
                _log.warning("QuotaEngine refresh failed: %s", e)

            for _ in range(self._interval):
                if not self._running:
                    return
                time.sleep(1)

    def _refresh_all(self) -> None:
        """全量刷新：查询所有 Provider 的状态。"""
        now = time.time()

        # 1. Get all known providers from credentials
        all_providers = set()
        try:
            for k in self._creds.list_keys():
                all_providers.add(k["provider"])
        except Exception:
            pass
        for p in ["deepseek", "openai", "anthropic", "gemini", "ollama"]:
            all_providers.add(p)

        # 2. Query codexbar-supported providers in parallel
        codexbar_providers = [p for p in all_providers if p in CODEXBAR_PROVIDERS]
        threads = []
        for p in codexbar_providers:
            t = threading.Thread(target=self._query_one, args=(p, now), daemon=True)
            t.start()
            threads.append(t)
        for t in threads:
            t.join(timeout=20.0)  # max 20s for all codexbar queries

        # 3. Quick check for remaining providers (no codexbar)
        for p in all_providers:
            if p not in self._cache or (time.time() - self._cache[p].updated_at) > self._interval:
                self._quick_check(p, now)

    def _query_one(self, provider: str, now: float) -> None:
        """查询单个 Provider (含 codexbar)。"""
        pd = ProviderData(provider=provider, updated_at=now)

        # Has key?
        creds = self._creds.list_keys(provider)
        env_map = {"deepseek": "DEEPSEEK_API_KEY", "openai": "OPENAI_API_KEY",
                   "anthropic": "ANTHROPIC_API_KEY", "gemini": "GOOGLE_API_KEY"}
        pd.has_key = len(creds) > 0 or bool(os.environ.get(env_map.get(provider, ""), ""))

        if not pd.has_key:
            pd.status = "no_credentials"
            self._set_cache(pd)
            return

        # Query codexbar
        mapped = CODEXBAR_PROVIDERS.get(provider, provider)
        try:
            result = subprocess.run(
                ["codexbar", "usage", "--format", "json", "--provider", mapped],
                capture_output=True, text=True, timeout=30,
            )
            if result.returncode == 0:
                data = json.loads(result.stdout)
                if isinstance(data, list) and len(data) > 0:
                    entry = data[0]
                    usage = entry.get("usage", {})
                    primary = usage.get("primary") or {}
                    used_pct = primary.get("usedPercent", 0) if isinstance(primary, dict) else 0
                    reset_desc = primary.get("resetDescription", "")

                    pd.online = True
                    pd.quota_pct = 100 - used_pct
                    pd.quota_source = "codexbar"
                    pd.quota_ok = pd.quota_pct >= 10
                    pd.quota_model = QUOTA_MODEL_MAP.get(provider, "unknown")
                    pd.available = pd.quota_pct > 0
                    pd.status = "available" if pd.available else "quota_exhausted"
                    if pd.quota_pct < 10 and pd.quota_pct > 0:
                        pd.status = "quota_low"

                    # Parse balance
                    if "¥" in reset_desc:
                        import re
                        nums = re.findall(r"[\d.]+", reset_desc)
                        if nums:
                            pd.balance = float(nums[0])
                            pd.balance_unit = "CNY"
                    elif "$" in reset_desc:
                        nums = re.findall(r"[\d.]+", reset_desc)
                        if nums:
                            pd.balance = float(nums[0])
                            pd.balance_unit = "USD"

                    self._set_cache(pd)
                    return
        except (subprocess.TimeoutExpired, json.JSONDecodeError, FileNotFoundError, OSError) as e:
            pd.error = str(e)[:50]

        # codexbar failed — still mark as available (has key)
        pd.online = True
        pd.quota_source = "local"
        pd.status = "available"
        pd.available = True
        pd.quota_ok = True
        self._set_cache(pd)

    def _quick_check(self, provider: str, now: float) -> None:
        """快速检查（无 codexbar，仅凭据）。"""
        creds = self._creds.list_keys(provider)
        env_map = {"deepseek": "DEEPSEEK_API_KEY", "openai": "OPENAI_API_KEY",
                   "anthropic": "ANTHROPIC_API_KEY", "gemini": "GOOGLE_API_KEY"}
        has_key = len(creds) > 0 or bool(os.environ.get(env_map.get(provider, ""), ""))
        pd = ProviderData(
            provider=provider,
            has_key=has_key,
            available=has_key,
            online=has_key,
            quota_ok=has_key,
            status="available" if has_key else "no_credentials",
            quota_source="local",
            updated_at=now,
        )
        if not has_key:
            pd.status = "no_credentials"
        self._set_cache(pd)

    def _set_cache(self, pd: ProviderData) -> None:
        with self._lock:
            self._cache[pd.provider] = pd

    # ── Public API: 只读缓存，从不阻塞 ─────────────────────────────────

    def get_quota(self, provider: str) -> ProviderData:
        """获取缓存中的配额数据。从不阻塞。"""
        with self._lock:
            pd = self._cache.get(provider)
            if pd:
                return pd
        # Cache miss — do quick check synchronously
        self._quick_check(provider, time.time())
        with self._lock:
            return self._cache.get(provider, ProviderData(provider=provider))

    def get_status(self, provider: str) -> ProviderData:
        return self.get_quota(provider)

    def get_all_status(self) -> dict[str, ProviderData]:
        """批量获取 — 全部从缓存读取。"""
        with self._lock:
            return dict(self._cache)

    def get_summary(self) -> dict[str, Any]:
        """大盘 — 纯缓存读取，< 0.01s。"""
        with self._lock:
            all_pds = list(self._cache.values())

        total = len(all_pds)
        available = sum(1 for p in all_pds if p.available)
        no_key = sum(1 for p in all_pds if p.status == "no_credentials")
        quota_low = sum(1 for p in all_pds if p.status == "quota_low")
        exhausted = sum(1 for p in all_pds if p.status == "quota_exhausted")

        providers = [p.to_dict() for p in sorted(all_pds, key=lambda x: x.provider)]

        return {
            "total": total,
            "available": available,
            "no_key": no_key,
            "quota_low": quota_low,
            "quota_exhausted": exhausted,
            "codexbar_available": self._codexbar_available(),
            "providers": providers,
            "cached_at": time.time(),
        }

    @staticmethod
    def _codexbar_available() -> bool:
        try:
            r = subprocess.run(["codexbar", "--help"], capture_output=True, timeout=2)
            return r.returncode == 0
        except (FileNotFoundError, OSError):
            return False

    def invalidate(self) -> None:
        """清除缓存。"""
        with self._lock:
            self._cache.clear()
