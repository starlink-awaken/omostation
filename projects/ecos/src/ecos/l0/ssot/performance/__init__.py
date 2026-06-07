"""
SSOT Kernel — Performance Module
==================================
性能基准测试和监控模块

功能：
1. 性能基准测试（多规模、多场景）
2. 性能回归检测
3. 资源使用监控
4. 性能指标收集和分析
"""

from .benchmark import BenchmarkConfig, BenchmarkResult, PerformanceBenchmark, PerformanceMetrics
from .generators import DomainDataFactory, TestDataGenerator
from .monitor import MetricsCollector, PerformanceMonitor, ResourceMonitor
from .regression import PerformanceBaseline, PerformanceRegressionDetector, RegressionReport

__all__ = [
    # Benchmark
    "PerformanceBenchmark",
    "BenchmarkResult",
    "PerformanceMetrics",
    "BenchmarkConfig",
    # Generators
    "TestDataGenerator",
    "DomainDataFactory",
    # Regression
    "PerformanceRegressionDetector",
    "RegressionReport",
    "PerformanceBaseline",
    # Monitor
    "PerformanceMonitor",
    "ResourceMonitor",
    "MetricsCollector",
]
