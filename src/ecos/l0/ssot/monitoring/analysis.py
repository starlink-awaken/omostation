"""
SSOT Kernel — Analysis Module
==============================
数据分析和趋势分析模块
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class TrendDirection(Enum):
    """趋势方向"""

    INCREASING = "increasing"
    DECREASING = "decreasing"
    STABLE = "stable"
    UNKNOWN = "unknown"


@dataclass
class TrendAnalysis:
    """趋势分析结果"""

    metric_name: str
    window: str
    trend_direction: TrendDirection
    trend_slope: float
    correlation: float
    significance: bool
    forecast: float | None = None
    anomalies: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "metric_name": self.metric_name,
            "window": self.window,
            "trend_direction": self.trend_direction.value,
            "trend_slope": self.trend_slope,
            "correlation": self.correlation,
            "significance": self.significance,
            "forecast": self.forecast,
            "anomalies": self.anomalies,
            "timestamp": datetime.now().isoformat(),
        }


class AnomalyDetector:
    """异常检测器"""

    def __init__(self):
        self.thresholds = {
            "std_dev": 2.0,  # 标准差倍数
            "iqr": 1.5,  # IQR倍数
            "percentile": 95,  # 百分位数
        }

    def detect_anomalies(self, values: list[float], timestamps: list[str]) -> list[dict[str, Any]]:
        """检测异常值"""
        if len(values) < 10:
            return []

        anomalies = []

        # 方法1: 标准差方法
        anomalies.extend(self._detect_std_dev_anomalies(values, timestamps))

        # 方法2: IQR方法
        anomalies.extend(self._detect_iqr_anomalies(values, timestamps))

        # 去重
        unique_anomalies = []
        seen_indices = set()

        for anomaly in anomalies:
            if anomaly["index"] not in seen_indices:
                unique_anomalies.append(anomaly)
                seen_indices.add(anomaly["index"])

        return unique_anomalies

    def _detect_std_dev_anomalies(self, values: list[float], timestamps: list[str]) -> list[dict[str, Any]]:
        """使用标准差方法检测异常"""
        import statistics

        anomalies = []

        try:
            mean_val = statistics.mean(values)
            std_dev = statistics.stdev(values)

            if std_dev == 0:
                return []

            threshold = self.thresholds["std_dev"]

            for i, value in enumerate(values):
                z_score = abs((value - mean_val) / std_dev)

                if z_score > threshold:
                    anomalies.append(
                        {
                            "index": i,
                            "value": value,
                            "timestamp": timestamps[i] if i < len(timestamps) else None,
                            "method": "std_dev",
                            "z_score": z_score,
                            "severity": "high" if z_score > 3 else "medium",
                        }
                    )

        except Exception:
            pass

        return anomalies

    def _detect_iqr_anomalies(self, values: list[float], timestamps: list[str]) -> list[dict[str, Any]]:
        """使用IQR方法检测异常"""

        anomalies = []

        try:
            sorted_values = sorted(values)
            n = len(sorted_values)

            if n < 4:
                return []

            q1_index = int(n * 0.25)
            q3_index = int(n * 0.75)

            q1 = sorted_values[q1_index]
            q3 = sorted_values[q3_index]

            iqr = q3 - q1
            lower_bound = q1 - self.thresholds["iqr"] * iqr
            upper_bound = q3 + self.thresholds["iqr"] * iqr

            for i, value in enumerate(values):
                if value < lower_bound or value > upper_bound:
                    severity = "high" if (value < q1 - 2 * iqr or value > q3 + 2 * iqr) else "medium"

                    anomalies.append(
                        {
                            "index": i,
                            "value": value,
                            "timestamp": timestamps[i] if i < len(timestamps) else None,
                            "method": "iqr",
                            "bounds": {"lower": lower_bound, "upper": upper_bound},
                            "severity": severity,
                        }
                    )

        except Exception:
            pass

        return anomalies


class PerformanceTrendAnalyzer:
    """性能趋势分析器"""

    def __init__(self):
        self.anomaly_detector = AnomalyDetector()
        self.trend_cache: dict[str, TrendAnalysis] = {}

    def analyze_trend(
        self, metric_name: str, values: list[float], timestamps: list[str], window_minutes: int = 60
    ) -> TrendAnalysis:
        """分析性能趋势"""
        if len(values) < 3:
            return self._create_empty_analysis(metric_name, window_minutes)

        # 检测异常
        anomalies = self.anomaly_detector.detect_anomalies(values, timestamps)

        # 计算趋势
        trend_direction, slope, correlation = self._calculate_trend(values)

        # 预测下一个值
        forecast = self._forecast_next_value(values, slope)

        # 统计显著性
        significance = self._check_significance(correlation, len(values))

        return TrendAnalysis(
            metric_name=metric_name,
            window=f"{window_minutes}min",
            trend_direction=trend_direction,
            trend_slope=slope,
            correlation=correlation,
            significance=significance,
            forecast=forecast,
            anomalies=anomalies,
        )

    def _create_empty_analysis(self, metric_name: str, window_minutes: int) -> TrendAnalysis:
        """创建空分析"""
        return TrendAnalysis(
            metric_name=metric_name,
            window=f"{window_minutes}min",
            trend_direction=TrendDirection.UNKNOWN,
            trend_slope=0.0,
            correlation=0.0,
            significance=False,
            anomalies=[],
        )

    def _calculate_trend(self, values: list[float]) -> tuple:
        """计算趋势"""
        import statistics

        x = list(range(len(values)))
        y = values

        # 简单线性回归
        try:
            n = len(values)
            sum_x = sum(x)
            sum_y = sum(y)
            sum_xy = sum(xi * yi for xi, yi in zip(x, y))
            sum_x2 = sum(xi**2 for xi in x)

            # 计算斜率
            denominator = n * sum_x2 - sum_x**2
            if denominator == 0:
                return TrendDirection.STABLE, 0.0, 0.0

            slope = (n * sum_xy - sum_x * sum_y) / denominator

            # 计算相关系数
            mean_x = statistics.mean(x)
            mean_y = statistics.mean(y)

            numerator = sum((xi - mean_x) * (yi - mean_y) for xi, yi in zip(x, y))
            denominator_x = sum((xi - mean_x) ** 2 for xi in x)
            denominator_y = sum((yi - mean_y) ** 2 for yi in y)

            if denominator_x == 0 or denominator_y == 0:
                correlation = 0.0
            else:
                correlation = numerator / ((denominator_x * denominator_y) ** 0.5)

            # 确定趋势方向
            if abs(slope) < 0.001:
                trend_direction = TrendDirection.STABLE
            elif slope > 0:
                trend_direction = TrendDirection.INCREASING
            else:
                trend_direction = TrendDirection.DECREASING

            return trend_direction, slope, correlation

        except Exception:
            return TrendDirection.UNKNOWN, 0.0, 0.0

    def _forecast_next_value(self, values: list[float], slope: float) -> float | None:
        """预测下一个值"""
        if len(values) < 2:
            return None

        # 简单线性预测
        last_value = values[-1]
        forecast = last_value + slope

        return forecast

    def _check_significance(self, correlation: float, sample_size: int) -> bool:
        """检查统计显著性"""
        if sample_size < 3:
            return False

        # 简单的显著性阈值
        threshold = 0.5 if sample_size < 10 else 0.3

        return abs(correlation) > threshold

    def get_multi_metric_analysis(
        self, metrics_data: dict[str, list[float]], timestamps_data: dict[str, list[str]], window_minutes: int = 60
    ) -> dict[str, TrendAnalysis]:
        """多指标分析"""
        results = {}

        for metric_name, values in metrics_data.items():
            timestamps = timestamps_data.get(metric_name, [])

            analysis = self.analyze_trend(metric_name, values, timestamps, window_minutes)
            results[metric_name] = analysis

            # 缓存结果
            self.trend_cache[metric_name] = analysis

        return results

    def generate_trend_report(self) -> str:
        """生成趋势分析报告"""
        report = []

        report.append("=" * 70)
        report.append("📈 SSOT 性能趋势分析报告")
        report.append("=" * 70)

        if not self.trend_cache:
            report.append("\n暂无趋势分析数据")
        else:
            report.append(f"\n分析指标数量: {len(self.trend_cache)}")

            for metric_name, analysis in self.trend_cache.items():
                direction_icon = {
                    TrendDirection.INCREASING: "📈",
                    TrendDirection.DECREASING: "📉",
                    TrendDirection.STABLE: "➡️",
                    TrendDirection.UNKNOWN: "❓",
                }.get(analysis.trend_direction, "❓")

                significance_icon = "✅" if analysis.significance else "⚪"

                report.append(f"\n{direction_icon} {metric_name}:")
                report.append(f"  方向: {analysis.trend_direction.value}")
                report.append(f"  斜率: {analysis.trend_slope:.6f}")
                report.append(f"  相关性: {analysis.correlation:.3f} {significance_icon}")

                if analysis.forecast is not None:
                    report.append(f"  预测: {analysis.forecast:.2f}")

                if analysis.anomalies:
                    report.append(f"  异常数: {len(analysis.anomalies)}")

        report.append("=" * 70)

        return "\n".join(report)
