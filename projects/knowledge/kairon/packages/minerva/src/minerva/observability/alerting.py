from __future__ import annotations

"""
Extracted from SharedBrain D_Harvest → minerva.

---
Type: Module
Status: ACTIVE
Version: 1.0.0
Authority: nucleus/Z-Core/L0-Genome/R0-ACT-SYS-AX01-10_holographic_metadata_axiom.md
Layer: L3
---
"""
# Alerting ≡ Module
# 内涵 ≝ {Alerting}
# 外延 ≝ {e | e ∈ Organs ∧ implements(e, Alerting)}
# 功能 ⊢ {Init_Alerting, Execute_Alerting, Validate_Alerting}
# =============================================================================

# ---
# domain: D-Harvest
# layer: observability
# status: active
# ---

"""
D-Harvest 告警管理器

支持多通道告警、规则引擎、去重和历史记录。

特性：
- 基于规则的告警评估
- 多通道通知（日志/邮件/Webhook）
- 告警去重和合并
- 告警历史持久化
- 线程安全
"""

import hashlib
import json
import logging
import threading
import time
import urllib.request
from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any, cast

logger = logging.getLogger(__name__)


class AlertSeverity(StrEnum):
    """告警严重级别"""

    CRITICAL = "critical"
    WARNING = "warning"
    INFO = "info"


class AlertStatus(StrEnum):
    """告警状态"""

    FIRING = "firing"  # 触发中
    RESOLVED = "resolved"  # 已解决
    SUPPRESSED = "suppressed"  # 已抑制


@dataclass
class Alert:
    """
    告警数据结构

    遵循Prometheus AlertManager兼容格式。
    """

    # 告警标识
    alert_id: str
    name: str  # 告警名称

    # 告警内容
    severity: AlertSeverity
    status: AlertStatus = AlertStatus.FIRING
    summary: str = ""
    description: str = ""

    # 元数据
    labels: dict[str, str] = field(default_factory=dict)
    annotations: dict[str, str] = field(default_factory=dict)

    # 时间戳
    starts_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    ends_at: datetime | None = None
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    # 去重
    fingerprint: str = ""

    def __post_init__(self) -> None:
        """生成告警指纹用于去重"""
        if not self.fingerprint:
            self.fingerprint = self._compute_fingerprint()

    def _compute_fingerprint(self) -> str:
        """
        计算告警指纹用于去重

        指纹基于alert_name + labels，忽略value和timestamp。
        相同的告警条件会产生相同的指纹。
        """
        # 排序后的标签键值对
        label_str = ",".join(f"{k}={v}" for k, v in sorted(self.labels.items()))

        # 组合名称和标签
        content = f"{self.name}:{label_str}"

        # SHA256哈希（取前16位）
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    def resolve(self) -> None:
        """解决告警"""
        self.status = AlertStatus.RESOLVED
        self.ends_at = datetime.now(UTC)
        self.updated_at = datetime.now(UTC)

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "alert_id": self.alert_id,
            "name": self.name,
            "severity": self.severity.value,
            "status": self.status.value,
            "summary": self.summary,
            "description": self.description,
            "labels": self.labels,
            "annotations": self.annotations,
            "starts_at": self.starts_at.isoformat(),
            "ends_at": self.ends_at.isoformat() if self.ends_at else None,
            "updated_at": self.updated_at.isoformat(),
            "fingerprint": self.fingerprint,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Alert:
        """从字典创建"""
        return cls(
            alert_id=data["alert_id"],
            name=data["name"],
            severity=AlertSeverity(data["severity"]),
            status=AlertStatus(data["status"]),
            summary=data.get("summary", ""),
            description=data.get("description", ""),
            labels=data.get("labels", {}),
            annotations=data.get("annotations", {}),
            starts_at=datetime.fromisoformat(data["starts_at"]),
            ends_at=datetime.fromisoformat(data["ends_at"]) if data.get("ends_at") else None,
            updated_at=datetime.fromisoformat(data["updated_at"]),
            fingerprint=data.get("fingerprint", ""),
        )


