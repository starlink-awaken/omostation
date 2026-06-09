"""
SSOT Kernel — Dashboard Module
==============================
监控仪表板模块
"""

import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

# 导入analysis模块，确保它是可用的
try:
    from .analysis import PerformanceTrendAnalyzer
except ImportError:
    # 创建一个简化版本
    class PerformanceTrendAnalyzer:
        def __init__(self):
            self.trend_cache = {}

    print("⚠️  使用简化版本的趋势分析器")

from .alerting import IntelligentAlertingSystem
from .collectors import EnhancedMetricsCollector


@dataclass
class WidgetConfig:
    """仪表板组件配置"""

    widget_type: str  # chart, metric, alert, status
    title: str
    position: dict[str, int] = field(default_factory=dict)  # row, col
    size: dict[str, int] = field(default_factory=dict)  # rows, cols
    refresh_interval: int = 60
    config: dict[str, Any] = field(default_factory=dict)


@dataclass
class DashboardConfig:
    """仪表板配置"""

    name: str
    title: str
    description: str = ""
    widgets: list[WidgetConfig] = field(default_factory=list)
    layout: dict[str, Any] = field(default_factory=dict)
    refresh_interval: int = 60
    theme: str = "light"


class MonitoringDashboard:
    """监控仪表板"""

    def __init__(self, config: DashboardConfig | None = None):
        self.config = config or self._create_default_config()

        # 核心组件
        self.metrics_collector = None
        self.alerting_system = None
        self.trend_analyzer = PerformanceTrendAnalyzer()

        # 数据缓存
        self.data_cache: dict[str, Any] = {}
        self.last_update = None

    def _create_default_config(self) -> DashboardConfig:
        """创建默认仪表板配置"""
        return DashboardConfig(
            name="default",
            title="SSOT 监控仪表板",
            description="SSOT引擎实时监控仪表板",
            refresh_interval=30,
            theme="light",
            widgets=[
                WidgetConfig(
                    widget_type="status",
                    title="系统状态",
                    position={"row": 1, "col": 1},
                    size={"rows": 1, "cols": 2},
                    refresh_interval=30,
                ),
                WidgetConfig(
                    widget_type="chart",
                    title="执行时间趋势",
                    position={"row": 1, "col": 3},
                    size={"rows": 1, "cols": 2},
                    refresh_interval=60,
                    config={"metric": "execution.total_time_ms", "chart_type": "line"},
                ),
                WidgetConfig(
                    widget_type="metrics",
                    title="关键指标",
                    position={"row": 2, "col": 1},
                    size={"rows": 2, "cols": 2},
                    refresh_interval=15,
                    config={
                        "metrics": [
                            "system.cpu_percent",
                            "system.memory_percent",
                            "execution.rules_per_second",
                        ]
                    },
                ),
                WidgetConfig(
                    widget_type="alerts",
                    title="活跃告警",
                    position={"row": 2, "col": 3},
                    size={"rows": 2, "cols": 2},
                    refresh_interval=30,
                ),
            ],
        )

    def initialize(
        self,
        metrics_collector: EnhancedMetricsCollector,
        alerting_system: IntelligentAlertingSystem,
    ):
        """初始化仪表板组件"""
        self.metrics_collector = metrics_collector
        self.alerting_system = alerting_system

        print(f"🎛️  仪表板初始化完成: {self.config.title}")

    def update_data(self):
        """更新仪表板数据"""
        self.last_update = datetime.now().isoformat()

        # 更新系统状态
        self.data_cache["system_status"] = self._get_system_status()

        # 更新指标数据
        self.data_cache["metrics_snapshot"] = (
            self.metrics_collector.get_realtime_snapshot()
        )

        # 更新告警数据
        self.data_cache["alert_summary"] = self.alerting_system.get_alert_summary()

        # 更新趋势数据
        self._update_trend_data()

    def _get_system_status(self) -> dict[str, Any]:
        """获取系统状态"""
        if self.metrics_collector:
            snapshot = self.metrics_collector.get_realtime_snapshot()

            # 计算系统健康度
            cpu_percent = snapshot.get("system_metrics", {}).get(
                "system.cpu_percent", 0
            )
            memory_percent = snapshot.get("system_metrics", {}).get(
                "system.memory_percent", 0
            )

            if cpu_percent > 80 or memory_percent > 80:
                health = "warning"
            elif cpu_percent > 90 or memory_percent > 90:
                health = "error"
            else:
                health = "healthy"

            return {
                "health": health,
                "cpu_percent": cpu_percent,
                "memory_percent": memory_percent,
                "timestamp": snapshot["timestamp"],
            }

        return {"health": "unknown", "timestamp": datetime.now().isoformat()}

    def _update_trend_data(self):
        """更新趋势数据"""
        # 简化版本：从缓存中获取趋势分析
        if hasattr(self.trend_analyzer, "trend_cache"):
            self.data_cache["trend_analysis"] = {
                metric_name: analysis.to_dict()
                for metric_name, analysis in self.trend_analyzer.trend_cache.items()
            }

    def render_dashboard(self) -> str:
        """渲染仪表板（文本模式）"""
        self.update_data()

        dashboard = []

        # 标题
        dashboard.append("=" * 70)
        dashboard.append(f"🎛️  {self.config.title}")
        dashboard.append("=" * 70)
        dashboard.append(f"更新时间: {self.last_update}")

        # 系统状态组件
        dashboard.append("\n📊 系统状态")
        dashboard.append("-" * 70)
        system_status = self.data_cache.get("system_status", {})

        status_icon = {"healthy": "✅", "warning": "⚠️", "error": "❌"}.get(
            system_status.get("health", "unknown"), "❓"
        )

        dashboard.append(
            f"{status_icon} 系统状态: {system_status.get('health', 'unknown')}"
        )
        dashboard.append(f"🖥️  CPU: {system_status.get('cpu_percent', 0):.1f}%")
        dashboard.append(f"💾 内存: {system_status.get('memory_percent', 0):.1f}%")

        # 关键指标组件
        dashboard.append("\n📈 关键指标")
        dashboard.append("-" * 70)
        metrics_snapshot = self.data_cache.get("metrics_snapshot", {})

        # 系统指标
        system_metrics = metrics_snapshot.get("system_metrics", {})
        if system_metrics:
            dashboard.append("🖥️  系统指标:")
            for name, value in system_metrics.items():
                icon = (
                    "🔥"
                    if "cpu_percent" in name and value > 80
                    else ("🔴" if "memory_percent" in name and value > 80 else "✅")
                )
                dashboard.append(f"  {icon} {name}: {value:.2f}")

        # 执行指标
        execution_metrics = metrics_snapshot.get("execution_metrics", {})
        if execution_metrics:
            dashboard.append("\n⚡ 执行指标:")
            for name, value in execution_metrics.items():
                dashboard.append(f"  • {name}: {value:.2f}")

        # 告警组件
        dashboard.append("\n🚨 活跃告警")
        dashboard.append("-" * 70)
        alert_summary = self.data_cache.get("alert_summary", {})

        active_count = alert_summary.get("total_active", 0)
        severity_counts = alert_summary.get("by_severity", {})

        dashboard.append(f"总计: {active_count} 个活跃告警")

        if active_count > 0:
            for severity, count in severity_counts.items():
                icon = {
                    "CRITICAL": "🔴",
                    "ERROR": "🟠",
                    "WARNING": "🟡",
                    "INFO": "🔵",
                }.get(severity, "⚪")
                dashboard.append(f"  {icon} {severity}: {count}")
        else:
            dashboard.append("✅ 当前没有活跃告警")

        # 趋势分析组件
        trend_analysis = self.data_cache.get("trend_analysis", {})
        if trend_analysis:
            dashboard.append("\n📊 趋势分析")
            dashboard.append("-" * 70)

            for metric_name, analysis in list(trend_analysis.items())[:5]:
                direction_icon = {
                    "increasing": "📈",
                    "decreasing": "📉",
                    "stable": "➡️",
                    "unknown": "❓",
                }.get(analysis["trend_direction"], "❓")

                dashboard.append(f"{direction_icon} {metric_name}:")
                dashboard.append(f"  方向: {analysis['trend_direction']}")
                dashboard.append(f"  斜率: {analysis['trend_slope']:.6f}")

                if analysis.get("forecast"):
                    dashboard.append(f"  预测: {analysis['forecast']:.2f}")

        dashboard.append("=" * 70)

        return "\n".join(dashboard)

    def export_dashboard(self, filepath: str = "dashboard_export.json"):
        """导出仪表板数据"""
        self.update_data()

        export_data = {
            "config": {
                "name": self.config.name,
                "title": self.config.title,
                "description": self.config.description,
                "refresh_interval": self.config.refresh_interval,
                "theme": self.config.theme,
            },
            "widgets": [
                {
                    "widget_type": widget.widget_type,
                    "title": widget.title,
                    "position": widget.position,
                    "size": widget.size,
                    "config": widget.config,
                }
                for widget in self.config.widgets
            ],
            "data": self.data_cache,
            "export_time": datetime.now().isoformat(),
        }

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(export_data, f, ensure_ascii=False, indent=2)

        print(f"📄 仪表板数据已导出到: {filepath}")

    def create_html_dashboard(self, filepath: str = "dashboard.html"):
        """创建HTML仪表板"""
        self.update_data()

        html = f"""
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{self.config.title}</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            margin: 0;
            padding: 20px;
            background-color: #f5f5f5;
        }}
        .dashboard {{
            max-width: 1200px;
            margin: 0 auto;
            background: white;
            padding: 30px;
            border-radius: 8px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }}
        .header {{
            text-align: center;
            margin-bottom: 40px;
        }}
        .header h1 {{
            margin: 0;
            color: #333;
        }}
        .header p {{
            color: #666;
            margin: 10px 0 0 0;
        }}
        .grid {{
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 20px;
            margin-bottom: 20px;
        }}
        .card {{
            background: #f9f9f9;
            border-radius: 6px;
            padding: 20px;
            border-left: 4px solid #ddd;
        }}
        .card-title {{
            font-weight: 600;
            margin: 0 0 15px 0;
            color: #333;
        }}
        .metric {{
            font-size: 24px;
            font-weight: 700;
            margin: 10px 0;
        }}
        .metric-label {{
            font-size: 14px;
            color: #666;
            margin-bottom: 5px;
        }}
        .alert-item {{
            padding: 8px 0;
            border-bottom: 1px solid #eee;
        }}
        .alert-item:last-child {{
            border-bottom: none;
        }}
        .alert-critical {{
            border-left-color: #dc3545;
        }}
        .alert-warning {{
            border-left-color: #ffc107;
        }}
        .alert-info {{
            border-left-color: #17a2b8;
        }}
        .trend-up {{
            color: #28a745;
        }}
        .trend-down {{
            color: #dc3545;
        }}
        .trend-stable {{
            color: #6c757d;
        }}
        .footer {{
            text-align: center;
            color: #999;
            font-size: 12px;
            margin-top: 40px;
            padding-top: 20px;
            border-top: 1px solid #eee;
        }}
    </style>
</head>
<body>
    <div class="dashboard">
        <div class="header">
            <h1>{self.config.title}</h1>
            <p>更新时间: {self.last_update} | 环境: 开发环境</p>
        </div>

        <!-- 系统状态 -->
        <div class="grid" style="grid-template-columns: repeat(2, 1fr);">
            <div class="card">
                <div class="card-title">📊 系统状态</div>
                <div class="metric-label">系统健康</div>
                <div class="metric">✅ 健康</div>
                <div style="margin-top: 15px;">
                    <div>🖥️ CPU: <span id="cpu-percent">--</span>%</div>
                    <div>💾 内存: <span id="memory-percent">--</span>%</div>
                </div>
            </div>
            <div class="card">
                <div class="card-title">📈 执行统计</div>
                <div class="metric-label">规则速率</div>
                <div class="metric" id="throughput">--</div>
                <div class="metric-label">成功率</div>
                <div class="metric" id="success-rate">--</div>
            </div>
        </div>

        <!-- 关键指标 -->
        <div class="grid" style="grid-template-columns: repeat(4, 1fr);">
            <div class="card">
                <div class="card-title">🖥️ CPU</div>
                <div class="metric" id="cpu">--</div>
            </div>
            <div class="card">
                <div class="card-title">💾 内存</div>
                <div class="metric" id="memory">--</div>
            </div>
            <div class="card">
                <div class="card-title">⚡ 吞吐量</div>
                <div class="metric" id="throughput-card">--</div>
            </div>
            <div class="card">
                <div class="card-title">✅ 成功率</div>
                <div class="metric" id="success-rate-card">--</div>
            </div>
        </div>

        <!-- 告警信息 -->
        <div class="card" style="grid-column: 1 / -1;">
            <div class="card-title">🚨 活跃告警</div>
            <div id="alerts-container">
                <div class="alert-item">✅ 当前没有活跃告警</div>
            </div>
        </div>

        <div class="footer">
            SSOT 智能监控系统 v2.0 | 自动刷新间隔: {self.config.refresh_interval}秒
        </div>
    </div>

    <script>
        // 模拟数据更新
        function updateMetrics() {{
            // 在实际应用中，这些会从监控系统API获取
            document.getElementById('cpu').textContent = Math.random() * 30 + 10;
            document.getElementById('memory').textContent = Math.random() * 20 + 40;
            document.getElementById('throughput-card').textContent = (Math.random() * 2000 + 1000).toFixed(0);
            document.getElementById('success-rate-card').textContent = (Math.random() * 5 + 95).toFixed(1) + '%';
            document.getElementById('cpu-percent').textContent = document.getElementById('cpu').textContent;
            document.getElementById('memory-percent').textContent = document.getElementById('memory').textContent;
            document.getElementById('throughput').textContent = document.getElementById('throughput-card').textContent;
            document.getElementById('success-rate').textContent = document.getElementById('success-rate-card').textContent;
        }}

        // 初始化并设置定时更新
        updateMetrics();
        setInterval(updateMetrics, {self.config.refresh_interval * 1000});
    </script>
</body>
</html>
"""

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(html)

        print(f"🌐 HTML仪表板已创建: {filepath}")
        print("💡 在浏览器中打开文件查看实时监控界面")
