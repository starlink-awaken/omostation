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
import time as _time
from fnmatch import fnmatch
from pathlib import Path
from typing import Any

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
        self._default_daily_usd = float(
            data.get("default_daily_usd", _DEFAULT_DAILY_USD)
        )
        self._callers = {}
        for c in data.get("callers", []) or []:
            if isinstance(c, dict) and c.get("id"):
                self._callers[str(c["id"])] = float(
                    c.get("daily_usd", _DEFAULT_DAILY_USD)
                )
        self._services = []
        for s in data.get("services", []) or []:
            if isinstance(s, dict) and s.get("prefix"):
                self._services.append(
                    (str(s["prefix"]), float(s.get("daily_usd", _DEFAULT_DAILY_USD)))
                )

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

    # 告警防抖: 同一 caller 最短告警间隔 (秒)
    _ALERT_THROTTLE_SECONDS = 300.0
    # 预警阈值: 用量 ≥ 80% 触发 warning
    _WARN_RATIO = 0.8

    def __init__(
        self,
        config: QuotaConfig | None = None,
        account_db: ResourceAccountDB | None = None,
    ):
        self._config = config or QuotaConfig()
        self._db = account_db or ResourceAccountDB()
        self._lock = threading.Lock()
        self._last_alert_ts: dict[str, float] = {}  # caller → last alert time
        self._blocked_sent: set[str] = set()  # caller 已发过 blocked 告警

    def _get_prom_metrics(self):
        """懒加载配额 Prometheus 指标 (模块级单例避免重复注册)."""
        return _get_prom_metrics()

    def _emit_alert(self, caller_id: str, level: str, info: dict, service: str) -> None:
        """发布配额告警事件 + 可选 webhook (防抖 + 状态翻转语义).

        level: "warning" (≥80%) 或 "blocked" (超限).
        防抖: per-caller 300s 节流; blocked 只在首次进入时发 (恢复后重置)。
        """
        now = _time.time()
        with self._lock:
            last = self._last_alert_ts.get(caller_id, 0.0)
            if now - last < self._ALERT_THROTTLE_SECONDS:
                return
            # blocked 状态翻转: 已发过且仍 blocked → 不再重复 (恢复后 blocked_sent 重置)
            if level == "blocked" and caller_id in self._blocked_sent:
                self._last_alert_ts[caller_id] = now
                return
            self._last_alert_ts[caller_id] = now
            if level == "blocked":
                self._blocked_sent.add(caller_id)

        # Prometheus 指标
        counter, gauge = self._get_prom_metrics()
        if counter is not None and gauge is not None:
            if level == "blocked":
                counter.labels(caller_id=caller_id).inc()
            gauge.labels(caller_id=caller_id).set(
                min(info.get("usage_ratio", 0.0), 1.0)
            )

        # 事件总线 (统一告警入口)
        try:
            from agora.core.state import get_event_bus

            bus = get_event_bus()
            bus.publish(
                {
                    "type": f"quota:{level}",
                    "source": "agora.bos_quota",
                    "payload": {
                        "caller_id": caller_id,
                        "service": service,
                        "today_cost": info.get("today_cost"),
                        "limit_usd": info.get("limit_usd"),
                        "remaining": info.get("remaining"),
                        "usage_ratio": round(info.get("usage_ratio", 0.0), 4),
                    },
                }
            )
        except Exception:  # defensive: 告警发布失败不阻塞调用
            _log.warning(
                "quota_alert_publish_failed caller=%s level=%s", caller_id, level
            )

        # 可选 webhook (复用 is_safe_url 校验)
        try:
            from agora.core.circuit_breaker import is_safe_url

            webhook = os.environ.get("AGORA_QUOTA_WEBHOOK", "")
            if webhook and is_safe_url(webhook):
                import httpx

                def _send():
                    try:
                        httpx.post(
                            webhook,
                            json={
                                "type": f"quota:{level}",
                                "caller_id": caller_id,
                                "service": service,
                                "today_cost": info.get("today_cost"),
                                "limit_usd": info.get("limit_usd"),
                                "remaining": info.get("remaining"),
                            },
                            timeout=5,
                        )
                    except Exception:  # defensive
                        _log.warning("quota_webhook_failed caller=%s", caller_id)

                threading.Thread(target=_send, daemon=True).start()
        except Exception:  # defensive
            pass

    def _reset_alert(self, caller_id: str) -> None:
        """配额恢复后重置告警状态 (允许下次 blocked 再发)."""
        with self._lock:
            self._blocked_sent.discard(caller_id)

    def reload(self) -> None:
        """热重载配置 (ConfigWatcher 回调)."""
        with self._lock:
            self._config.load()

    def check(self, caller_id: str, service: str = "") -> tuple[bool, dict]:
        """检查调用者是否还有配额.

        Returns: (allowed, info) — info 含 today_cost/limit/remaining.
        遗留-4: 超限/预警触发告警事件 + 指标。
        """
        with self._lock:
            limit = self._config.daily_limit_for(caller_id, service)
            today = self._db.get_quota(caller_id)
            today_cost = float(today.get("today_cost", 0.0))
        usage_ratio = (today_cost / limit) if limit > 0 else 0.0
        allowed = today_cost < limit
        info = {
            "caller_id": caller_id,
            "today_cost": round(today_cost, 6),
            "limit_usd": limit,
            "remaining": round(max(limit - today_cost, 0.0), 6),
            "usage_ratio": round(usage_ratio, 4),
            "allowed": allowed,
        }
        if allowed and usage_ratio >= self._WARN_RATIO:
            self._emit_alert(caller_id, "warning", info, service)
        elif not allowed:
            self._emit_alert(caller_id, "blocked", info, service)
        else:
            # 恢复: 用量降回阈值下 → 重置 blocked 状态
            self._reset_alert(caller_id)
        return allowed, info

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
            _log.warning("quota_record_failed caller=%s service=%s", caller_id, service)


# ── Prometheus 配额指标 (模块级单例, 避免重复注册) ──────────────
_prom_exceeded: Any | None = None
_prom_ratio: Any | None = None
_prom_lock = threading.Lock()


def _get_prom_metrics():
    """懒加载配额 Prometheus 指标 (全局共享)."""
    global _prom_exceeded, _prom_ratio
    if _prom_exceeded is not None:
        return _prom_exceeded, _prom_ratio
    with _prom_lock:
        if _prom_exceeded is not None:
            return _prom_exceeded, _prom_ratio
        try:
            from prometheus_client import Counter, Gauge

            _prom_exceeded = Counter(
                "bos_quota_exceeded_total",
                "BOS quota exceeded (blocked) by caller",
                ["caller_id"],
            )
            _prom_ratio = Gauge(
                "bos_quota_usage_ratio",
                "BOS quota usage ratio (today_cost/limit) by caller",
                ["caller_id"],
            )
        except ImportError:  # defensive: prometheus-client 未装
            _prom_exceeded = None
            _prom_ratio = None
    return _prom_exceeded, _prom_ratio


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
