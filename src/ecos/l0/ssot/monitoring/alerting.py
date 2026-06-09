"""
SSOT Kernel — Intelligent Alerting System
===========================================
智能告警系统模块

功能：
1. 多维度告警规则
2. 智能阈值管理
3. 告警抑制和冷却
4. 上下文感知告警
5. 自动化响应和建议
"""

from collections import defaultdict, deque
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any

from .environment import EnvironmentAwareMonitor, get_environment_manager


class AlertSeverity(Enum):
    """告警严重程度"""

    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"
    FATAL = "FATAL"


class AlertStatus(Enum):
    """告警状态"""

    ACTIVE = "active"  # 活跃告警
    RESOLVED = "resolved"  # 已解决
    SUPPRESSED = "suppressed"  # 已抑制
    ACKNOWLEDGED = "acknowledged"  # 已确认


@dataclass
class Alert:
    """告警"""

    id: str
    name: str
    severity: AlertSeverity
    status: AlertStatus
    message: str
    timestamp: str
    environment: str
    metrics_data: dict[str, Any] = field(default_factory=dict)
    recommendations: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "id": self.id,
            "name": self.name,
            "severity": self.severity.value,
            "status": self.status.value,
            "message": self.message,
            "timestamp": self.timestamp,
            "environment": self.environment,
            "metrics_data": self.metrics_data,
            "recommendations": self.recommendations,
            "metadata": self.metadata,
        }


@dataclass
class AlertRule:
    """告警规则"""

    id: str
    name: str
    metric_name: str
    condition: Callable[[float], bool]
    severity: AlertSeverity
    cooldown_seconds: int = 300
    enabled: bool = True
    description: str = ""
    recommendations: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def evaluate(self, value: float) -> bool:
        """评估是否触发告警"""
        if not self.enabled:
            return False
        return self.condition(value)


