"""
SSOT Kernel — Performance Regression Detection
==============================================
性能回归检测模块

功能：
1. 自动检测性能退化
2. 建立和管理性能基线
3. 生成回归报告和建议
4. 支持多维度对比分析
"""

import json
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from .benchmark import BenchmarkConfig, BenchmarkResult, PerformanceMetrics


class SeverityLevel(Enum):
    """严重程度级别"""

    CRITICAL = "CRITICAL"  # 严重回归，必须立即处理
    HIGH = "HIGH"  # 高度回归，需要尽快处理
    MEDIUM = "MEDIUM"  # 中度回归，需要关注
    LOW = "LOW"  # 轻度回归，可以观察
    NONE = "NONE"  # 无回归


@dataclass
class RegressionMetric:
    """回归指标"""

    metric_name: str
    baseline_value: float
    current_value: float
    change_percent: float
    change_absolute: float
    is_regression: bool
    severity: SeverityLevel

    @property
    def formatted_change(self) -> str:
        """格式化变化"""
        icon = "🔴" if self.change_percent > 0 else "🟢"
        return f"{icon} {abs(self.change_percent):.1f}% ({self.change_absolute:+.2f})"

    @property
    def trend_icon(self) -> str:
        """趋势图标"""
        if self.is_regression:
            if self.severity == SeverityLevel.CRITICAL:
                return "🚨"
            elif self.severity == SeverityLevel.HIGH:
                return "🔴"
            elif self.severity == SeverityLevel.MEDIUM:
                return "🟡"
            else:
                return "🔵"
        return "✅"


@dataclass
class RegressionReport:
    """回归检测报告"""

    timestamp: str
    benchmark_name: str
    has_regression: bool
    severity: SeverityLevel
    regression_metrics: list[RegressionMetric] = field(default_factory=list)
    analysis_summary: str = ""
    recommendations: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def critical_count(self) -> int:
        """严重回归数量"""
        return len(
            [m for m in self.regression_metrics if m.severity == SeverityLevel.CRITICAL]
        )

    @property
    def high_count(self) -> int:
        """高度回归数量"""
        return len(
            [m for m in self.regression_metrics if m.severity == SeverityLevel.HIGH]
        )

    @property
    def total_regression_count(self) -> int:
        """总回归数量"""
        return len([m for m in self.regression_metrics if m.is_regression])

    def print_summary(self):
        """打印回归摘要"""
        print(f"\n{'=' * 60}")
        print(f"🔍 性能回归检测报告: {self.benchmark_name}")
        print(f"{'=' * 60}")
        print(f"📅 检测时间: {self.timestamp}")
        print(f"🎯 整体状态: {self.severity.value}")

        if self.has_regression:
            print("🚨 检测到性能回归!")
            print(f"   🔴 严重: {self.critical_count}")
            print(f"   🔴 高度: {self.high_count}")
            print(
                f"   🟡 中度: {self.total_regression_count - self.critical_count - self.high_count}"
            )

            print("\n📊 回归详情:")
            for metric in self.regression_metrics:
                if metric.is_regression:
                    print(
                        f"   {metric.trend_icon} {metric.metric_name}: {metric.formatted_change}"
                    )
        else:
            print("✅ 未检测到性能回归")

        if self.recommendations:
            print("\n💡 优化建议:")
            for i, rec in enumerate(self.recommendations, 1):
                print(f"   {i}. {rec}")

        print(f"{'=' * 60}\n")


@dataclass
class PerformanceBaseline:
    """性能基线"""

    name: str
    version: str
    created_at: str
    benchmark_results: dict[str, BenchmarkResult] = field(default_factory=dict)
    system_info: dict[str, str] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def get_baseline_result(self, benchmark_name: str) -> BenchmarkResult | None:
        """获取指定基准测试的基线结果"""
        return self.benchmark_results.get(benchmark_name)

    def add_result(self, result: BenchmarkResult):
        """添加基准测试结果"""
        self.benchmark_results[result.config.name] = result

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "name": self.name,
            "version": self.version,
            "created_at": self.created_at,
            "system_info": self.system_info,
            "metadata": self.metadata,
            "benchmark_results": {
                name: {
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
                }
                for name, result in self.benchmark_results.items()
            },
        }

    @classmethod
    def from_dict(cls, data: dict) -> "PerformanceBaseline":
        """从字典创建"""
        baseline = cls(
            name=data["name"],
            version=data["version"],
            created_at=data["created_at"],
            system_info=data.get("system_info", {}),
            metadata=data.get("metadata", {}),
        )

        # 重建基准测试结果（简化版本）
        for name, result_data in data.get("benchmark_results", {}).items():
            config = BenchmarkConfig(
                name=result_data["config"]["name"],
                rule_count=result_data["config"]["rule_count"],
                target_execution_time=result_data["config"]["target_execution_time"],
                target_memory_mb=result_data["config"]["target_memory_mb"],
            )

            metrics = PerformanceMetrics(
                total_execution_time_ms=result_data["metrics"][
                    "total_execution_time_ms"
                ],
                peak_memory_usage_mb=result_data["metrics"]["peak_memory_usage_mb"],
                rules_per_second=result_data["metrics"]["rules_per_second"],
                passed_rules=result_data["metrics"]["passed_rules"],
                failed_rules=result_data["metrics"]["failed_rules"],
                blocked_rules=result_data["metrics"]["blocked_rules"],
                total_rules=result_data["config"]["rule_count"],
            )

            result = BenchmarkResult(config=config, metrics=metrics, success=True)

            baseline.benchmark_results[name] = result

        return baseline