# ============ 告警规则引擎 ============


@dataclass
class AlertRule:
    """告警规则定义"""

    name: str
    # 规则条件（PromQL表达式或自定义条件）
    expression: str | Callable[..., bool]
    # 评估条件
    severity: AlertSeverity = AlertSeverity.WARNING
    # 持续时间（秒）- 条件满足多久后触发告警
    for_duration: float = 0.0
    # 告警摘要
    summary: str = ""
    # 告警描述
    description: str = ""
    # 标签
    labels: dict[str, str] = field(default_factory=dict)
    # 注释
    annotations: dict[str, str] = field(default_factory=dict)


class AlertRuleEvaluator:
    """
    告警规则评估器

    评估规则条件是否满足，管理告警生命周期。
    """

    def __init__(self) -> None:
        """初始化评估器"""
        self._rules: list[AlertRule] = []
        self._active_fingerprints: dict[str, Alert] = {}
        self._pending_fingerprints: dict[str, float] = {}  # fingerprint -> first_seen_time
        self._lock = threading.RLock()

    def add_rule(self, rule: AlertRule) -> None:
        """添加规则"""
        with self._lock:
            self._rules.append(rule)
            logger.info(f"Added alert rule: {rule.name}")

    def remove_rule(self, rule_name: str) -> bool:
        """移除规则"""
        with self._lock:
            for i, rule in enumerate(self._rules):
                if rule.name == rule_name:
                    self._rules.pop(i)
                    logger.info(f"Removed alert rule: {rule_name}")
                    return True
            return False

    def evaluate(self, metrics_getter: Callable[[str], float | None]) -> list[Alert]:
        """
        评估所有规则

        Args:
            metrics_getter: 函数，接收指标名返回值

        Returns:
            新触发或更新的告警列表
        """
        with self._lock:
            new_alerts = []
            current_time = time.time()

            # 评估每个规则
            for rule in self._rules:
                try:
                    # 检查条件
                    condition_met = self._check_condition(rule, metrics_getter)

                    # 生成预期的fingerprint
                    expected_fingerprint = self._make_fingerprint(rule)

                    if condition_met:
                        # 条件满足
                        if expected_fingerprint in self._active_fingerprints:
                            # 已存在的告警，更新时间
                            alert = self._active_fingerprints[expected_fingerprint]
                            alert.updated_at = datetime.now(UTC)
                        elif expected_fingerprint in self._pending_fingerprints:
                            # 检查是否达到持续时间
                            first_seen = self._pending_fingerprints[expected_fingerprint]
                            if current_time - first_seen >= rule.for_duration:
                                # 触发告警
                                alert = self._create_alert(rule)
                                self._active_fingerprints[expected_fingerprint] = alert
                                del self._pending_fingerprints[expected_fingerprint]
                                new_alerts.append(alert)
                                logger.warning(f"Alert triggered: {rule.name}")
                        else:
                            if rule.for_duration <= 0:
                                # 无等待窗口时首次命中立即触发。
                                alert = self._create_alert(rule)
                                self._active_fingerprints[expected_fingerprint] = alert
                                new_alerts.append(alert)
                                logger.warning(f"Alert triggered: {rule.name}")
                            else:
                                # 首次满足条件，进入pending
                                self._pending_fingerprints[expected_fingerprint] = current_time

                    else:
                        # 条件不满足
                        if expected_fingerprint in self._active_fingerprints:
                            # 解决告警
                            alert = self._active_fingerprints[expected_fingerprint]
                            alert.resolve()
                            new_alerts.append(alert)
                            del self._active_fingerprints[expected_fingerprint]
                            logger.info(f"Alert resolved: {rule.name}")

                        # 清除pending
                        if expected_fingerprint in self._pending_fingerprints:
                            del self._pending_fingerprints[expected_fingerprint]

                except (KeyError, TypeError, ValueError, RuntimeError) as e:
                    logger.error(f"Error evaluating rule {rule.name}: {e}")

            return new_alerts

    def _check_condition(self, rule: AlertRule, metrics_getter: Callable[[str], float | None]) -> bool:
        """检查规则条件"""
        if callable(rule.expression):
            # 自定义条件函数
            return rule.expression(metrics_getter)
        else:
            # 简单指标阈值比较（格式: "metric_name > value"）
            return self._evaluate_simple_expression(rule.expression, metrics_getter)

    def _evaluate_simple_expression(self, expression: str, metrics_getter: Callable[[str], float | None]) -> bool:
        """评估简单表达式"""
        try:
            # 支持格式: "metric > 10", "metric < 5", "metric >= 0.5"
            for op in [">=", "<=", "!=", ">", "<", "=="]:
                if op in expression:
                    metric_name, threshold_str = expression.split(op, 1)
                    metric_name = metric_name.strip()
                    threshold = float(threshold_str.strip())

                    value = metrics_getter(metric_name)
                    if value is None:
                        return False

                    match op:
                        case ">":
                            return value > threshold
                        case "<":
                            return value < threshold
                        case ">=":
                            return value >= threshold
                        case "<=":
                            return value <= threshold
                        case "==":
                            return value == threshold
                        case "!=":
                            return value != threshold

            # 尝试直接解析为布尔值
            value = metrics_getter(expression.strip())
            return bool(value)

        except (ValueError, AttributeError):
            logger.warning(f"Failed to evaluate expression: {expression}")
            return False

    def _create_alert(self, rule: AlertRule) -> Alert:
        """从规则创建告警"""
        alert_id = f"{rule.name}-{int(time.time())}"

        return Alert(
            alert_id=alert_id,
            name=rule.name,
            severity=rule.severity,
            summary=rule.summary or f"Alert: {rule.name}",
            description=rule.description,
            labels=rule.labels.copy(),
            annotations=rule.annotations.copy(),
        )

    def _make_fingerprint(self, rule: AlertRule) -> str:
        """生成规则的指纹"""
        label_str = ",".join(f"{k}={v}" for k, v in sorted(rule.labels.items()))
        content = f"{rule.name}:{label_str}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    def get_active_alerts(self) -> list[Alert]:
        """获取当前活跃的告警"""
        with self._lock:
            return list(self._active_fingerprints.values())


