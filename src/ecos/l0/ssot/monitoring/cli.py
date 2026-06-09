"""
SSOT Kernel — Monitoring CLI
===============================
监控命令行接口

命令：
1. monitor start - 启动监控
2. monitor status - 显示监控状态
3. monitor alerts - 查看告警信息
4. monitor metrics - 查看指标
5. monitor report - 生成监控报告
"""

import argparse
import json
import sys
from datetime import datetime
from typing import Any

from .alerting import AlertSeverity, IntelligentAlertingSystem
from .architecture import get_monitoring_architecture
from .collectors import EnhancedMetricsCollector
from .environment import get_environment_manager


class MonitoringCLI:
    """监控命令行接口"""

    def __init__(self):
        self.architecture = get_monitoring_architecture()
        self.environment_manager = get_environment_manager()
        self.monitor = self.environment_manager.get_monitor("default")
        self.metrics_collector = EnhancedMetricsCollector(self.monitor)
        self.alerting_system = IntelligentAlertingSystem(self.monitor)

    def cmd_start(self, args):
        """启动监控"""
        print("🚀 启动SSOT智能监控系统...")

        if args.duration:
            self._run_with_duration(args.duration, args)
        else:
            self._show_monitoring_status()

    def _run_with_duration(self, duration: int, args: Any | None = None):
        """运行指定时长的监控"""
        import time

        self._show_monitoring_status()

        print(f"\n📊 监控中... (持续 {duration} 秒)")
        print("按 Ctrl+C 停止监控")

        try:
            start_time = time.time()
            last_collection = start_time

            while time.time() - start_time < duration:
                current_time = time.time()

                # 每5秒收集一次指标
                if current_time - last_collection >= 5:
                    self._collect_and_display_metrics()
                    last_collection = current_time

                time.sleep(1)

        except KeyboardInterrupt:
            print("\n⏹️  监控已手动停止")

        # 最终报告
        print("\n📋 最终监控报告:")
        self._generate_final_report()

        # 导出数据
        if args.export:
            self._export_monitoring_data(args.export)

    def _collect_and_display_metrics(self):
        """收集并显示指标"""
        # 收集系统指标
        system_metrics = self.metrics_collector.system_collector.collect_all()

        # 显示关键指标
        print(f"\n🕐 {datetime.now().strftime('%H:%M:%S')}: ", end="")

        system_dict = {m.name: m.value for m in system_metrics}

        cpu_percent = system_dict.get("system.cpu_percent", 0)
        memory_percent = system_dict.get("system.memory_percent", 0)

        status_icon = "✅"
        if cpu_percent > 80 or memory_percent > 80:
            status_icon = "⚠️"

        print(f"{status_icon} CPU: {cpu_percent:.1f}% | 内存: {memory_percent:.1f}%")

        # 检查告警
        self._check_alerts(system_dict)

    def _check_alerts(self, metrics: dict):
        """检查告警条件"""
        new_alerts = self.alerting_system.evaluate_metrics(metrics)

        if new_alerts:
            for alert in new_alerts:
                severity_icon = {
                    "INFO": "🔵",
                    "WARNING": "🟡",
                    "ERROR": "🟠",
                    "CRITICAL": "🔴",
                    "FATAL": "🚨",
                }.get(alert.severity.value, "⚪")

                print(f"  {severity_icon} {alert.name}: {alert.message}")

    def _show_monitoring_status(self):
        """显示监控状态"""
        health = self.architecture.get_system_health()

        print("\n🏥 SSOT 监控系统状态")
        print("=" * 60)

        status_icon = (
            "✅"
            if health["status"] == "healthy"
            else ("⚠️" if health["status"] == "warning" else "❌")
        )
        print(f"系统状态: {status_icon} {health['status']}")

        # 环境信息
        env_info = self.architecture.get_environment_info()
        print("\n🌍 运行环境:")
        print(f"  环境: {env_info['environment']}")
        print(f"  采样率: {env_info['sample_rate'] * 100:.0f}%")
        print(f"  告警启用: {env_info['alert_enabled']}")

        # 指标统计
        metrics_data = health.get("metrics", {})
        print("\n📊 指标统计:")
        for scope, count in metrics_data.get("by_scope", {}).items():
            print(f"  {scope}: {count} 个指标")

        # 告警状态
        alert_summary = self.alerting_system.get_alert_summary()
        print("\n🚨 告警状态:")
        print(f"  活跃告警: {alert_summary['total_active']}")

        for severity, count in alert_summary["by_severity"].items():
            icon = {"CRITICAL": "🔴", "ERROR": "🟠", "WARNING": "🟡", "INFO": "🔵"}.get(
                severity, "⚪"
            )
            print(f"  {icon} {severity}: {count}")

        # 组件状态
        print("\n🔧 组件状态:")
        for name, component_health in health.get("components", {}).items():
            comp_status = component_health.get("status", "unknown")
            icon = (
                "✅"
                if comp_status == "healthy"
                else ("⚠️" if comp_status == "warning" else "❌")
            )
            print(f"  {icon} {name}: {comp_status}")

        print("=" * 60)

    def _generate_final_report(self):
        """生成最终报告"""
        print("\n📊 监控摘要:")

        # 执行统计
        if hasattr(
            self.metrics_collector.execution_collector, "get_execution_statistics"
        ):
            exec_stats = (
                self.metrics_collector.execution_collector.get_execution_statistics()
            )
            if exec_stats["total_executions"] > 0:
                print(f"  执行次数: {exec_stats['total_executions']}")
                print(f"  平均执行时间: {exec_stats['average_time_ms']:.2f}ms")
                print(f"  成功率: {exec_stats['success_rate'] * 100:.1f}%")
                print(f"  吞吐量: {exec_stats['throughput']:.1f} rules/s")

        # 环境统计
        env_summary = self.monitor.get_environment_summary()
        stats = env_summary["statistics"]
        print("\n📈 采样统计:")
        print(f"  总采集: {stats['collections']}")
        print(f"  实际采样: {stats['samples_taken']}")
        print(f"  跳过采样: {stats['samples_skipped']}")

        # 告警统计
        alert_summary = self.alerting_system.get_alert_summary()
        print("\n🚨 告警统计:")
        print(f"  总生成: {alert_summary['total_generated']}")
        print(f"  总抑制: {alert_summary['total_suppressed']}")
        print(f"  总解决: {alert_summary['total_resolved']}")

    def _export_monitoring_data(self, filepath: str):
        """导出监控数据"""
        data = {
            "export_time": datetime.now().isoformat(),
            "environment_info": self.architecture.get_environment_info(),
            "environment_summary": self.monitor.get_environment_summary(),
            "system_health": self.architecture.get_system_health(),
            "alert_summary": self.alerting_system.get_alert_summary(),
            "metrics_snapshot": self.metrics_collector.get_realtime_snapshot(),
        }

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        print(f"📄 监控数据已导出到: {filepath}")

    def cmd_status(self, args):
        """显示监控状态"""
        self._show_monitoring_status()

        # 系统诊断
        if args.detailed:
            print("\n🔍 系统诊断:")
            diagnostic = self.architecture.generate_diagnostic_report()
            print(diagnostic)

    def cmd_alerts(self, args):
        """查看告警信息"""
        severity_filter = args.severity if args.severity else None

        if severity_filter:
            try:
                severity = AlertSeverity[severity_filter.upper()]
                active_alerts = self.alerting_system.get_active_alerts(severity)
            except ValueError:
                print(f"❌ 无效的严重程度: {args.severity}")
                print("可用选项: INFO, WARNING, ERROR, CRITICAL, FATAL")
                return 1
        else:
            active_alerts = self.alerting_system.get_active_alerts()

        print(f"\n🚨 活跃告警: {len(active_alerts)} 个")

        if not active_alerts:
            print("✅ 当前没有活跃告警")
            return 0

        for alert in active_alerts:
            severity_icon = {
                "INFO": "🔵",
                "WARNING": "🟡",
                "ERROR": "🟠",
                "CRITICAL": "🔴",
                "FATAL": "🚨",
            }.get(alert.severity.value, "⚪")

            print(f"\n{severity_icon} [{alert.severity.value}] {alert.name}")
            print(f"  时间: {alert.timestamp}")
            print(f"  消息: {alert.message}")
            print(f"  状态: {alert.status.value}")

            if alert.metrics_data:
                trigger_value = alert.metrics_data.get("trigger_value", "N/A")
                threshold = alert.metrics_data.get("threshold", "N/A")
                print(f"  触发值: {trigger_value} (阈值: {threshold})")

            if alert.recommendations:
                print("  建议:")
                for i, rec in enumerate(alert.recommendations[:3], 1):
                    print(f"    {i}. {rec}")

        # 告警统计
        if args.stats:
            alert_summary = self.alerting_system.get_alert_summary()
            print("\n📊 告警统计:")
            print(f"  活跃: {alert_summary['total_active']}")
            print(f"  总生成: {alert_summary['total_generated']}")
            print(f"  总抑制: {alert_summary['total_suppressed']}")
            print(f"  总解决: {alert_summary['total_resolved']}")

        # 生成报告
        if args.report:
            report = self.alerting_system.generate_alert_report()
            print(f"\n{report}")

        return 0

    def cmd_metrics(self, args):
        """查看指标"""
        snapshot = self.metrics_collector.get_realtime_snapshot()

        if args.category == "all":
            categories = ["system", "execution", "business", "quality"]
        else:
            categories = [args.category]

        print("📊 实时指标快照")
        print(f"时间: {snapshot['timestamp']}")
        print(f"环境: {snapshot['environment']}")
        print("=" * 60)

        for category in categories:
            metrics = snapshot.get(f"{category}_metrics", {})

            if metrics:
                print(f"\n📈 {category.upper()} 指标:")
                for name, value in metrics.items():
                    print(f"  {name}: {value:.2f}")
            else:
                print(f"\n⚪ {category.upper()}: 无数据")

        if args.history:
            print(f"\n📊 指标历史 (最近{args.history}分钟):")

            for category in categories:
                # 获取聚合指标
                for metric_name in list(snapshot.get(f"{category}_metrics", {}).keys()):
                    aggregated = self.metrics_collector.aggregate_metrics(
                        metric_name, time_window_minutes=args.history
                    )

                    if aggregated:
                        print(f"\n{metric_name}:")
                        print(f"  数量: {aggregated.count}")
                        print(f"  平均: {aggregated.avg:.2f}")
                        print(f"  范围: {aggregated.min:.2f} - {aggregated.max:.2f}")
                        if aggregated.p95:
                            print(f"  P95: {aggregated.p95:.2f}")

        if args.export:
            self._export_monitoring_data(args.export)

        return 0

    def cmd_report(self, args):
        """生成监控报告"""
        print("📋 生成SSOT监控报告...")

        # 综合报告
        print(f"\n{'=' * 60}")
        print("📊 SSOT智能监控系统综合报告")
        print(f"{'=' * 60}")

        # 系统健康
        health = self.architecture.get_system_health()
        print("\n🏥 系统健康:")
        status_icon = (
            "✅"
            if health["status"] == "healthy"
            else ("⚠️" if health["status"] == "warning" else "❌")
        )
        print(f"  {status_icon} 状态: {health['status']}")

        # 环境概览
        env_overview = self.environment_manager.get_environment_overview()
        print("\n🌍 环境概览:")
        print(f"  总环境数: {env_overview['total_environments']}")
        print(f"  活跃环境: {env_overview['active_environment']}")

        # 指标收集器报告
        collector_report = self.metrics_collector.generate_summary_report()
        print(collector_report)

        # 告警报告
        alert_report = self.alerting_system.generate_alert_report()
        print(alert_report)

        # 导出报告
        if args.export:
            self._export_monitoring_data(args.export)

        return 0


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        prog="ssot-monitor", description="SSOT 智能监控工具"
    )

    subparsers = parser.add_subparsers(dest="command", help="子命令")

    # monitor start
    p_start = subparsers.add_parser("start", help="启动监控")
    p_start.add_argument("--duration", type=int, help="监控时长（秒）")
    p_start.add_argument("--export", help="导出数据到文件")

    # monitor status
    p_status = subparsers.add_parser("status", help="显示监控状态")
    p_status.add_argument("--detailed", "-d", action="store_true", help="详细信息")

    # monitor alerts
    p_alerts = subparsers.add_parser("alerts", help="查看告警信息")
    p_alerts.add_argument("--severity", help="过滤严重程度")
    p_alerts.add_argument("--stats", action="store_true", help="显示统计信息")
    p_alerts.add_argument("--report", action="store_true", help="生成告警报告")

    # monitor metrics
    p_metrics = subparsers.add_parser("metrics", help="查看指标")
    p_metrics.add_argument(
        "--category",
        choices=["system", "execution", "business", "quality", "all"],
        default="all",
        help="指标类别",
    )
    p_metrics.add_argument("--history", type=int, help="历史时间窗口（分钟）")
    p_metrics.add_argument("--export", help="导出数据到文件")

    # monitor report
    p_report = subparsers.add_parser("report", help="生成监控报告")
    p_report.add_argument("--export", help="导出报告到文件")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 0

    cli = MonitoringCLI()

    if args.command == "start":
        return cli.cmd_start(args)
    elif args.command == "status":
        return cli.cmd_status(args)
    elif args.command == "alerts":
        return cli.cmd_alerts(args)
    elif args.command == "metrics":
        return cli.cmd_metrics(args)
    elif args.command == "report":
        return cli.cmd_report(args)
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())
