"""
SSOT Kernel — Performance Benchmark
====================================
性能基准测试核心模块

支持：
- 多规模基准测试（100/500/1000规则）
- 多轮迭代性能测试
- 内存使用监控
- 性能回归检测
"""

import json
import time
import tracemalloc
from dataclasses import dataclass, field
from datetime import datetime

from ..engine import DerivationReport, RuleEngine
from .generators import TestDataGenerator


@dataclass
class BenchmarkConfig:
    """基准测试配置"""

    name: str
    rule_count: int
    entity_count: int = 100
    fact_count: int = 200
    inference_count: int = 50
    relation_count: int = 20

    # 性能目标
    target_execution_time: float = 10.0  # 目标执行时间（秒）
    target_memory_mb: float = 512.0  # 目标内存使用（MB）

    # 测试参数
    rounds: int = 1  # 执行轮次
    parallel: bool = False  # 是否并行执行
    timeout: float = 60.0  # 超时时间（秒）


@dataclass
class PerformanceMetrics:
    """性能指标集合"""

    # 时间指标（毫秒）
    total_execution_time_ms: float = 0.0  # 总执行时间
    rule_loading_time_ms: float = 0.0  # 规则加载时间
    dependency_check_time_ms: float = 0.0  # 依赖检查时间
    rule_execution_time_ms: float = 0.0  # 规则执行时间
    report_generation_time_ms: float = 0.0  # 报告生成时间

    # 内存指标（MB）
    peak_memory_usage_mb: float = 0.0  # 峰值内存使用
    memory_leak_detected: bool = False  # 内存泄漏检测

    # 规模指标
    total_rules: int = 0  # 总规则数
    total_entities: int = 0  # 总实体数
    total_facts: int = 0  # 总事实数
    total_inferences: int = 0  # 总推论数
    total_relations: int = 0  # 总关系数

    # 效率指标
    rules_per_second: float = 0.0  # 规则执行速率
    memory_per_rule_mb: float = 0.0  # 每规则内存消耗

    # 质量指标
    passed_rules: int = 0  # 通过规则数
    failed_rules: int = 0  # 失败规则数
    blocked_rules: int = 0  # 阻塞规则数
    warn_rules: int = 0  # 警告规则数

    # 系统指标
    cpu_time_ms: float = 0.0  # CPU时间
    user_time_ms: float = 0.0  # 用户时间
    system_time_ms: float = 0.0  # 系统时间


@dataclass
class BenchmarkResult:
    """基准测试结果"""

    config: BenchmarkConfig
    metrics: PerformanceMetrics
    report: DerivationReport | None = None
    success: bool = True
    error: str | None = None
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    @property
    def performance_score(self) -> float:
        """计算性能得分（0-100）"""
        score = 100.0

        # 时间得分（权重40%）
        time_score = min(
            100, (self.config.target_execution_time * 1000) / (self.metrics.total_execution_time_ms + 0.1) * 40
        )
        score -= 40 - time_score

        # 内存得分（权重30%）
        memory_score = min(100, (self.config.target_memory_mb) / (self.metrics.peak_memory_usage_mb + 0.1) * 30)
        score -= 30 - memory_score

        # 质量得分（权重30%）
        if self.metrics.total_rules > 0:
            quality_score = (self.metrics.passed_rules / self.metrics.total_rules) * 30
            score += quality_score
        else:
            score -= 30

        return max(0, min(100, score))

    @property
    def meets_target(self) -> bool:
        """是否达到性能目标"""
        time_met = self.metrics.total_execution_time_ms <= (self.config.target_execution_time * 1000)
        memory_met = self.metrics.peak_memory_usage_mb <= self.config.target_memory_mb
        # 对于性能测试，我们主要关注性能指标，质量指标不是硬性要求
        quality_met = self.metrics.blocked_rules == 0  # 只要有阻塞就算未达到目标

        return time_met and memory_met and quality_met


