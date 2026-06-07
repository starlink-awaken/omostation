"""
SSOT Kernel — Monitoring Architecture
========================================
监控架构设计模块

功能：
1. 监控架构设计
2. 监控配置管理
3. 监控范围定义
4. 系统集成接口
"""

import os
import random
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class MonitoringScope(Enum):
    """监控范围"""

    ENGINE = "engine"  # 引擎监控
    EXECUTION = "execution"  # 执行监控
    RESOURCE = "resource"  # 资源监控
    BUSINESS = "business"  # 业务监控
    QUALITY = "quality"  # 质量监控
    SYSTEM = "system"  # 系统监控
    ALL = "all"  # 全部监控


class EnvironmentType(Enum):
    """环境类型"""

    DEVELOPMENT = "development"
    CI = "ci"
    PRODUCTION = "production"
    TESTING = "testing"


class DataRetention(Enum):
    """数据保留策略"""

    MINIMAL = "minimal"  # 保留最少数据
    STANDARD = "standard"  # 标准保留
    EXTENDED = "extended"  # 扩展保留
    ARCHIVE = "archive"  # 归档保留


@dataclass
class EnvironmentConfig:
    """环境配置"""

    environment: EnvironmentType
    sample_rate: float = 1.0  # 采样率
    log_level: str = "INFO"  # 日志级别
    alert_enabled: bool = False  # 是否启用告警
    retention: DataRetention = DataRetention.STANDARD
    metrics_to_collect: list[str] = field(default_factory=list)

    # 环境特定配置
    development_defaults: dict[str, Any] = {
        "sample_rate": 1.0,
        "log_level": "DEBUG",
        "alert_enabled": False,
        "retention": DataRetention.MINIMAL,
    }

    ci_defaults: dict[str, Any] = {"sample_rate": 1.0, "log_level": "INFO", "alert_enabled": False, "retention": DataRetention.MINIMAL}

    production_defaults: dict[str, Any] = {
        "sample_rate": 0.1,
        "log_level": "WARN",
        "alert_enabled": True,
        "retention": DataRetention.EXTENDED,
    }

    @classmethod
    def from_environment(cls, environment: EnvironmentType) -> "EnvironmentConfig":
        """根据环境类型创建配置"""
        defaults = {
            EnvironmentType.DEVELOPMENT: cls.development_defaults,
            EnvironmentType.CI: cls.ci_defaults,
            EnvironmentType.PRODUCTION: cls.production_defaults,
            EnvironmentType.TESTING: cls.development_defaults,
        }

        config_data = defaults.get(environment, cls.development_defaults)

        return cls(
            environment=environment,
            sample_rate=config_data["sample_rate"],
            log_level=config_data["log_level"],
            alert_enabled=config_data["alert_enabled"],
            retention=config_data["retention"],
        )


@dataclass
class MonitoringConfig:
    """监控配置"""

    name: str = "ssot_monitoring"
    version: str = "2.0.0"
    enabled: bool = True
    scopes: list[MonitoringScope] = field(default_factory=lambda: [MonitoringScope.ALL])

    # 数据存储配置
    storage_backend: str = "in_memory"  # in_memory, json, sqlite
    storage_path: str = ""

    # 告警配置
    alert_cooldown: int = 300  # 告警冷却时间（秒）
    max_alerts_per_hour: int = 60  # 每小时最大告警数

    # 数据收集配置
    collection_interval: float = 1.0  # 收集间隔（秒）
    batch_size: int = 100  # 批处理大小

    # 性能优化
    enable_async: bool = True  # 启用异步收集
    enable_compression: bool = True  # 启用数据压缩

    # 集成配置
    enable_ci_integration: bool = True  # CI集成
    enable_dashboard: bool = True  # 仪表板
    enable_alerting: bool = True  # 告警系统

    # 自定义配置
    custom_config: dict[str, Any] = field(default_factory=dict)


@dataclass
class MetricDefinition:
    """指标定义"""

    name: str
    description: str
    scope: MonitoringScope
    data_type: str = "float"  # float, int, string, bool
    unit: str = ""
    aggregation: str = "avg"  # avg, sum, min, max, count
    tags: list[str] = field(default_factory=list)

    # 阈值配置
    warning_threshold: float | None = None
    critical_threshold: float | None = None
    higher_is_better: bool = True  # 值越大越好

    # 收集配置
    collection_enabled: bool = True
    collection_interval: float = 1.0
    retention_days: int = 30