# ============ 告警通道 ============


class AlertChannel(ABC):
    """告警通道抽象基类"""

    @abstractmethod
    def send(self, alert: Alert) -> bool:
        """
        发送告警

        Returns:
            发送成功返回True
        """
        pass


class LogAlertChannel(AlertChannel):
    """日志告警通道"""

    def __init__(self, logger_instance: logging.Logger | None = None) -> None:
        self.logger = logger_instance or logger

    def send(self, alert: Alert) -> bool:
        """记录告警到日志"""
        if alert.status == AlertStatus.FIRING:
            log_func = self.logger.warning if alert.severity != AlertSeverity.CRITICAL else self.logger.error
            log_func(f"[ALERT] {alert.name} | {alert.severity.value.upper()} | {alert.summary}")
        else:
            self.logger.info(f"[ALERT RESOLVED] {alert.name}")
        return True


class WebhookAlertChannel(AlertChannel):
    """Webhook告警通道"""

    def __init__(self, url: str, timeout: float = 5.0) -> None:
        self.url = url
        self.timeout = timeout

    def send(self, alert: Alert) -> bool:
        """发送告警到Webhook"""
        try:
            payload = {
                "alert": alert.to_dict(),
                "timestamp": datetime.now(UTC).isoformat(),
            }

            data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(  # noqa: S310
                self.url,
                data=data,
                headers={"Content-Type": "application/json"},
                method="POST",
            )

            with urllib.request.urlopen(req, timeout=self.timeout) as response:  # noqa: S310
                return cast("bool", response.status == 200)

        except (OSError, urllib.error.URLError, ValueError, TypeError) as e:  # type: ignore[reportAttributeAccessIssue]
            logger.error(f"Webhook send failed: {e}")
            return False