class PerformanceBenchmark:
    """
    SSOT 性能基准测试框架

    功能：
    1. 多规模基准测试（100/500/1000规则）
    2. 多轮迭代性能测试
    3. 内存使用监控
    4. 性能回归检测
    """

    def __init__(self):
        self.benchmark_configs = {
            "small": BenchmarkConfig(
                name="small",
                rule_count=100,
                entity_count=50,
                fact_count=100,
                inference_count=25,
                relation_count=10,
                target_execution_time=1.0,
                target_memory_mb=128.0,
                rounds=1,
            ),
            "medium": BenchmarkConfig(
                name="medium",
                rule_count=500,
                entity_count=100,
                fact_count=200,
                inference_count=50,
                relation_count=20,
                target_execution_time=5.0,
                target_memory_mb=256.0,
                rounds=3,
            ),
            "large": BenchmarkConfig(
                name="large",
                rule_count=1000,
                entity_count=200,
                fact_count=400,
                inference_count=100,
                relation_count=40,
                target_execution_time=10.0,
                target_memory_mb=512.0,
                rounds=5,
            ),
        }

    def list_benchmarks(self) -> list[str]:
        """列出可用的基准测试"""
        return list(self.benchmark_configs.keys())

    def get_benchmark_config(self, size: str) -> BenchmarkConfig:
        """获取基准测试配置"""
        if size not in self.benchmark_configs:
            raise ValueError(f"Unknown benchmark size: {size}. Available: {self.list_benchmarks()}")
        return self.benchmark_configs[size]

    def run_benchmark(
        self, size: str = "medium", custom_config: BenchmarkConfig | None = None, verbose: bool = False
    ) -> BenchmarkResult:
        """执行基准测试"""
        config = custom_config or self.get_benchmark_config(size)

        if verbose:
            print(f"🏃 开始性能基准测试: {config.name}")
            print(f"   规则数: {config.rule_count}")
            print(f"   目标时间: {config.target_execution_time}s")
            print(f"   执行轮次: {config.rounds}")

        try:
            # 生成测试数据
            from .generators import TestDataGenerator

            generator = TestDataGenerator()
            domain = generator.generate_test_domain(
                entity_count=config.entity_count,
                fact_count=config.fact_count,
                rule_count=config.rule_count,
                inference_count=config.inference_count,
                relation_count=config.relation_count,
            )

            if verbose:
                print(
                    f"   生成测试数据: {len(domain.entities)} entities, {len(domain.facts)} facts, {len(domain.rules)} rules"
                )

            # 开始性能监控
            tracemalloc.start()
            start_time = time.perf_counter()
            start_cpu_time = time.process_time()

            # 执行引擎
            engine = RuleEngine()
            report = engine.execute(domain, rounds=config.rounds)

            # 收集性能指标
            end_cpu_time = time.process_time()
            end_time = time.perf_counter()

            current_memory, peak_memory = tracemalloc.get_traced_memory()
            tracemalloc.stop()

            # 计算指标
            metrics = PerformanceMetrics(
                total_execution_time_ms=(end_time - start_time) * 1000,
                cpu_time_ms=(end_cpu_time - start_cpu_time) * 1000,
                total_rules=len(domain.rules),
                total_entities=len(domain.entities),
                total_facts=len(domain.facts),
                total_inferences=len(domain.inferences),
                total_relations=len(domain.relations),
                peak_memory_usage_mb=peak_memory / 1024 / 1024,
                passed_rules=report.passed,
                failed_rules=report.error,
                blocked_rules=report.blocker,
                warn_rules=report.warn,
            )

            # 计算效率指标
            if metrics.total_execution_time_ms > 0:
                metrics.rules_per_second = (metrics.total_rules * config.rounds) / (
                    metrics.total_execution_time_ms / 1000
                )
            if metrics.total_rules > 0:
                metrics.memory_per_rule_mb = metrics.peak_memory_usage_mb / metrics.total_rules

            result = BenchmarkResult(config=config, metrics=metrics, report=report, success=report.all_passed)

            if verbose:
                self._print_result(result)

            return result

        except Exception as e:
            return BenchmarkResult(config=config, metrics=PerformanceMetrics(), success=False, error=str(e))

    def run_all_benchmarks(self, verbose: bool = True) -> dict[str, BenchmarkResult]:
        """运行所有基准测试"""
        results = {}

        for size in self.list_benchmarks():
            print(f"\n{'=' * 60}")
            result = self.run_benchmark(size, verbose=verbose)
            results[size] = result

        self._print_summary(results)
        return results

    def compare_results(
        self, baseline_results: dict[str, BenchmarkResult], current_results: dict[str, BenchmarkResult]
    ) -> dict[str, dict]:
        """对比基准测试结果"""
        comparison = {}

        for size in baseline_results.keys():
            if size not in current_results:
                continue

            baseline = baseline_results[size]
            current = current_results[size]

            # 性能变化
            time_change = self._calculate_change(
                baseline.metrics.total_execution_time_ms, current.metrics.total_execution_time_ms
            )
            memory_change = self._calculate_change(
                baseline.metrics.peak_memory_usage_mb, current.metrics.peak_memory_usage_mb
            )
            score_change = current.performance_score - baseline.performance_score

            comparison[size] = {
                "time_change_percent": time_change,
                "memory_change_percent": memory_change,
                "score_change": score_change,
                "baseline_score": baseline.performance_score,
                "current_score": current.performance_score,
                "regression_detected": time_change > 20 or memory_change > 15 or score_change < -10,
            }

        return comparison

    def _print_result(self, result: BenchmarkResult):
        """打印测试结果"""
        print(f"\n📊 测试结果: {result.config.name}")
        print(
            f"   执行时间: {result.metrics.total_execution_time_ms / 1000:.2f}s (目标: {result.config.target_execution_time}s)"
        )
        print(f"   峰值内存: {result.metrics.peak_memory_usage_mb:.2f}MB (目标: {result.config.target_memory_mb}MB)")
        print(f"   规则速率: {result.metrics.rules_per_second:.1f} rules/s")
        print(
            f"   通过率: {result.metrics.passed_rules}/{result.metrics.total_rules} ({result.metrics.passed_rules / result.metrics.total_rules * 100 if result.metrics.total_rules > 0 else 0:.1f}%)"
        )
        print(f"   性能得分: {result.performance_score:.1f}/100")
        print(f"   达到目标: {'✅' if result.meets_target else '❌'}")

        if not result.success:
            print(f"   ❌ 失败: {result.error}")

    def _print_summary(self, results: dict[str, BenchmarkResult]):
        """打印测试摘要"""
        print(f"\n{'=' * 60}")
        print("🏆 基准测试摘要")
        print(f"{'=' * 60}")

        for size, result in results.items():
            status = "✅" if result.success else "❌"
            target = "🎯" if result.meets_target else "⚠️"
            print(
                f"{status} {target} {size:8s}: {result.performance_score:.1f}分, "
                f"{result.metrics.total_execution_time_ms / 1000:.2f}s, "
                f"{result.metrics.peak_memory_usage_mb:.1f}MB"
            )

        # 计算平均得分
        avg_score = sum(r.performance_score for r in results.values()) / len(results)
        print(f"\n平均性能得分: {avg_score:.1f}/100")

        # 达标统计
        target_met = sum(1 for r in results.values() if r.meets_target)
        print(f"目标达成率: {target_met}/{len(results)} ({target_met / len(results) * 100:.0f}%)")

    def _calculate_change(self, baseline: float, current: float) -> float:
        """计算变化百分比"""
        if baseline == 0:
            return 0.0
        return ((current - baseline) / baseline) * 100

    def save_results(self, results: dict[str, BenchmarkResult], filepath: str = "benchmark_results.json"):
        """保存基准测试结果"""
        data = {
            "timestamp": datetime.now().isoformat(),
            "results": {
                size: {
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
                    },
                    "performance_score": result.performance_score,
                    "meets_target": result.meets_target,
                    "success": result.success,
                }
                for size, result in results.items()
            },
        }

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        print(f"📄 基准测试结果已保存到: {filepath}")

    def load_results(self, filepath: str = "benchmark_results.json") -> dict[str, BenchmarkResult]:
        """加载基准测试结果"""
        with open(filepath, encoding="utf-8") as f:
            data = json.load(f)

        results = {}
        for size, result_data in data["results"].items():
            config = BenchmarkConfig(
                name=result_data["config"]["name"],
                rule_count=result_data["config"]["rule_count"],
                target_execution_time=result_data["config"]["target_execution_time"],
                target_memory_mb=result_data["config"]["target_memory_mb"],
            )

            metrics = PerformanceMetrics(
                total_execution_time_ms=result_data["metrics"]["total_execution_time_ms"],
                peak_memory_usage_mb=result_data["metrics"]["peak_memory_usage_mb"],
                rules_per_second=result_data["metrics"]["rules_per_second"],
                passed_rules=result_data["metrics"]["passed_rules"],
                failed_rules=result_data["metrics"]["failed_rules"],
                blocked_rules=result_data["metrics"]["blocked_rules"],
                total_rules=result_data["config"]["rule_count"],
            )

            result = BenchmarkResult(config=config, metrics=metrics, success=result_data["success"])
            results[size] = result

        return results