class PerformanceRegressionDetector:
    """
    性能回归检测器

    功能：
    1. 自动检测性能退化
    2. 支持多维度指标检测
    3. 智能严重程度评估
    4. 生成优化建议
    """

    def __init__(self, baseline_file: str = "performance_baseline.json"):
        self.baseline_file = baseline_file
        self.thresholds = {
            "execution_time": {
                "warning": 1.10,  # 10%增长为警告
                "high": 1.20,  # 20%增长为高度回归
                "critical": 1.50,  # 50%增长为严重回归
            },
            "memory_usage": {
                "warning": 1.08,  # 8%增长为警告
                "high": 1.15,  # 15%增长为高度回归
                "critical": 1.30,  # 30%增长为严重回归
            },
            "throughput": {
                "warning": 0.95,  # 5%下降为警告
                "high": 0.90,  # 10%下降为高度回归
                "critical": 0.80,  # 20%下降为严重回归
            },
            "performance_score": {
                "warning": -5,  # 5分下降为警告
                "high": -10,  # 10分下降为高度回归
                "critical": -20,  # 20分下降为严重回归
            },
        }

    def load_baseline(self) -> PerformanceBaseline | None:
        """加载性能基线"""
        try:
            with open(self.baseline_file, encoding="utf-8") as f:
                data = json.load(f)
            return PerformanceBaseline.from_dict(data)
        except FileNotFoundError:
            return None
        except Exception as e:
            print(f"⚠️  加载基线失败: {e}")
            return None

    def save_baseline(self, baseline: PerformanceBaseline):
        """保存性能基线"""
        with open(self.baseline_file, "w", encoding="utf-8") as f:
            json.dump(baseline.to_dict(), f, ensure_ascii=False, indent=2)
        print(f"📄 性能基线已保存到: {self.baseline_file}")

    def create_baseline(
        self,
        results: dict[str, BenchmarkResult],
        name: str = "default_baseline",
        version: str = "1.0",
    ) -> PerformanceBaseline:
        """创建新的性能基线"""
        import platform

        baseline = PerformanceBaseline(
            name=name,
            version=version,
            created_at=datetime.now().isoformat(),
            system_info={
                "platform": platform.platform(),
                "python_version": platform.python_version(),
                "processor": platform.processor(),
            },
        )

        for name, result in results.items():
            baseline.add_result(result)

        self.save_baseline(baseline)
        return baseline

    def detect_regression(
        self,
        current_result: BenchmarkResult,
        baseline: PerformanceBaseline | None = None,
    ) -> RegressionReport:
        """检测性能回归"""
        if baseline is None:
            baseline = self.load_baseline()

        if baseline is None:
            return RegressionReport(
                timestamp=datetime.now().isoformat(),
                benchmark_name=current_result.config.name,
                has_regression=False,
                severity=SeverityLevel.NONE,
                analysis_summary="无可用基线，无法检测回归",
            )

        baseline_result = baseline.get_baseline_result(current_result.config.name)
        if baseline_result is None:
            return RegressionReport(
                timestamp=datetime.now().isoformat(),
                benchmark_name=current_result.config.name,
                has_regression=False,
                severity=SeverityLevel.NONE,
                analysis_summary=f"基线中无 {current_result.config.name} 的基准数据",
            )

        # 检测各项指标
        regression_metrics = []

        # 执行时间检测
        time_metric = self._detect_metric_regression(
            "执行时间",
            baseline_result.metrics.total_execution_time_ms,
            current_result.metrics.total_execution_time_ms,
            self.thresholds["execution_time"],
            higher_is_worse=True,
        )
        regression_metrics.append(time_metric)

        # 内存使用检测
        memory_metric = self._detect_metric_regression(
            "内存使用",
            baseline_result.metrics.peak_memory_usage_mb,
            current_result.metrics.peak_memory_usage_mb,
            self.thresholds["memory_usage"],
            higher_is_worse=True,
        )
        regression_metrics.append(memory_metric)

        # 吞吐量检测
        throughput_metric = self._detect_metric_regression(
            "规则吞吐量",
            baseline_result.metrics.rules_per_second,
            current_result.metrics.rules_per_second,
            self.thresholds["throughput"],
            higher_is_worse=False,
        )
        regression_metrics.append(throughput_metric)

        # 性能得分检测
        score_metric = self._detect_metric_regression(
            "性能得分",
            baseline_result.metrics.performance_score,
            current_result.metrics.performance_score,
            self.thresholds["performance_score"],
            higher_is_worse=False,
        )
        regression_metrics.append(score_metric)

        # 确定整体严重程度
        severity = self._assess_overall_severity(regression_metrics)
        has_regression = any(m.is_regression for m in regression_metrics)

        # 生成分析摘要和建议
        analysis_summary = self._generate_analysis_summary(regression_metrics)
        recommendations = self._generate_recommendations(regression_metrics)

        return RegressionReport(
            timestamp=datetime.now().isoformat(),
            benchmark_name=current_result.config.name,
            has_regression=has_regression,
            severity=severity,
            regression_metrics=regression_metrics,
            analysis_summary=analysis_summary,
            recommendations=recommendations,
            metadata={
                "baseline_version": baseline.version,
                "current_version": current_result.config.name,
            },
        )

    def _detect_metric_regression(
        self,
        metric_name: str,
        baseline_value: float,
        current_value: float,
        thresholds: dict[str, float],
        higher_is_worse: bool,
    ) -> RegressionMetric:
        """检测单个指标的回归"""
        change_percent = (
            (current_value - baseline_value) / (baseline_value + 0.001)
        ) * 100
        change_absolute = current_value - baseline_value

        # 判断是否回归
        if higher_is_worse:
            is_regression = change_percent > 0
        else:
            is_regression = change_percent < 0

        # 确定严重程度
        severity = SeverityLevel.NONE
        if is_regression:
            if higher_is_worse:
                if change_percent > thresholds.get("critical", 50):
                    severity = SeverityLevel.CRITICAL
                elif change_percent > thresholds.get("high", 20):
                    severity = SeverityLevel.HIGH
                elif change_percent > thresholds.get("warning", 10):
                    severity = SeverityLevel.MEDIUM
                else:
                    severity = SeverityLevel.LOW
            else:
                if change_percent < -thresholds.get("critical", 20):
                    severity = SeverityLevel.CRITICAL
                elif change_percent < -thresholds.get("high", 10):
                    severity = SeverityLevel.HIGH
                elif change_percent < -thresholds.get("warning", 5):
                    severity = SeverityLevel.MEDIUM
                else:
                    severity = SeverityLevel.LOW

        return RegressionMetric(
            metric_name=metric_name,
            baseline_value=baseline_value,
            current_value=current_value,
            change_percent=change_percent,
            change_absolute=change_absolute,
            is_regression=is_regression,
            severity=severity,
        )

    def _assess_overall_severity(
        self, metrics: list[RegressionMetric]
    ) -> SeverityLevel:
        """评估整体严重程度"""
        if not any(m.is_regression for m in metrics):
            return SeverityLevel.NONE

        if any(m.severity == SeverityLevel.CRITICAL for m in metrics):
            return SeverityLevel.CRITICAL

        if any(m.severity == SeverityLevel.HIGH for m in metrics):
            return SeverityLevel.HIGH

        if any(m.severity == SeverityLevel.MEDIUM for m in metrics):
            return SeverityLevel.MEDIUM

        return SeverityLevel.LOW

    def _generate_analysis_summary(self, metrics: list[RegressionMetric]) -> str:
        """生成分析摘要"""
        regressed_metrics = [m for m in metrics if m.is_regression]

        if not regressed_metrics:
            return "所有性能指标表现良好，未检测到明显退化。"

        summary_parts = []

        if any(m.severity == SeverityLevel.CRITICAL for m in regressed_metrics):
            summary_parts.append("检测到严重性能退化，需要立即关注和处理。")
        elif any(m.severity == SeverityLevel.HIGH for m in regressed_metrics):
            summary_parts.append("检测到显著性能退化，建议尽快进行优化。")
        else:
            summary_parts.append("检测到轻微性能变化，建议持续关注。")

        # 具体指标变化
        metric_changes = []
        for metric in regressed_metrics:
            if metric.severity in [SeverityLevel.CRITICAL, SeverityLevel.HIGH]:
                metric_changes.append(f"{metric.metric_name}{metric.formatted_change}")

        if metric_changes:
            summary_parts.append(f"主要问题: {', '.join(metric_changes)}")

        return " ".join(summary_parts)

    def _generate_recommendations(self, metrics: list[RegressionMetric]) -> list[str]:
        """生成优化建议"""
        recommendations = []

        for metric in metrics:
            if not metric.is_regression:
                continue

            if metric.metric_name == "执行时间":
                if metric.severity in [SeverityLevel.CRITICAL, SeverityLevel.HIGH]:
                    recommendations.append(
                        "执行时间严重退化，建议：1) 分析热点代码路径；2) 考虑并行执行；3) 优化条件评估逻辑"
                    )
                else:
                    recommendations.append(
                        "执行时间有所增长，建议检查最近的代码变更是否有性能影响"
                    )

            elif metric.metric_name == "内存使用":
                if metric.severity in [SeverityLevel.CRITICAL, SeverityLevel.HIGH]:
                    recommendations.append(
                        "内存使用严重增长，建议：1) 检查内存泄漏；2) 优化数据结构；3) 实现数据分批处理"
                    )
                else:
                    recommendations.append(
                        "内存使用有所增长，建议检查缓存策略和大对象处理"
                    )

            elif metric.metric_name == "规则吞吐量":
                if metric.severity in [SeverityLevel.CRITICAL, SeverityLevel.HIGH]:
                    recommendations.append(
                        "规则吞吐量显著下降，建议：1) 分析规则执行效率；2) 优化规则依赖关系；3) 考虑规则缓存"
                    )
                else:
                    recommendations.append(
                        "规则吞吐量轻微下降，建议持续监控规则执行效率"
                    )

        # 通用建议
        if len(recommendations) > 1:
            recommendations.append(
                "建议进行全面的性能分析：1) 运行性能分析工具；2) 检查系统资源使用；3) 对比代码变更历史"
            )

        return recommendations[:5]  # 最多返回5条建议

    def batch_detect_regression(
        self,
        current_results: dict[str, BenchmarkResult],
        baseline: PerformanceBaseline | None = None,
    ) -> dict[str, RegressionReport]:
        """批量检测性能回归"""
        reports = {}

        for name, result in current_results.items():
            report = self.detect_regression(result, baseline)
            reports[name] = report

        return reports

    def generate_comparison_report(
        self,
        baseline_results: dict[str, BenchmarkResult],
        current_results: dict[str, BenchmarkResult],
    ) -> str:
        """生成对比报告"""
        report_lines = [
            "=" * 70,
            "📊 性能基线对比报告",
            "=" * 70,
            f"📅 对比时间: {datetime.now().isoformat()}",
            "",
        ]

        for size in baseline_results.keys():
            if size not in current_results:
                continue

            baseline = baseline_results[size]
            current = current_results[size]

            report_lines.extend(
                [
                    f"🎯 {size.upper()} 规模基准测试对比",
                    "-" * 70,
                ]
            )

            # 执行时间对比
            time_change = (
                (
                    current.metrics.total_execution_time_ms
                    - baseline.metrics.total_execution_time_ms
                )
                / baseline.metrics.total_execution_time_ms
                * 100
            )
            time_icon = (
                "🔴" if time_change > 10 else ("🟡" if time_change > 5 else "🟢")
            )
            report_lines.append(
                f"{time_icon} 执行时间: {baseline.metrics.total_execution_time_ms / 1000:.2f}s → {current.metrics.total_execution_time_ms / 1000:.2f}s ({time_change:+.1f}%)"
            )

            # 内存使用对比
            memory_change = (
                (
                    current.metrics.peak_memory_usage_mb
                    - baseline.metrics.peak_memory_usage_mb
                )
                / baseline.metrics.peak_memory_usage_mb
                * 100
            )
            memory_icon = (
                "🔴" if memory_change > 10 else ("🟡" if memory_change > 5 else "🟢")
            )
            report_lines.append(
                f"{memory_icon} 内存使用: {baseline.metrics.peak_memory_usage_mb:.1f}MB → {current.metrics.peak_memory_usage_mb:.1f}MB ({memory_change:+.1f}%)"
            )

            # 性能得分对比
            score_change = current.performance_score - baseline.performance_score
            score_icon = (
                "🔴" if score_change < -5 else ("🟡" if score_change < 0 else "🟢")
            )
            report_lines.append(
                f"{score_icon} 性能得分: {baseline.performance_score:.1f} → {current.performance_score:.1f} ({score_change:+.1f})"
            )

            report_lines.append("")

        report_lines.extend(["=" * 70, "✅ 对比报告完成"])

        return "\n".join(report_lines)
