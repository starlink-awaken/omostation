"""BOS 配额检查器 — per-caller 每日成本配额 (遗留-3, 网关→编排大脑).

在 resolve_bos_uri 的限流之后、执行之前检查调用者今日累计成本是否超限。
配置来自 agora-bos-rates.yaml 的 ``quotas:`` 段 (支持通配 caller + 服务级)。

配额语义:
- ``default_daily_usd`` — 未配置 caller 的默认每日上限 (安全默认, 防止匿名滥用)
- ``callers[].daily_usd`` — 按 caller_id 覆盖 (支持 ``*`` 通配)
- ``services[].daily_usd`` — 服务级配额 (对特定 prefix 的调用额外限制)

成本记录复用 ``accounting.ResourceAccountDB`` (SQLite, WAL 模式)。
"""

from __future__ import annotations

import logging
import os
import threading
from fnmatch import fnmatch
from pathlib import Path

from agora.accounting import ResourceAccountDB

_log = logging.getLogger(__name__)

_DEFAULT_DAILY_USD = 10.0


class QuotaConfig:
    """配额配置 — 从 agora-bos-rates.yaml 加载, 支持热重载."""

    def __init__(self, rates_path: Path | None = None):
        self._rates_path = rates_path or _default_rates_path()
        self._default_daily_usd = _DEFAULT_DAILY_USD
        self._callers: dict[str, float] = {}
        self._services: list[tuple[str, float]] = []

    def load(self, data: dict | None = None) -> None:
        """从 dict 或文件加载配额配置."""
        if data is None:
            try:
                import yaml

                raw = yaml.safe_load(self._rates_path.read_text(encoding="utf-8"))
                data = raw.get("quotas", {}) if isinstance(raw, dict) else {}
            except (OSError, ValueError, ImportError):
                data = {}
        if not isinstance(data, dict):
            data = {}
        self._default_daily_usd = float(data.get("default_daily_usd", _DEFAULT_DAILY_USD))
        self._callers = {}
        for c in data.get("callers", []) or []:
            if isinstance(c, dict) and c.get("id"):
                self._callers[str(c["id"])] = float(c.get("daily_usd", _DEFAULT_DAILY_USD))
        self._services = []
        for s in data.get("services", []) or []:
            if isinstance(s, dict) and s.get("prefix"):
                self._services.append((str(s["prefix"]), float(s.get("daily_usd", _DEFAULT_DAILY_USD))))

    def daily_limit_for(self, caller_id: str, service: str = "") -> float:
        """返回 caller 对某服务的每日配额上限 (USD)."""
        # 精确匹配 → 通配匹配 → 默认
        if caller_id in self._callers:
            limit = self._callers[caller_id]
        else:
            limit = self._default_daily_usd
            for pattern, lmt in self._callers.items():
                if fnmatch(caller_id, pattern):
                    limit = lmt
                    break
        # 服务级覆盖 (更严格时取 min)
        for prefix, svc_limit in self._services:
            if service.startswith(prefix) and svc_limit < limit:
                limit = svc_limit
        return limit

    @property
    def default_daily_usd(self) -> float:
        return self._default_daily_usd

    @property
    def callers(self) -> dict[str, float]:
        return dict(self._callers)


def _default_rates_path() -> Path:
    return Path(__file__).resolve().parent.parent / "agora-bos-rates.yaml"


class QuotaChecker:
    """配额检查器 — 查今日累计成本 vs 配置上限."""

    def __init__(self, config: QuotaConfig | None = None, account_db: ResourceAccountDB | None = None):
        self._config = config or QuotaConfig()
        self._db = account_db or ResourceAccountDB()
        self._lock = threading.Lock()

    def reload(self) -> None:
        """热重载配置 (ConfigWatcher 回调)."""
        with self._lock:
            self._config.load()

    def check(self, caller_id: str, service: str = "") -> tuple[bool, dict]:
        """检查调用者是否还有配额.

        Returns: (allowed, info) — info 含 today_cost/limit/remaining.
        """
        with self._lock:
            limit = self._config.daily_limit_for(caller_id, service)
            today = self._db.get_quota(caller_id)
            today_cost = float(today.get("today_cost", 0.0))
        allowed = today_cost < limit
        return allowed, {
            "caller_id": caller_id,
            "today_cost": round(today_cost, 6),
            "limit_usd": limit,
            "remaining": round(max(limit - today_cost, 0.0), 6),
            "allowed": allowed,
        }

    def record(
        self,
        caller_id: str,
        service: str,
        tool_name: str = "",
        input_tokens: int = 0,
        output_tokens: int = 0,
        cost_usd: float = 0.0,
    ) -> None:
        """记录一次调用成本 (成功路径)."""
        try:
            from agora.accounting import CallRecord

            rec = CallRecord(
                caller_id=caller_id,
                service_name=service,
                tool_name=tool_name,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cost_usd=cost_usd,
            )
            self._db.record_call(rec)
        except Exception:  # defensive: 记账失败不阻塞调用
            _log.warning("quota_record_failed", caller_id=caller_id, service=service)


# ── 全局单例 ──
_quota_checker: QuotaChecker | None = None
_quota_config: QuotaConfig | None = None


def get_quota_checker() -> QuotaChecker:
    """返回全局 QuotaChecker 单例 (延迟初始化)."""
    global _quota_checker, _quota_config
    if _quota_checker is None:
        _quota_config = QuotaConfig()
        _quota_config.load()
        _quota_checker = QuotaChecker(config=_quota_config)
    return _quota_checker


def reload_quota_config() -> None:
    """热重载配额配置 (供 ConfigWatcher 调用)."""
    checker = get_quota_checker()
    checker.reload()
    _log.info("quota_config_reloaded")