# 专用基准测试场景
class ContradictionDetectionBenchmark:
    """矛盾推导性能测试"""

    def run(self, rule_count: int = 1000, verbose: bool = False) -> BenchmarkResult:
        """测试大量矛盾检测规则的性能"""
        config = BenchmarkConfig(
            name="contradiction_detection",
            rule_count=rule_count,
            target_execution_time=rule_count / 100.0,  # 动态目标
            target_memory_mb=512.0,
        )

        generator = TestDataGenerator()
        domain = generator.generate_contradiction_test_domain(rule_count)

        if verbose:
            print(f"🔍 矛盾检测测试: {rule_count} 条规则")

        benchmark = PerformanceBenchmark()
        result = benchmark.run_benchmark(custom_config=config)

        # 注入自定义域数据
        generator._inject_custom_domain(result, domain)

        return result


class MultiRoundBenchmark:
    """多轮迭代性能测试"""

    def run(self, rounds: int = 5, verbose: bool = False) -> dict[int, BenchmarkResult]:
        """测试不同轮次的性能退化"""
        results = {}

        config = BenchmarkConfig(
            name="multi_round",
            rule_count=500,
            rounds=1,  # 基础配置，后面动态调整
        )

        for round_num in [1, 3, 5]:
            current_config = BenchmarkConfig(
                name=config.name,
                rule_count=config.rule_count,
                rounds=round_num,
                target_execution_time=config.target_execution_time * round_num,
            )

            if verbose:
                print(f"🔄 多轮测试: {round_num} 轮")

            benchmark = PerformanceBenchmark()
            result = benchmark.run_benchmark(custom_config=current_config)
            results[round_num] = result

        return results