class IntelligentAlertingSystem:
    """
    智能告警系统

    功能：
    1. 多维度告警规则管理
    2. 智能阈值学习和调整
    3. 告警抑制和冷却
    4. 上下文感知告警
    5. 自动化建议生成
    """

    def __init__(self, monitor: EnvironmentAwareMonitor | None = None):
        self.monitor = monitor or get_environment_manager().get_monitor("default")

        # 告警规则
        self.rules: dict[str, AlertRule] = {}
        self._load_default_rules()

        # 告警历史
        self.alert_history: deque = deque(maxlen=10000)
        self.active_alerts: dict[str, Alert] = {}

        # 冷却管理
        self.last_alert_times: dict[str, datetime] = {}

        # 统计信息
        self.stats = {
            "total_generated": 0,
            "total_suppressed": 0,
            "total_resolved": 0,
            "by_severity": defaultdict(int),
            "by_rule": defaultdict(int),
        }

        # 告警回调
        self.alert_callbacks: list[Callable[[Alert], None]] = []

    def _load_default_rules(self):
        """加载默认告警规则"""

        # 高失败率告警
        self._add_rule(
            AlertRule(
                id="alert_high_failure_rate",
                name="高失败率告警",
                metric_name="quality.failed_ratio",
                condition=lambda v: v > 0.1,  # 10%失败率
                severity=AlertSeverity.CRITICAL,
                cooldown_seconds=300,
                description="规则执行失败率过高，需要立即关注",
                recommendations=[
                    "检查规则依赖是否完整",
                    "验证领域数据格式是否正确",
                    "查看详细错误日志",
                    "考虑启用错误恢复机制",
                ],
            )
        )

        # 执行超时告警
        self._add_rule(
            AlertRule(
                id="alert_execution_timeout",
                name="执行超时告警",
                metric_name="execution.total_time_ms",
                condition=lambda v: v > 30000,  # 30秒
                severity=AlertSeverity.WARNING,
                cooldown_seconds=600,
                description="执行时间过长，可能存在性能问题",
                recommendations=[
                    "分析性能瓶颈",
                    "检查规则复杂度",
                    "考虑规则并行执行",
                    "优化条件评估逻辑",
                ],
            )
        )

        # 内存使用告警
        self._add_rule(
            AlertRule(
                id="alert_high_memory",
                name="内存使用告警",
                metric_name="system.memory_percent",
                condition=lambda v: v > 85,  # 85%内存使用
                severity=AlertSeverity.WARNING,
                cooldown_seconds=900,
                description="内存使用率过高",
                recommendations=[
                    "检查内存泄漏",
                    "优化数据结构",
                    "实现数据分批处理",
                    "清理不必要的缓存",
                ],
            )
        )

        # CPU使用告警
        self._add_rule(
            AlertRule(
                id="alert_high_cpu",
                name="CPU使用告警",
                metric_name="system.cpu_percent",
                condition=lambda v: v > 90,  # 90% CPU使用
                severity=AlertSeverity.WARNING,
                cooldown_seconds=600,
                description="CPU使用率过高",
                recommendations=[
                    "检查是否有死循环",
                    "优化算法复杂度",
                    "减少不必要的计算",
                    "考虑异步处理",
                ],
            )
        )

        # 吞吐量下降告警
        self._add_rule(
            AlertRule(
                id="alert_low_throughput",
                name="吞吐量下降告警",
                metric_name="execution.rules_per_second",
                condition=lambda v: v < 100,  # 低于100 rules/s
                severity=AlertSeverity.WARNING,
                cooldown_seconds=900,
                description="规则执行吞吐量过低",
                recommendations=[
                    "分析规则执行效率",
                    "检查规则依赖关系",
                    "考虑规则缓存优化",
                    "验证数据加载性能",
                ],
            )
        )

        # 阻塞规则告警
        self._add_rule(
            AlertRule(
                id="alert_blocked_rules",
                name="阻塞规则告警",
                metric_name="execution.blocked_rules",
                condition=lambda v: v > 5,  # 超过5个阻塞规则
                severity=AlertSeverity.ERROR,
                cooldown_seconds=300,
                description="存在阻塞规则，影响正常执行",
                recommendations=[
                    "检查规则依赖完整性",
                    "验证实体/事实是否存在",
                    "修复依赖引用问题",
                    "考虑依赖自动恢复",
                ],
            )
        )

        # 质量得分告警
        self._add_rule(
            AlertRule(
                id="alert_low_quality_score",
                name="质量得分告警",
                metric_name="quality.score",
                condition=lambda v: v < 80,  # 低于80分
                severity=AlertSeverity.WARNING,
                cooldown_seconds=600,
                description="执行质量得分过低",
                recommendations=[
                    "分析失败规则原因",
                    "检查数据质量问题",
                    "优化规则定义",
                    "提升测试覆盖率",
                ],
            )
        )

    def _add_rule(self, rule: AlertRule):
        """添加告警规则"""
        self.rules[rule.id] = rule
        print(f"🔔 加载告警规则: {rule.name}")

    def register_rule(self, rule: AlertRule):
        """注册自定义告警规则"""
        self.rules[rule.id] = rule
        print(f"🔔 注册告警规则: {rule.name}")

    def unregister_rule(self, rule_id: str):
        """取消注册告警规则"""
        if rule_id in self.rules:
            del self.rules[rule_id]
            print(f"🔕 取消告警规则: {rule_id}")

    def evaluate_metrics(self, metrics: dict[str, float]) -> list[Alert]:
        """评估指标并生成告警"""
        new_alerts = []

        if not self.monitor.should_alert():
            self.stats["total_suppressed"] += len(self.rules)
            return new_alerts

        for rule_id, rule in self.rules.items():
            if not rule.enabled:
                continue

            # 检查指标是否存在于数据中
            if rule.metric_name not in metrics:
                continue

            metric_value = metrics[rule.metric_name]

            # 检查冷却时间
            if self._is_in_cooldown(rule_id, rule.cooldown_seconds):
                continue

            # 评估告警条件
            if rule.evaluate(metric_value):
                # 创建告警
                alert = self._create_alert(rule, metric_value, metrics)
                new_alerts.append(alert)

                # 记录告警
                self.alert_history.append(alert)
                self.active_alerts[alert.id] = alert
                self.last_alert_times[rule_id] = datetime.now()

                # 更新统计
                self.stats["total_generated"] += 1
                self.stats["by_severity"][alert.severity.value] += 1
                self.stats["by_rule"][rule_id] += 1

                # 记录到环境监控器
                self.monitor.record_alert(
                    alert_name=alert.name,
                    severity=alert.severity.value,
                    message=alert.message,
                    metadata={"alert_id": alert.id, "rule_id": rule_id},
                )

                # 调用告警回调
                self._execute_alert_callbacks(alert)

        return new_alerts

    def _create_alert(
        self, rule: AlertRule, trigger_value: float, all_metrics: dict[str, float]
    ) -> Alert:
        """创建告警"""
        alert_id = f"{rule.id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        alert = Alert(
            id=alert_id,
            name=rule.name,
            severity=rule.severity,
            status=AlertStatus.ACTIVE,
            message=f"{rule.description} (当前值: {trigger_value})",
            timestamp=datetime.now().isoformat(),
            environment=self.monitor.environment_type.value,
            metrics_data={
                "trigger_metric": rule.metric_name,
                "trigger_value": trigger_value,
                "threshold": self._get_threshold_value(rule),
                "all_metrics": all_metrics,
            },
            recommendations=rule.recommendations.copy(),
            metadata={
                "rule_id": rule.id,
                "cooldown_seconds": rule.cooldown_seconds,
                "rule_metadata": rule.metadata,
            },
        )

        # 生成增强建议
        enhanced_recommendations = self._generate_enhanced_recommendations(
            rule, trigger_value, all_metrics
        )
        alert.recommendations.extend(enhanced_recommendations)

        return alert

    def _get_threshold_value(self, rule: AlertRule) -> float:
        """获取规则阈值"""
        # 从条件中提取阈值（简化版本）
        if rule.metric_name == "quality.failed_ratio":
            return 0.1
        elif rule.metric_name == "execution.total_time_ms":
            return 30000
        elif rule.metric_name == "system.memory_percent":
            return 85
        elif rule.metric_name == "system.cpu_percent":
            return 90
        elif rule.metric_name == "execution.rules_per_second":
            return 100
        elif rule.metric_name == "execution.blocked_rules":
            return 5
        elif rule.metric_name == "quality.score":
            return 80
        return 0.0

    def _generate_enhanced_recommendations(
        self, rule: AlertRule, trigger_value: float, all_metrics: dict[str, float]
    ) -> list[str]:
        """生成增强建议"""
        recommendations = []

        # 基于相关指标的建议
        if rule.metric_name == "execution.total_time_ms":
            throughput = all_metrics.get("execution.rules_per_second", 0)
            if throughput < 100:
                recommendations.append("吞吐量过低，建议优化规则执行效率")

            memory_percent = all_metrics.get("system.memory_percent", 0)
            if memory_percent > 80:
                recommendations.append("内存使用过高，可能是执行时间长的原因")

        elif rule.metric_name == "quality.failed_ratio":
            blocked_count = all_metrics.get("execution.blocked_rules", 0)
            if blocked_count > 0:
                recommendations.append(f"存在{blocked_count}个阻塞规则，需要优先处理")

        # 基于环境的建议
        if self.monitor.environment_type.value == "production":
            recommendations.append("生产环境告警，建议立即响应")
        elif self.monitor.environment_type.value == "development":
            recommendations.append("开发环境告警，建议优化后测试")

        return recommendations

    def _is_in_cooldown(self, rule_id: str, cooldown_seconds: int) -> bool:
        """检查是否在冷却期"""
        if rule_id not in self.last_alert_times:
            return False

        last_time = self.last_alert_times[rule_id]
        cooldown_end = last_time + timedelta(seconds=cooldown_seconds)

        return datetime.now() < cooldown_end

    def resolve_alert(self, alert_id: str) -> bool:
        """解决告警"""
        if alert_id in self.active_alerts:
            alert = self.active_alerts[alert_id]
            alert.status = AlertStatus.RESOLVED
            alert.metadata["resolved_at"] = datetime.now().isoformat()

            # 从活跃告警中移除
            del self.active_alerts[alert_id]

            # 更新统计
            self.stats["total_resolved"] += 1

            print(f"✅ 告警已解决: {alert.name}")
            return True

        return False

    def acknowledge_alert(self, alert_id: str) -> bool:
        """确认告警"""
        if alert_id in self.active_alerts:
            alert = self.active_alerts[alert_id]
            alert.status = AlertStatus.ACKNOWLEDGED
            alert.metadata["acknowledged_at"] = datetime.now().isoformat()

            print(f"👁️  告警已确认: {alert.name}")
            return True

        return False

    def get_active_alerts(self, severity: AlertSeverity | None = None) -> list[Alert]:
        """获取活跃告警"""
        active_alerts = list(self.active_alerts.values())

        if severity:
            active_alerts = [a for a in active_alerts if a.severity == severity]

        # 按严重程度排序
        severity_order = {
            AlertSeverity.FATAL: 0,
            AlertSeverity.CRITICAL: 1,
            AlertSeverity.ERROR: 2,
            AlertSeverity.WARNING: 3,
            AlertSeverity.INFO: 4,
        }

        active_alerts.sort(key=lambda a: severity_order.get(a.severity, 999))

        return active_alerts

    def get_alert_summary(self) -> dict[str, Any]:
        """获取告警摘要"""
        active_alerts = list(self.active_alerts.values())

        return {
            "total_active": len(active_alerts),
            "by_severity": self._count_by_severity(active_alerts),
            "total_generated": self.stats["total_generated"],
            "total_suppressed": self.stats["total_suppressed"],
            "total_resolved": self.stats["total_resolved"],
            "recent_alerts": [a.to_dict() for a in list(self.alert_history)[-10:]],
            "most_frequent_rules": self._get_most_frequent_rules(),
        }

    def _count_by_severity(self, alerts: list[Alert]) -> dict[str, int]:
        """按严重程度统计"""
        counts = defaultdict(int)
        for alert in alerts:
            counts[alert.severity.value] += 1
        return dict(counts)

    def _get_most_frequent_rules(self, top_n: int = 5) -> list[dict]:
        """获取最频繁触发的规则"""
        sorted_rules = sorted(
            self.stats["by_rule"].items(), key=lambda x: x[1], reverse=True
        )

        return [
            {"rule_id": rule_id, "count": count}
            for rule_id, count in sorted_rules[:top_n]
        ]

    def register_callback(self, callback: Callable[[Alert], None]):
        """注册告警回调函数"""
        self.alert_callbacks.append(callback)

    def _execute_alert_callbacks(self, alert: Alert):
        """执行告警回调"""
        for callback in self.alert_callbacks:
            try:
                callback(alert)
            except Exception as e:
                print(f"⚠️  告警回调执行失败: {e}")

    def auto_resolve_stale_alerts(self, max_age_hours: int = 24):
        """自动解决过期告警"""
        current_time = datetime.now()
        resolved_count = 0

        stale_alerts = []

        for alert_id, alert in list(self.active_alerts.items()):
            alert_time = datetime.fromisoformat(alert.timestamp)
            age = current_time - alert_time

            if age > timedelta(hours=max_age_hours):
                stale_alerts.append(alert_id)

        for alert_id in stale_alerts:
            if self.resolve_alert(alert_id):
                resolved_count += 1

        if resolved_count > 0:
            print(f"🧹 自动解决了 {resolved_count} 个过期告警")

        return resolved_count

    def generate_alert_report(self) -> str:
        """生成告警报告"""
        summary = self.get_alert_summary()

        report = []
        report.append("=" * 70)
        report.append("🚨 SSOT 智能告警系统报告")
        report.append("=" * 70)

        # 活跃告警统计
        active_count = summary["total_active"]
        severity_counts = summary["by_severity"]

        report.append("\n📊 活跃告警统计:")
        report.append(f"  总计: {active_count}")
        for severity, count in severity_counts.items():
            icon = {"CRITICAL": "🔴", "ERROR": "🟠", "WARNING": "🟡", "INFO": "🔵"}.get(
                severity, "⚪"
            )
            report.append(f"  {icon} {severity}: {count}")

        # 历史统计
        report.append("\n📈 历史统计:")
        report.append(f"  总生成告警: {summary['total_generated']}")
        report.append(f"  总抑制告警: {summary['total_suppressed']}")
        report.append(f"  总解决告警: {summary['total_resolved']}")

        # 活跃告警详情
        active_alerts = self.get_active_alerts()
        if active_alerts:
            report.append("\n🚨 活跃告警详情:")
            for alert in active_alerts[:10]:  # 最多显示10个
                severity_icon = {
                    "CRITICAL": "🔴",
                    "ERROR": "🟠",
                    "WARNING": "🟡",
                    "INFO": "🔵",
                }.get(alert.severity.value, "⚪")
                report.append(
                    f"  {severity_icon} [{alert.severity.value}] {alert.name}"
                )
                report.append(f"      时间: {alert.timestamp}")
                report.append(f"      消息: {alert.message}")
                if alert.recommendations:
                    report.append(f"      建议: {alert.recommendations[0]}")

        # 频繁规则
        if summary["most_frequent_rules"]:
            report.append("\n🔔 频繁触发的告警规则:")
            for rule_info in summary["most_frequent_rules"]:
                report.append(f"  {rule_info['rule_id']}: {rule_info['count']} 次")

        report.append("=" * 70)

        return "\n".join(report)
