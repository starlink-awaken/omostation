"""
SSOT Kernel — Environment-Aware Monitoring
===========================================
环境差异化监控模块

功能：
1. 环境自动检测
2. 环境适配配置
3. 数据采样控制
4. 环境隔离
"""

import hashlib
import os
import platform
import random
import sys
from datetime import datetime
from typing import Any

from .architecture import EnvironmentConfig, EnvironmentType, MetricDefinition


class EnvironmentDetector:
    """环境检测器"""

    @staticmethod
    def detect() -> EnvironmentType:
        """检测运行环境"""
        # CI环境检测
        if EnvironmentDetector._is_ci_environment():
            return EnvironmentType.CI

        # 生产环境检测
        if EnvironmentDetector._is_production_environment():
            return EnvironmentType.PRODUCTION

        # 测试环境检测
        if EnvironmentDetector._is_testing_environment():
            return EnvironmentType.TESTING

        # 默认开发环境
        return EnvironmentType.DEVELOPMENT

    @staticmethod
    def _is_ci_environment() -> bool:
        """检测是否为CI环境"""
        ci_indicators = [
            "CI",
            "GITHUB_ACTIONS",
            "JENKINS_HOME",
            "GITLAB_CI",
            "TRAVIS",
            "CIRCLECI",
            "TEAMCITY_VERSION",
            "BUILD_NUMBER",
        ]

        return any(os.getenv(indicator) for indicator in ci_indicators)

    @staticmethod
    def _is_production_environment() -> bool:
        """检测是否为生产环境"""
        return bool(
            os.getenv("PRODUCTION")
            or os.getenv("ENVIRONMENT") == "production"
            or os.getenv("ENV") == "prod"
            or os.getenv("NODE_ENV") == "production"
        )

    @staticmethod
    def _is_testing_environment() -> bool:
        """检测是否为测试环境"""
        return bool(
            os.getenv("TESTING")
            or os.getenv("ENVIRONMENT") == "testing"
            or "pytest" in sys.modules
            or "unittest" in sys.modules
        )

    @staticmethod
    def get_system_info() -> dict[str, str]:
        """获取系统信息"""
        return {
            "platform": platform.platform(),
            "system": platform.system(),
            "release": platform.release(),
            "version": platform.version(),
            "machine": platform.machine(),
            "processor": platform.processor(),
            "python_version": platform.python_version(),
            "python_implementation": platform.python_implementation(),
        }

    @staticmethod
    def generate_environment_id() -> str:
        """生成环境唯一标识"""
        system_info = EnvironmentDetector.get_system_info()
        environment_type = EnvironmentDetector.detect()

        # 基于系统信息和环境类型生成唯一ID
        data_string = f"{system_info['platform']}_{system_info['python_version']}_{environment_type.value}"
        return hashlib.md5(data_string.encode()).hexdigest()[:12]  # noqa: S324