class ComplexDependencyBenchmark:
    """复杂依赖链性能测试"""

    def run(self, complexity_level: str = "high", verbose: bool = False) -> BenchmarkResult:
        """
        测试复杂依赖关系的性能影响

        complexity_level: low/medium/high
        """
        complexity_config = {
            "low": {"entity_count": 50, "fact_count": 100, "dependency_depth": 2},
            "medium": {"entity_count": 100, "fact_count": 200, "dependency_depth": 5},
            "high": {"entity_count": 200, "fact_count": 400, "dependency_depth": 10},
        }

        config_data = complexity_config.get(complexity_level, complexity_config["medium"])

        config = BenchmarkConfig(
            name=f"complex_dependency_{complexity_level}",
            rule_count=200,
            entity_count=config_data["entity_count"],
            fact_count=config_data["fact_count"],
            target_execution_time=5.0,
            target_memory_mb=512.0,
        )

        generator = TestDataGenerator()
        domain = generator.generate_complex_dependency_domain(
            entity_count=config_data["entity_count"],
            fact_count=config_data["fact_count"],
            dependency_depth=config_data["dependency_depth"],
        )

        if verbose:
            print(f"🔗 复杂依赖测试: {complexity_level} 复杂度, 深度 {config_data['dependency_depth']}")

        benchmark = PerformanceBenchmark()
        result = benchmark.run_benchmark(custom_config=config)

        # 注入自定义域数据
        generator._inject_custom_domain(result, domain)

        return result