class EmailAlertChannel(AlertChannel):
    """邮件告警通道（占位实现）"""

    def __init__(self, smtp_host: str, from_addr: str, to_addrs: list[str]) -> None:
        self.smtp_host = smtp_host
        self.from_addr = from_addr
        self.to_addrs = to_addrs

    def send(self, alert: Alert) -> bool:
        """发送告警邮件（占位）"""
        # 实际实现需要smtplib
        logger.info(f"[EMAIL] Would send alert {alert.name} to {self.to_addrs}")
        return True


# ============ 告警历史 ============


class AlertHistory:
    """
    告警历史记录

    持久化存储告警历史，支持查询和统计。
    """

    def __init__(self, storage_path: Path | None = None) -> None:
        """
        初始化历史记录

        Args:
            storage_path: 存储文件路径（默认: .omc/alerts_history.jsonl）
        """
        self.storage_path = storage_path or Path(".omc/alerts_history.jsonl")
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def record(self, alert: Alert) -> bool:
        """
        记录告警

        Args:
            alert: 告警对象

        Returns:
            记录成功返回True
        """
        with self._lock:
            try:
                with open(self.storage_path, "a", encoding="utf-8") as f:
                    f.write(json.dumps(alert.to_dict()) + "\n")
                return True
            except OSError as e:
                logger.error(f"Failed to write alert history: {e}")
                return False

    def query(
        self,
        limit: int = 100,
        severity: AlertSeverity | None = None,
        status: AlertStatus | None = None,
        since: datetime | None = None,
    ) -> list[Alert]:
        """
        查询告警历史

        Args:
            limit: 返回数量限制
            severity: 过滤严重级别
            status: 过滤状态
            since: 起始时间

        Returns:
            告警列表
        """
        with self._lock:
            results: list[Alert] = []

            try:
                if not self.storage_path.exists():
                    return []

                with open(self.storage_path, encoding="utf-8") as f:
                    for line in f:
                        if len(results) >= limit:
                            break

                        try:
                            data = json.loads(line.strip())
                            alert = Alert.from_dict(data)

                            # 过滤
                            if severity and alert.severity != severity:
                                continue
                            if status and alert.status != status:
                                continue
                            if since and alert.starts_at < since:
                                continue

                            results.append(alert)

                        except (json.JSONDecodeError, KeyError):
                            continue

            except OSError as e:
                logger.error(f"Failed to read alert history: {e}")

            # 按时间倒序
            results.sort(key=lambda a: a.starts_at, reverse=True)
            return results

    def get_stats(self) -> dict[str, Any]:
        """获取统计信息"""
        alerts = self.query(limit=10000)  # 获取足够多的样本

        total = len(alerts)
        by_severity = {s.value: 0 for s in AlertSeverity}
        by_status = {s.value: 0 for s in AlertStatus}

        for alert in alerts:
            by_severity[alert.severity.value] += 1
            by_status[alert.status.value] += 1

        return {
            "total_alerts": total,
            "by_severity": by_severity,
            "by_status": by_status,
        }


# ============ 告警管理器 ============


