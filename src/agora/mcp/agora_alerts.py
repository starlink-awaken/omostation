"""Agora 统一告警入口 (P4).

统一 EventBus 事件 + 可选 webhook + Prometheus 指标 的告警发送。
现有告警源接入: 配额 (bos_quota)、熔断 (circuit_breaker)、健康 (health_self_check)。

用法:
    from agora.mcp.agora_alerts import send_alert

    send_alert(
        level="warning",          # warning | blocked | degraded | recovered
        event="quota:blocked",
        payload={"caller_id": "...", "today_cost": 1.2},
        caller_key="caller:xxx",  # 防抖 key (可选, 默认 event+caller_id)
    )
"""

from __future__ import annotations

import logging
import os
import threading
import time as _time
from pathlib import Path
from typing import Any

_log = logging.getLogger(__name__)

# 告警防抖: 同一 key 最短告警间隔 (秒)
_DEFAULT_THROTTLE_SECONDS = 300.0

_ALERT_WEBHOOK_ENV = "AGORA_ALERT_WEBHOOK"  # 统一 webhook (替代分源 env)
# 兼容: 配额专用 webhook env (P4 前已有)
_QUOTA_WEBHOOK_ENV = "AGORA_QUOTA_WEBHOOK"

# 防抖状态
_throttle_ts: dict[str, float] = {}
_throttle_lock = threading.Lock()

# Prometheus 指标 (模块级单例)
_prom_alerts: Any | None = None
_prom_lock = threading.Lock()


def _get_prom_alerts():
    """懒加载告警 Prometheus 指标 (全局共享)."""
    global _prom_alerts
    if _prom_alerts is not None:
        return _prom_alerts
    with _prom_lock:
        if _prom_alerts is not None:
            return _prom_alerts
        try:
            from prometheus_client import Counter

            _prom_alerts = Counter(
                "agora_alerts_total",
                "Agora alerts emitted by level and event",
                ["level", "event"],
            )
        except ImportError:  # defensive: prometheus-client 未装
            _prom_alerts = None
    return _prom_alerts


def _resolve_webhook(event: str) -> str:
    """选择 webhook URL: 统一 env 优先, 兼容 quota 专用 env."""
    return (
        os.environ.get(_ALERT_WEBHOOK_ENV, "")
        or os.environ.get(_QUOTA_WEBHOOK_ENV, "")
    )


def _is_throttled(key: str, seconds: float) -> bool:
    """防抖: key 在 seconds 内是否已发过. 返回 True=应跳过."""
    now = _time.time()
    with _throttle_lock:
        last = _throttle_ts.get(key, 0.0)
        if now - last < seconds:
            return True
        _throttle_ts[key] = now
        return False


def send_alert(
    level: str,
    event: str,
    payload: dict[str, Any] | None = None,
    *,
    caller_key: str = "",
    throttle_seconds: float = _DEFAULT_THROTTLE_SECONDS,
    force: bool = False,
) -> None:
    """发送统一告警 (EventBus 事件 + 可选 webhook + Prometheus 指标).

    Args:
        level: warning | blocked | degraded | recovered | info
        event: 事件名 (如 quota:blocked / circuit:open / health:degraded)
        payload: 告警详情 (自动附 emitted_at)
        caller_key: 防抖 key; 空则用 f"{event}:{caller_id in payload}"
        throttle_seconds: 防抖窗口; force=True 时忽略防抖
    """
    payload = dict(payload or {})
    payload.setdefault("emitted_at", _time.strftime("%Y-%m-%dT%H:%M:%SZ", _time.gmtime()))

    # 防抖 (除非 force)
    if not force:
        key = caller_key or f"{event}:{payload.get('caller_id', '')}"
        if _is_throttled(key, throttle_seconds):
            return

    # Prometheus 指标
    counter = _get_prom_alerts()
    if counter is not None:
        counter.labels(level=level, event=event).inc()

    # 阶段4: 告警日志持久化 (JSONL, 供面板/消费端读取)
    _append_alert_log(level, event, payload)

    # EventBus 事件
    try:
        from agora.core.state import get_event_bus

        bus = get_event_bus()
        bus.publish(
            {
                "type": event,
                "source": "agora.alerts",
                "level": level,
                "payload": payload,
            }
        )
    except Exception:  # defensive: 事件发布失败不阻塞
        _log.warning("agora_alerts: EventBus publish failed event=%s", event)

    # Webhook (统一 env + is_safe_url 校验)
    webhook = _resolve_webhook(event)
    if webhook:
        try:
            from agora.core.circuit_breaker import is_safe_url

            if is_safe_url(webhook):
                import httpx

                def _send():
                    try:
                        httpx.post(
                            webhook,
                            json={"level": level, "event": event, "payload": payload},
                            timeout=5,
                        )
                    except Exception:  # defensive
                        _log.warning("agora_alerts: webhook failed event=%s", event)

                threading.Thread(target=_send, daemon=True).start()
            else:
                _log.warning("agora_alerts: unsafe webhook blocked event=%s", event)
        except Exception:  # defensive
            pass


# ── 阶段4: 告警日志持久化 ─────────────────────────────────────
_ALERT_LOG_PATH = os.environ.get(
    "AGORA_ALERT_LOG", str(Path.home() / ".agora" / "alerts.jsonl")
)
_ALERT_LOG_LOCK = threading.Lock()
_ALERT_LOG_MAX_LINES = 500  # 轮转阈值


def _append_alert_log(level: str, event: str, payload: dict) -> None:
    """追加告警到 JSONL 日志 (供面板/消费端读取, 完成告警→通知闭环)."""
    try:
        import json as _json
        from pathlib import Path as _Path

        path = _Path(_ALERT_LOG_PATH)
        path.parent.mkdir(parents=True, exist_ok=True)
        entry = {
            "ts": _time.strftime("%Y-%m-%dT%H:%M:%SZ", _time.gmtime()),
            "level": level,
            "event": event,
            "payload": payload,
        }
        with _ALERT_LOG_LOCK:
            # 轮转: 超过阈值只保留最近 N 条
            if path.exists() and sum(1 for _ in path.open()) >= _ALERT_LOG_MAX_LINES:
                lines = path.read_text().splitlines()
                path.write_text("\n".join(lines[-_ALERT_LOG_MAX_LINES // 2:]) + "\n")
            with path.open("a", encoding="utf-8") as f:
                f.write(_json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception:  # defensive: 日志写入失败不影响告警主流程
        pass


def list_recent_alerts(limit: int = 20, level: str = "") -> list[dict]:
    """读取最近告警日志 (供面板/MCP 工具消费, 阶段4).

    Args:
        limit: 返回条数 (默认 20)
        level: 按级别过滤 (warning/blocked/degraded/recovered/info, 空=全部)

    Returns:
        告警条目列表 (时间倒序, 最新在前)
    """
    try:
        import json as _json
        from pathlib import Path as _Path

        path = _Path(_ALERT_LOG_PATH)
        if not path.exists():
            return []
        entries = []
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                e = _json.loads(line)
                if level and e.get("level") != level:
                    continue
                entries.append(e)
            except Exception:  # noqa: BLE001 — 单条损坏跳过
                continue
        return entries[-limit:][::-1]  # 最新在前
    except Exception:  # defensive
        return []