class EnvironmentAwareMonitor:
    """
    环境感知监控器

    功能：
    1. 环境差异化监控
    2. 智能采样控制
    3. 环境隔离
    4. 配置自适应
    """

    def __init__(self, config: EnvironmentConfig | None = None):
        self.environment_type = EnvironmentDetector.detect()
        self.environment_id = EnvironmentDetector.generate_environment_id()
        self.config = config or EnvironmentConfig.from_environment(
            self.environment_type
        )
        self.system_info = EnvironmentDetector.get_system_info()

        # 监控历史
        self.collection_history: list[dict] = []
        self.alert_history: list[dict] = []

        # 统计信息
        self.stats = {
            "collections": 0,
            "alerts_generated": 0,
            "alerts_suppressed": 0,
            "samples_taken": 0,
            "samples_skipped": 0,
        }

    def should_collect(self, metric_name: str = "") -> bool:
        """判断是否应该收集指标"""
        # 检查采样率
        if not self._should_sample():
            self.stats["samples_skipped"] += 1
            return False

        # 检查是否在指定指标列表中
        if self.config.metrics_to_collect and metric_name:
            if metric_name not in self.config.metrics_to_collect:
                return False

        self.stats["samples_taken"] += 1
        return True

    def should_alert(self, severity: str = "INFO") -> bool:
        """判断是否应该发送告警"""
        # 生产环境严格控制告警
        if self.environment_type == EnvironmentType.PRODUCTION:
            return self.config.alert_enabled and severity in ["ERROR", "CRITICAL"]

        # CI环境不发送告警
        if self.environment_type == EnvironmentType.CI:
            return False

        # 开发环境根据配置
        return self.config.alert_enabled

    def get_sampling_strategy(self) -> dict[str, Any]:
        """获取采样策略"""
        strategies = {
            EnvironmentType.DEVELOPMENT: {
                "sample_rate": 1.0,
                "log_level": "DEBUG",
                "detailed_tracing": True,
                "metrics_storage": "full",
                "alert_enabled": False,
            },
            EnvironmentType.CI: {
                "sample_rate": 1.0,
                "log_level": "INFO",
                "detailed_tracing": False,
                "metrics_storage": "minimal",
                "alert_enabled": False,
            },
            EnvironmentType.PRODUCTION: {
                "sample_rate": self.config.sample_rate,
                "log_level": self.config.log_level,
                "detailed_tracing": False,
                "metrics_storage": "aggregated",
                "alert_enabled": self.config.alert_enabled,
            },
            EnvironmentType.TESTING: {
                "sample_rate": 1.0,
                "log_level": "DEBUG",
                "detailed_tracing": True,
                "metrics_storage": "minimal",
                "alert_enabled": False,
            },
        }

        return strategies[self.environment_type]

    def adapt_metric_config(
        self, metric_definition: MetricDefinition
    ) -> MetricDefinition:
        """根据环境适配指标配置"""
        # 创建配置副本
        adapted_config = metric_definition

        # 生产环境降低采样频率
        if self.environment_type == EnvironmentType.PRODUCTION:
            adapted_config.collection_interval *= 10
            adapted_config.retention_days = min(adapted_config.retention_days, 7)

        # CI环境禁用长时间运行监控
        if self.environment_type == EnvironmentType.CI:
            if adapted_config.collection_interval > 60:
                adapted_config.collection_interval = 60

        # 开发环境启用详细监控
        if self.environment_type == EnvironmentType.DEVELOPMENT:
            adapted_config.collection_interval = min(
                adapted_config.collection_interval, 5
            )
            adapted_config.retention_days = 1

        return adapted_config

    def record_collection(
        self, metric_name: str, value: Any, tags: dict[str, str] | None = None
    ):
        """记录指标收集"""
        record = {
            "timestamp": datetime.now().isoformat(),
            "environment": self.environment_type.value,
            "environment_id": self.environment_id,
            "metric_name": metric_name,
            "value": value,
            "tags": tags or {},
            "sample_rate": self.config.sample_rate,
        }

        self.collection_history.append(record)
        self.stats["collections"] += 1

        # 限制历史记录大小
        if len(self.collection_history) > 10000:
            self.collection_history = self.collection_history[-5000:]

    def record_alert(
        self,
        alert_name: str,
        severity: str,
        message: str,
        metadata: dict[str, Any] | None = None,
    ):
        """记录告警"""
        # 检查是否应该生成告警
        if not self.should_alert(severity):
            self.stats["alerts_suppressed"] += 1
            return False

        alert_record = {
            "timestamp": datetime.now().isoformat(),
            "environment": self.environment_type.value,
            "environment_id": self.environment_id,
            "alert_name": alert_name,
            "severity": severity,
            "message": message,
            "metadata": metadata or {},
            "system_info": self.system_info,
        }

        self.alert_history.append(alert_record)
        self.stats["alerts_generated"] += 1

        # 限制告警历史大小
        if len(self.alert_history) > 1000:
            self.alert_history = self.alert_history[-500:]

        return True

    def get_environment_summary(self) -> dict[str, Any]:
        """获取环境摘要"""
        return {
            "environment_type": self.environment_type.value,
            "environment_id": self.environment_id,
            "config": {
                "sample_rate": self.config.sample_rate,
                "log_level": self.config.log_level,
                "alert_enabled": self.config.alert_enabled,
                "retention": self.config.retention.value,
                "metrics_count": len(self.config.metrics_to_collect),
            },
            "system_info": self.system_info,
            "sampling_strategy": self.get_sampling_strategy(),
            "statistics": self.stats,
            "history": {
                "collections": len(self.collection_history),
                "alerts": len(self.alert_history),
            },
        }

    def generate_isolation_key(self, component: str, metric_name: str) -> str:
        """生成环境隔离键"""
        return f"{self.environment_type.value}:{self.environment_id}:{component}:{metric_name}"

    def should_persist_data(self) -> bool:
        """判断是否应该持久化数据"""
        # 生产环境和CI环境持久化数据
        return self.environment_type in [EnvironmentType.PRODUCTION, EnvironmentType.CI]

    def get_retention_policy(self) -> dict[str, Any]:
        """获取数据保留策略"""
        policies = {
            EnvironmentType.DEVELOPMENT: {
                "metrics_days": 1,
                "alerts_days": 1,
                "logs_days": 1,
                "cleanup_enabled": True,
            },
            EnvironmentType.CI: {
                "metrics_days": 3,
                "alerts_days": 3,
                "logs_days": 3,
                "cleanup_enabled": True,
            },
            EnvironmentType.PRODUCTION: {
                "metrics_days": 30,
                "alerts_days": 90,
                "logs_days": 30,
                "cleanup_enabled": True,
            },
            EnvironmentType.TESTING: {
                "metrics_days": 1,
                "alerts_days": 1,
                "logs_days": 1,
                "cleanup_enabled": True,
            },
        }

        return policies[self.environment_type]

    def _should_sample(self) -> bool:
        """判断是否应该采样"""
        return random.random() < self.config.sample_rate  # noqa: S311

    def get_environment_specific_config(self) -> dict[str, Any]:
        """获取环境特定配置"""
        return {
            "monitoring": {
                "enabled": True,
                "level": self.config.log_level,
                "alerting": self.config.alert_enabled,
            },
            "storage": {
                "backend": "in_memory"
                if self.environment_type == EnvironmentType.DEVELOPMENT
                else "json",
                "retention_days": self.get_retention_policy()["metrics_days"],
            },
            "performance": {
                "async_enabled": self.environment_type != EnvironmentType.CI,
                "compression_enabled": self.environment_type
                == EnvironmentType.PRODUCTION,
            },
            "debugging": {
                "enabled": self.environment_type
                in [EnvironmentType.DEVELOPMENT, EnvironmentType.TESTING],
                "detailed_logging": self.environment_type
                == EnvironmentType.DEVELOPMENT,
            },
        }

    def create_environment_tag(
        self, additional_tags: dict[str, str] | None = None
    ) -> dict[str, str]:
        """创建环境标签"""
        tags = {
            "environment": self.environment_type.value,
            "environment_id": self.environment_id,
            "platform": self.system_info["platform"],
            "python_version": self.system_info["python_version"],
        }

        if additional_tags:
            tags.update(additional_tags)

        return tags


