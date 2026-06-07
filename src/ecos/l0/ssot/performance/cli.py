"""
SSOT Kernel — Performance CLI
================================
性能测试命令行接口

命令：
1. benchmark - 运行性能基准测试
2. baseline - 管理性能基线
3. compare - 对比性能结果
4. monitor - 启动性能监控
"""

import argparse
import sys
from datetime import datetime

from .benchmark import (
    ComplexDependencyBenchmark,
    ContradictionDetectionBenchmark,
    MultiRoundBenchmark,
    PerformanceBenchmark,
)
from .generators import TestDataGenerator
from .monitor import PerformanceMonitor
from .regression import PerformanceBaseline, PerformanceRegressionDetector


class PerformanceCLI:
    """性能测试命令行接口"""

    def __init__(self):
        self.benchmark = PerformanceBenchmark()
        self.regression_detector = PerformanceRegressionDetector()
        self.monitor = PerformanceMonitor()

    def cmd_benchmark(self, args):
        """运行性能基准测试"""
        print("🚀 开始性能基准测试...")

        if args.all_sizes:
            # 运行所有规模的基准测试
            results = self.benchmark.run_all_benchmarks(verbose=True)

            # 保存结果
            if args.save:
                self.benchmark.save_results(results, args.save)

            # 检测回归
            if args.check_regression:
                self._check_regression(results)

        elif args.scenario:
            # 运行特定场景的基准测试
            self._run_scenario_benchmark(args)

        else:
            # 运行指定规模的基准测试
            result = self.benchmark.run_benchmark(size=args.size, verbose=args.verbose)

            if args.save:
                # 单个测试结果需要特殊处理
                import json

                data = {
                    "timestamp": datetime.now().isoformat(),
                    "results": {
                        result.config.name: {
                            "config": {
                                "name": result.config.name,
                                "rule_count": result.config.rule_count,
                                "target_execution_time": result.config.target_execution_time,
                                "target_memory_mb": result.config.target_memory_mb,
                            },
                            "metrics": {
                                "total_execution_time_ms": result.metrics.total_execution_time_ms,
                                "peak_memory_usage_mb": result.metrics.peak_memory_usage_mb,
                                "rules_per_second": result.metrics.rules_per_second,
                                "passed_rules": result.metrics.passed_rules,
                                "failed_rules": result.metrics.failed_rules,
                                "blocked_rules": result.metrics.blocked_rules,
                                "performance_score": result.performance_score,
                            },
                            "performance_score": result.performance_score,
                            "meets_target": result.meets_target,
                            "success": result.success,
                        }
                    },
                }

                with open(args.save, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                print(f"📄 测试结果已保存到: {args.save}")

            # 检测回归
            if args.check_regression:
                baseline = self.regression_detector.load_baseline()
                if baseline:
                    report = self.regression_detector.detect_regression(result, baseline)
                    report.print_summary()

    def _run_scenario_benchmark(self, args):
        """运行场景基准测试"""
        scenario = args.scenario

        if scenario == "contradiction":
            print("🔍 运行矛盾检测场景测试...")
            benchmark = ContradictionDetectionBenchmark()
            result = benchmark.run(rule_count=args.rule_count or 1000, verbose=True)

        elif scenario == "multi_round":
            print("🔄 运行多轮迭代场景测试...")
            benchmark = MultiRoundBenchmark()
            results = benchmark.run(verbose=True)

            for rounds, result in results.items():
                print(f"  轮次 {rounds}: {result.metrics.total_execution_time_ms / 1000:.2f}s")

        elif scenario == "complex_dependency":
            print("🔗 运行复杂依赖场景测试...")
            benchmark = ComplexDependencyBenchmark()
            result = benchmark.run(complexity_level=args.complexity or "medium", verbose=True)

        else:
            print(f"❌ 未知场景: {scenario}")
            print("可用场景: contradiction, multi_round, complex_dependency")
            return 1

        return 0

    def _check_regression(self, results):
        """检查性能回归"""
        baseline = self.regression_detector.load_baseline()
        if not baseline:
            print("⚠️  未找到性能基线，将使用当前结果创建新基线")

            # 创建新基线
            self.regression_detector.create_baseline(results, name="initial_baseline", version="1.0")
            print("✅ 新基线已创建")
            return

        # 批量检测回归
        reports = self.regression_detector.batch_detect_regression(results, baseline)

        # 打印回归摘要
        print(f"\n{'=' * 60}")
        print("🔍 性能回归检测摘要")
        print(f"{'=' * 60}")

        regression_count = sum(1 for r in reports.values() if r.has_regression)
        print(f"检测到回归: {regression_count}/{len(reports)}")

        for name, report in reports.items():
            if report.has_regression:
                print(f"🚨 {name}: {report.severity.value}")
            else:
                print(f"✅ {name}: 无回归")

        if regression_count > 0:
            return 1
        return 0

    def cmd_baseline(self, args):
        """管理性能基线"""
        if args.create:
            # 创建新基线
            print("📊 创建性能基线...")

            # 运行所有基准测试
            results = self.benchmark.run_all_benchmarks(verbose=False)

            # 创建基线
            baseline = self.regression_detector.create_baseline(
                results, name=args.name or "baseline", version=args.version or "1.0"
            )

            print(f"✅ 基线已创建: {baseline.name} v{baseline.version}")

        elif args.show:
            # 显示当前基线
            baseline = self.regression_detector.load_baseline()
            if baseline:
                self._show_baseline(baseline)
            else:
                print("❌ 未找到性能基线")
                return 1

        elif args.delete:
            # 删除基线
            import os

            if os.path.exists(self.regression_detector.baseline_file):
                os.remove(self.regression_detector.baseline_file)
                print("🗑️  基线已删除")
            else:
                print("❌ 基线文件不存在")
                return 1

        else:
            print("❌ 请指定操作: --create, --show, --delete")
            return 1

        return 0

    def _show_baseline(self, baseline: PerformanceBaseline):
        """显示基线信息"""
        print(f"\n{'=' * 60}")
        print("📊 性能基线信息")
        print(f"{'=' * 60}")
        print(f"名称: {baseline.name}")
        print(f"版本: {baseline.version}")
        print(f"创建时间: {baseline.created_at}")

        if baseline.system_info:
            print("\n系统信息:")
            for key, value in baseline.system_info.items():
                print(f"  {key}: {value}")

        print("\n基准测试结果:")
        for name, result in baseline.benchmark_results.items():
            print(f"  {name}:")
            print(f"    规则数: {result.config.rule_count}")
            print(f"    执行时间: {result.metrics.total_execution_time_ms / 1000:.2f}s")
            print(f"    内存使用: {result.metrics.peak_memory_usage_mb:.1f}MB")
            print(f"    性能得分: {result.metrics.performance_score:.1f}")

    def cmd_compare(self, args):
        """对比性能结果"""
        baseline_results = self.benchmark.load_results(args.baseline)
        current_results = self.benchmark.load_results(args.current)

        if not baseline_results or not current_results:
            print("❌ 无法加载结果文件")
            return 1

        # 生成对比报告
        comparison = self.benchmark.compare_results(baseline_results, current_results)

        print(f"\n{'=' * 60}")
        print("📊 性能对比报告")
        print(f"{'=' * 60}")

        for size, data in comparison.items():
            regression_icon = "🚨" if data["regression_detected"] else "✅"
            print(f"\n{regression_icon} {size.upper()} 规模:")
            print(f"  执行时间: {data['time_change_percent']:+.1f}%")
            print(f"  内存使用: {data['memory_change_percent']:+.1f}%")
            print(
                f"  性能得分: {data['baseline_score']:.1f} → {data['current_score']:.1f} ({data['score_change']:+.1f})"
            )

            if data["regression_detected"]:
                print("  🚨 检测到性能回归!")

        # 检查是否有严重回归
        severe_regressions = [size for size, data in comparison.items() if data["regression_detected"]]
        if severe_regressions:
            print(f"\n🚨 检测到性能回归: {', '.join(severe_regressions)}")
            return 1

        print("\n✅ 未检测到严重性能回归")
        return 0

    def cmd_monitor(self, args):
        """启动性能监控"""
        print("📊 启动性能监控...")

        if args.duration:
            # 监控指定时长
            import time

            self.monitor.start_monitoring()
            print(f"监控中... (持续 {args.duration} 秒)")

            try:
                time.sleep(args.duration)
            except KeyboardInterrupt:
                print("\n⏹️  监控已手动停止")

            self.monitor.stop_monitoring()

            # 导出监控数据
            if args.export:
                self.monitor.export_metrics(args.export)

            # 显示摘要
            summary = self.monitor.get_performance_summary()
            print("\n📊 性能监控摘要:")
            print(f"  总执行次数: {summary.get('total_executions', 0)}")
            print(f"  平均执行时间: {summary.get('average_duration_ms', 0) / 1000:.2f}s")

            if summary.get("resource_usage"):
                resource = summary["resource_usage"]
                print(f"  平均CPU使用: {resource.get('cpu_percent', 0):.1f}%")
                print(f"  平均内存使用: {resource.get('memory_usage_mb', 0):.1f}MB")

        else:
            print("❌ 请指定监控时长 --duration")
            return 1

        return 0

    def cmd_generate_test_data(self, args):
        """生成测试数据"""
        print("🔧 生成测试数据...")

        generator = TestDataGenerator()

        if args.dataset_type == "standard":
            domain = generator.generate_test_domain(
                entity_count=args.entity_count or 100,
                fact_count=args.fact_count or 200,
                rule_count=args.rule_count or 500,
                inference_count=args.inference_count or 50,
                relation_count=args.relation_count or 20,
            )
        elif args.dataset_type == "contradiction":
            domain = generator.generate_contradiction_test_domain(rule_count=args.rule_count or 800)
        elif args.dataset_type == "complex_dependency":
            domain = generator.generate_complex_dependency_domain(
                entity_count=args.entity_count or 150,
                fact_count=args.fact_count or 300,
                dependency_depth=args.depth or 8,
            )
        else:
            print(f"❌ 未知数据集类型: {args.dataset_type}")
            return 1

        # 保存测试数据
        if args.output:
            import json

            # 将DomainConfig转换为可序列化的格式
            data = {
                "domain": domain.domain,
                "entities_count": len(domain.entities),
                "facts_count": len(domain.facts),
                "rules_count": len(domain.rules),
                "inferences_count": len(domain.inferences),
                "relations_count": len(domain.relations),
                "timestamp": datetime.now().isoformat(),
            }

            with open(args.output, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

            print(f"📄 测试数据元信息已保存到: {args.output}")
        else:
            print("✅ 测试数据生成完成:")
            print(f"  实体: {len(domain.entities)}")
            print(f"  事实: {len(domain.facts)}")
            print(f"  规则: {len(domain.rules)}")
            print(f"  推论: {len(domain.inferences)}")
            print(f"  关系: {len(domain.relations)}")

        return 0


def main():
    """主函数"""
    parser = argparse.ArgumentParser(prog="ssot-performance", description="SSOT 性能测试工具")

    subparsers = parser.add_subparsers(dest="command", help="子命令")

    # benchmark 子命令
    p_benchmark = subparsers.add_parser("benchmark", help="运行性能基准测试")
    p_benchmark.add_argument("--size", choices=["small", "medium", "large"], help="测试规模")
    p_benchmark.add_argument(
        "--scenario", choices=["contradiction", "multi_round", "complex_dependency"], help="测试场景"
    )
    p_benchmark.add_argument("--all-sizes", action="store_true", help="运行所有规模的基准测试")
    p_benchmark.add_argument("--rule-count", type=int, help="规则数量（用于场景测试）")
    p_benchmark.add_argument("--complexity", choices=["low", "medium", "high"], help="复杂依赖测试的复杂度")
    p_benchmark.add_argument("--verbose", "-v", action="store_true", help="详细输出")
    p_benchmark.add_argument("--save", help="保存结果到文件")
    p_benchmark.add_argument("--check-regression", action="store_true", help="检查性能回归")

    # baseline 子命令
    p_baseline = subparsers.add_parser("baseline", help="管理性能基线")
    p_baseline.add_argument("--create", action="store_true", help="创建新基线")
    p_baseline.add_argument("--show", action="store_true", help="显示当前基线")
    p_baseline.add_argument("--delete", action="store_true", help="删除基线")
    p_baseline.add_argument("--name", help="基线名称")
    p_baseline.add_argument("--version", help="基线版本")

    # compare 子命令
    p_compare = subparsers.add_parser("compare", help="对比性能结果")
    p_compare.add_argument("--baseline", required=True, help="基线结果文件路径")
    p_compare.add_argument("--current", required=True, help="当前结果文件路径")

    # monitor 子命令
    p_monitor = subparsers.add_parser("monitor", help="性能监控")
    p_monitor.add_argument("--duration", type=int, required=True, help="监控时长（秒）")
    p_monitor.add_argument("--export", help="导出监控数据到文件")

    # generate 子命令
    p_generate = subparsers.add_parser("generate", help="生成测试数据")
    p_generate.add_argument(
        "--dataset-type",
        choices=["standard", "contradiction", "complex_dependency"],
        default="standard",
        help="数据集类型",
    )
    p_generate.add_argument("--entity-count", type=int, help="实体数量")
    p_generate.add_argument("--fact-count", type=int, help="事实数量")
    p_generate.add_argument("--rule-count", type=int, help="规则数量")
    p_generate.add_argument("--inference-count", type=int, help="推论数量")
    p_generate.add_argument("--relation-count", type=int, help="关系数量")
    p_generate.add_argument("--depth", type=int, help="依赖深度")
    p_generate.add_argument("--output", help="输出文件路径")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 0

    cli = PerformanceCLI()

    if args.command == "benchmark":
        return cli.cmd_benchmark(args)
    elif args.command == "baseline":
        return cli.cmd_baseline(args)
    elif args.command == "compare":
        return cli.cmd_compare(args)
    elif args.command == "monitor":
        return cli.cmd_monitor(args)
    elif args.command == "generate":
        return cli.cmd_generate_test_data(args)
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())