class MonitoringArchitecture:
    """
    监控架构系统

    功能：
    1. 监控架构设计和管理
    2. 配置管理和环境适配
    3. 系统集成和扩展
    4. 监控组件协调
    """

    def __init__(self, config: MonitoringConfig | None = None):
        self.config = config or MonitoringConfig()
        self.components: dict[str, Any] = {}
        self.metrics_definitions: dict[str, Any] = {}
        self.environment = EnvironmentType.DEVELOPMENT
        self.environment_config = EnvironmentConfig.from_environment(self.environment)

        # 初始化系统
        self._initialize()

    def _initialize(self):
        """初始化监控系统"""
        # 检测运行环境
        self.environment = self._detect_environment()
        self.environment_config = EnvironmentConfig.from_environment(self.environment)

        # 加载指标定义
        self._load_default_metrics()

        # 初始化存储后端
        self._initialize_storage()

        print(f"🏗️  监控系统初始化完成: {self.environment.value} 环境")

    def _detect_environment(self) -> EnvironmentType:
        """检测运行环境"""
        # 检查CI环境
        if os.getenv("CI") or os.getenv("GITHUB_ACTIONS") or os.getenv("JENKINS_HOME"):
            return EnvironmentType.CI

        # 检查生产环境
        if os.getenv("PRODUCTION") or os.getenv("ENVIRONMENT") == "production":
            return EnvironmentType.PRODUCTION

        # 默认为开发环境
        return EnvironmentType.DEVELOPMENT

    def _load_default_metrics(self):
        """加载默认指标定义"""
        # 引擎指标
        self._add_metric_definition(
            MetricDefinition(
                name="engine.pattern_count",
                description="注册的规则模式数量",
                scope=MonitoringScope.ENGINE,
                data_type="int",
                aggregation="count",
                collection_interval=60.0,
            )
        )

        # 执行指标
        self._add_metric_definition(
            MetricDefinition(
                name="execution.total_time_ms",
                description="总执行时间（毫秒）",
                scope=MonitoringScope.EXECUTION,
                data_type="float",
                unit="ms",
                aggregation="avg",
                warning_threshold=30000,
                critical_threshold=60000,
                higher_is_better=False,
                collection_interval=1.0,
            )
        )

        self._add_metric_definition(
            MetricDefinition(
                name="execution.rules_per_second",
                description="规则执行速率（每秒规则数）",
                scope=MonitoringScope.EXECUTION,
                data_type="float",
                unit="rules/s",
                aggregation="avg",
                warning_threshold=1000,
                critical_threshold=500,
                higher_is_better=True,
                collection_interval=1.0,
            )
        )

        # 资源指标
        self._add_metric_definition(
            MetricDefinition(
                name="resource.cpu_percent",
                description="CPU使用百分比",
                scope=MonitoringScope.RESOURCE,
                data_type="float",
                unit="%",
                aggregation="avg",
                warning_threshold=80,
                critical_threshold=90,
                higher_is_better=False,
                collection_interval=1.0,
            )
        )

        self._add_metric_definition(
            MetricDefinition(
                name="resource.memory_usage_mb",
                description="内存使用量（MB）",
                scope=MonitoringScope.RESOURCE,
                data_type="float",
                unit="MB",
                aggregation="avg",
                warning_threshold=512,
                critical_threshold=1024,
                higher_is_better=False,
                collection_interval=1.0,
            )
        )

        # 业务指标
        self._add_metric_definition(
            MetricDefinition(
                name="business.entity_count",
                description="实体数量",
                scope=MonitoringScope.BUSINESS,
                data_type="int",
                aggregation="count",
                collection_interval=60.0,
            )
        )

        self._add_metric_definition(
            MetricDefinition(
                name="business.rule_count",
                description="规则数量",
                scope=MonitoringScope.BUSINESS,
                data_type="int",
                aggregation="count",
                collection_interval=60.0,
            )
        )

        # 质量指标
        self._add_metric_definition(
            MetricDefinition(
                name="quality.success_rate",
                description="规则执行成功率",
                scope=MonitoringScope.QUALITY,
                data_type="float",
                unit="%",
                aggregation="avg",
                warning_threshold=0.9,
                critical_threshold=0.8,
                higher_is_better=True,
                collection_interval=1.0,
            )
        )

        self._add_metric_definition(
            MetricDefinition(
                name="quality.blocked_count",
                description="阻塞规则数量",
                scope=MonitoringScope.QUALITY,
                data_type="int",
                aggregation="count",
                warning_threshold=5,
                critical_threshold=10,
                higher_is_better=False,
                collection_interval=1.0,
            )
        )

        # 系统指标
        self._add_metric_definition(
            MetricDefinition(
                name="system.thread_count",
                description="系统线程数量",
                scope=MonitoringScope.SYSTEM,
                data_type="int",
                aggregation="avg",
                warning_threshold=100,
                critical_threshold=200,
                higher_is_better=False,
                collection_interval=5.0,
            )
        )

    def _add_metric_definition(self, definition: MetricDefinition):
        """添加指标定义"""
        self.metrics_definitions[definition.name] = definition

    def _initialize_storage(self):
        """初始化存储后端"""
        from .storage import InMemoryStorage, JSONStorage, SQLiteStorage

        if self.config.storage_backend == "json":
            if not self.config.storage_path:
                self.config.storage_path = "monitoring_data.json"
            self.storage = JSONStorage(self.config.storage_path)
        elif self.config.storage_backend == "sqlite":
            if not self.config.storage_path:
                self.config.storage_path = "monitoring_data.db"
            self.storage = SQLiteStorage(self.config.storage_path)
        else:
            self.storage = InMemoryStorage()

        print(f"📊 存储后端: {self.config.storage_backend}")

    def register_component(self, name: str, component: Any):
        """注册监控组件"""
        self.components[name] = component
        print(f"🔧 注册组件: {name}")

    def should_collect(self) -> bool:
        """是否应该收集指标"""
        return random.random() < self.environment_config.sample_rate  # noqa: S311

    def should_alert(self) -> bool:
        """是否应该发送告警"""
        return self.environment_config.alert_enabled and self.config.enable_alerting

    def get_metric_definition(self, name: str) -> MetricDefinition | None:
        """获取指标定义"""
        return self.metrics_definitions.get(name)

    def list_metrics_by_scope(self, scope: MonitoringScope) -> list[MetricDefinition]:
        """列出指定范围的指标"""
        return [
            definition
            for definition in self.metrics_definitions.values()
            if definition.scope == scope or scope == MonitoringScope.ALL
        ]

    def get_environment_info(self) -> dict[str, Any]:
        """获取环境信息"""
        return {
            "environment": self.environment.value,
            "sample_rate": self.environment_config.sample_rate,
            "log_level": self.environment_config.log_level,
            "alert_enabled": self.environment_config.alert_enabled,
            "retention": self.environment_config.retention.value,
            "config_version": self.config.version,
            "monitoring_version": "2.0.0",
        }

    def validate_configuration(self) -> list[str]:
        """验证配置"""
        issues = []

        # 检查存储配置
        if self.config.storage_backend in ["json", "sqlite"]:
            if not self.config.storage_path:
                issues.append("存储路径未配置")

        # 检查采集间隔
        if self.config.collection_interval < 0.1:
            issues.append("采集间隔过小，可能影响性能")

        # 检查告警配置
        if self.config.max_alerts_per_hour < 10:
            issues.append("告警限制过低，可能错过重要问题")

        return issues

    def get_system_health(self) -> dict[str, Any]:
        """获取系统健康状态"""
        health: dict[str, Any] = {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "components": {},
            "metrics": {"total_definitions": len(self.metrics_definitions), "by_scope": {}},
        }

        # 统计各范围的指标数量
        for scope in MonitoringScope:
            metrics = self.list_metrics_by_scope(scope)
            health["metrics"]["by_scope"][scope.value] = len(metrics)

        # 组件状态
        for name, component in self.components.items():
            try:
                component_health = getattr(component, "get_health", lambda: {"status": "healthy"})()
                health["components"][name] = component_health
            except Exception as e:
                health["components"][name] = {"status": "error", "error": str(e)}

        # 检查配置问题
        issues = self.validate_configuration()
        if issues:
            health["status"] = "warning"
            health["config_issues"] = issues

        return health

    def generate_diagnostic_report(self) -> str:
        """生成诊断报告"""
        report = []

        report.append("=" * 70)
        report.append("🏥 SSOT 监控系统诊断报告")
        report.append("=" * 70)

        # 环境信息
        env_info = self.get_environment_info()
        report.append("\n🌍 环境信息:")
        for key, value in env_info.items():
            report.append(f"  {key}: {value}")

        # 系统健康
        health = self.get_system_health()
        status_icon = "✅" if health["status"] == "healthy" else ("⚠️" if health["status"] == "warning" else "❌")
        report.append(f"\n🏥 系统健康: {status_icon} {health['status']}")

        # 配置问题
        if "config_issues" in health:
            report.append("\n⚠️  配置问题:")
            for issue in health["config_issues"]:
                report.append(f"  - {issue}")

        # 指标统计
        report.append("\n📊 指标统计:")
        for scope, count in health["metrics"]["by_scope"].items():
            report.append(f"  {scope}: {count} 个指标")

        # 组件状态
        report.append("\n🔧 组件状态:")
        for name, component_health in health["components"].items():
            status = component_health.get("status", "unknown")
            icon = "✅" if status == "healthy" else ("⚠️" if status == "warning" else "❌")
            report.append(f"  {icon} {name}: {status}")

        report.append("=" * 70)

        return "\n".join(report)


# 全局监控架构实例
_global_architecture = None


def get_monitoring_architecture() -> MonitoringArchitecture:
    """获取全局监控架构实例"""
    global _global_architecture
    if _global_architecture is None:
        _global_architecture = MonitoringArchitecture()
    return _global_architecture


def set_monitoring_architecture(architecture: MonitoringArchitecture):
    """设置全局监控架构实例"""
    global _global_architecture
    _global_architecture = architecture
