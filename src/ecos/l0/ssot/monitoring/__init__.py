"""
SSOT Kernel — Monitoring Module
==================================
智能监控系统模块

功能：
1. 环境差异化监控（开发/CI/生产）
2. 智能指标收集和分析
3. 实时告警系统
4. 性能趋势分析
5. 数据存储和可视化
"""

from .alerting import Alert, AlertRule, AlertSeverity, IntelligentAlertingSystem
from .analysis import AnomalyDetector, PerformanceTrendAnalyzer, TrendAnalysis
from .architecture import MonitoringArchitecture, MonitoringConfig, MonitoringScope
from .collectors import (
    BusinessMetricsCollector,
    EnhancedMetricsCollector,
    QualityMetricsCollector,
    SystemMetricsCollector,
)
from .dashboard import DashboardConfig, MonitoringDashboard, WidgetConfig
from .environment import EnvironmentAwareMonitor, EnvironmentConfig, EnvironmentDetector
from .storage import InMemoryStorage, JSONStorage, MetricsStorage, SQLiteStorage

__all__ = [
    # Architecture
    "MonitoringArchitecture",
    "MonitoringConfig",
    "MonitoringScope",
    # Collectors
    "EnhancedMetricsCollector",
    "SystemMetricsCollector",
    "BusinessMetricsCollector",
    "QualityMetricsCollector",
    # Environment
    "EnvironmentAwareMonitor",
    "EnvironmentConfig",
    "EnvironmentDetector",
    # Alerting
    "IntelligentAlertingSystem",
    "AlertRule",
    "Alert",
    "AlertSeverity",
    # Storage
    "MetricsStorage",
    "InMemoryStorage",
    "JSONStorage",
    "SQLiteStorage",
    # Analysis
    "PerformanceTrendAnalyzer",
    "TrendAnalysis",
    "AnomalyDetector",
    # Dashboard
    "MonitoringDashboard",
    "DashboardConfig",
    "WidgetConfig",
]