class EnvironmentManager:
    """环境管理器"""

    def __init__(self):
        self.monitors: dict[str, EnvironmentAwareMonitor] = {}
        self.active_environment = None
        self.environments: dict[str, EnvironmentType] = {}

    def register_monitor(self, name: str, monitor: EnvironmentAwareMonitor):
        """注册环境监控器"""
        self.monitors[name] = monitor
        print(f"📊 注册环境监控器: {name} ({monitor.environment_type.value})")

    def get_monitor(self, name: str) -> EnvironmentAwareMonitor | None:
        """获取环境监控器"""
        return self.monitors.get(name)

    def set_active_environment(self, name: str):
        """设置活跃环境"""
        if name in self.monitors:
            self.active_environment = name
            monitor = self.monitors[name]
            print(f"🔄 切换活跃环境: {name} ({monitor.environment_type.value})")
        else:
            print(f"❌ 未找到环境: {name}")

    def get_all_environments(self) -> list[str]:
        """获取所有环境名称"""
        return list(self.monitors.keys())

    def get_environment_overview(self) -> dict[str, Any]:
        """获取环境概览"""
        overview = {
            "total_environments": len(self.monitors),
            "active_environment": self.active_environment,
            "environments": {},
        }

        for name, monitor in self.monitors.items():
            overview["environments"][name] = {
                "type": monitor.environment_type.value,
                "sample_rate": monitor.config.sample_rate,
                "alert_enabled": monitor.config.alert_enabled,
                "statistics": monitor.stats,
                "is_active": name == self.active_environment,
            }

        return overview

    def cleanup_old_data(self, days: int | None = None):
        """清理旧数据"""
        for name, monitor in self.monitors.items():
            policy = monitor.get_retention_policy()
            days or policy["metrics_days"]

            # 清理采集历史
            if monitor.collection_history:
                datetime.now().isoformat()
                # 简化的清理逻辑
                old_count = len(monitor.collection_history)
                monitor.collection_history = [
                    record for record in monitor.collection_history[-1000:]
                ]
                cleaned_count = old_count - len(monitor.collection_history)

                if cleaned_count > 0:
                    print(f"🧹 清理 {name}: {cleaned_count} 条历史记录")

    def generate_unified_report(self) -> str:
        """生成统一环境报告"""
        report = []

        report.append("=" * 70)
        report.append("🌍 SSOT 环境统一监控报告")
        report.append("=" * 70)

        overview = self.get_environment_overview()
        report.append("\n📊 环境概览:")
        report.append(f"  总环境数: {overview['total_environments']}")
        report.append(f"  活跃环境: {overview['active_environment']}")

        active_icon = "✅" if overview["active_environment"] else "⚠️"
        report.append(f"  状态: {active_icon}")

        # 各环境详细信息
        for name, env_data in overview["environments"].items():
            active_marker = "🟢 " if env_data["is_active"] else "⚪ "
            alert_status = "🔔" if env_data["alert_enabled"] else "🔕"

            report.append(f"\n{active_marker}{name}:")
            report.append(f"  类型: {env_data['type']}")
            report.append(f"  采样率: {env_data['sample_rate'] * 100:.0f}%")
            report.append(f"  告警: {alert_status}")
            report.append(f"  采集: {env_data['statistics']['collections']}")
            report.append(f"  告警生成: {env_data['statistics']['alerts_generated']}")

        report.append("=" * 70)

        return "\n".join(report)


# 全局环境管理器
_global_environment_manager = None


def get_environment_manager() -> EnvironmentManager:
    """获取全局环境管理器实例"""
    global _global_environment_manager
    if _global_environment_manager is None:
        _global_environment_manager = EnvironmentManager()

        # 注册默认环境监控器
        default_monitor = EnvironmentAwareMonitor()
        _global_environment_manager.register_monitor("default", default_monitor)
        _global_environment_manager.set_active_environment("default")

    return _global_environment_manager


def set_environment_manager(manager: EnvironmentManager):
    """设置全局环境管理器实例"""
    global _global_environment_manager
    _global_environment_manager = manager