class HarvestAlertManager:
    """
    D-Harvest 告警管理器

    整合规则评估、通道通知和历史记录。

    Example:
        manager = HarvestAlertManager()

        # 添加规则
        manager.add_rule(AlertRule(
            name="high_error_rate",
            expression="harvest_error_rate > 0.1",
            severity=AlertSeverity.WARNING,
            for_duration=600,  # 10分钟
            summary="错误率过高"
        ))

        # 评估并通知
        manager.evaluate()

        # 获取活跃告警
        active = manager.get_active_alerts()
    """

    def __init__(
        self,
        channels: list[AlertChannel] | None = None,
        history_path: Path | None = None,
    ) -> None:
        """
        初始化告警管理器

        Args:
            channels: 通知通道列表（默认使用日志通道）
            history_path: 历史记录存储路径
        """
        self.evaluator = AlertRuleEvaluator()
        self.channels = channels or [LogAlertChannel()]
        self.history = AlertHistory(history_path)
        self._lock = threading.RLock()

        # 注册默认规则
        self._register_default_rules()

    def _register_default_rules(self) -> None:
        """注册默认告警规则"""
        # 收割错误率告警
        self.add_rule(
            AlertRule(
                name="harvest_high_error_rate",
                expression="d_harvest_harvest_error_rate > 0.1",
                severity=AlertSeverity.WARNING,
                for_duration=600,  # 10分钟
                summary="收割错误率过高",
                description="过去5分钟错误率超过0.1次/秒",
            )
        )

        # 质量通过率告警
        self.add_rule(
            AlertRule(
                name="quality_low_pass_rate",
                expression="d_harvest_quality_gate_pass_rate < 0.5",
                severity=AlertSeverity.WARNING,
                for_duration=1800,  # 30分钟
                summary="质量门控通过率低",
                description="质量门控通过率低于50%",
            )
        )

        # 同步积压告警
        self.add_rule(
            AlertRule(
                name="sync_vector_lag_high",
                expression="d_harvest_sync_vector_lag_items > 10000",
                severity=AlertSeverity.CRITICAL,
                for_duration=600,  # 10分钟
                summary="向量同步积压严重",
                description="待向量同步条目超过10000条",
            )
        )

    def add_rule(self, rule: AlertRule) -> None:
        """添加告警规则"""
        self.evaluator.add_rule(rule)

    def remove_rule(self, rule_name: str) -> bool:
        """移除告警规则"""
        return self.evaluator.remove_rule(rule_name)

    def add_channel(self, channel: AlertChannel) -> None:
        """添加通知通道"""
        with self._lock:
            self.channels.append(channel)

    def evaluate(self, metrics_getter: Callable[[str], float | None] | None = None) -> list[Alert]:  # type: ignore[no-redef]
        """
        评估规则并发送告警

        Args:
            metrics_getter: 指标获取函数（默认使用全局收集器）

        Returns:
            新触发或更新的告警列表
        """
        if metrics_getter is None:
            # 使用全局收集器作为默认
            from minerva.observability.metrics_collector import get_global_collector

            collector = get_global_collector()

            def metrics_getter(name: str) -> float | None:
                return collector.get_metric(name)

        # 评估规则
        new_alerts = self.evaluator.evaluate(metrics_getter)

        # 发送通知并记录历史
        for alert in new_alerts:
            self._notify(alert)
            self.history.record(alert)

        return new_alerts

    def _notify(self, alert: Alert) -> None:
        """通过所有通道发送告警"""
        for channel in self.channels:
            try:
                channel.send(alert)
            except (OSError, RuntimeError, ValueError, TypeError) as e:
                logger.error(f"Channel {type(channel).__name__} failed: {e}")

    def get_active_alerts(self) -> list[Alert]:
        """获取当前活跃告警"""
        return self.evaluator.get_active_alerts()

    def get_history(
        self,
        limit: int = 100,
        severity: AlertSeverity | None = None,
    ) -> list[Alert]:
        """查询告警历史"""
        return self.history.query(limit=limit, severity=severity)

    def get_stats(self) -> dict[str, Any]:
        """获取告警统计"""
        return {
            "active_alerts": len(self.get_active_alerts()),
            "history_stats": self.history.get_stats(),
        }


# ============ 便捷函数 ============


def create_alert_manager(
    enable_webhook: bool = False,
    webhook_url: str = "",
    enable_email: bool = False,
    smtp_host: str = "",
    from_addr: str = "",
    to_addrs: list[str] | None = None,
) -> HarvestAlertManager:
    """
    创建配置好的告警管理器

    Args:
        enable_webhook: 是否启用Webhook
        webhook_url: Webhook URL
        enable_email: 是否启用邮件
        smtp_host: SMTP服务器
        from_addr: 发件人地址
        to_addrs: 收件人地址列表

    Returns:
        配置好的告警管理器
    """
    channels: list[AlertChannel] = [LogAlertChannel()]

    if enable_webhook and webhook_url:
        channels.append(WebhookAlertChannel(webhook_url))

    if enable_email and smtp_host and to_addrs:
        channels.append(EmailAlertChannel(smtp_host, from_addr, to_addrs))

    return HarvestAlertManager(channels=channels)
