"""
SSOT Kernel — Metrics Storage
================================
指标数据存储模块（简化版本）
"""

import json
import sqlite3
from datetime import datetime
from pathlib import Path

from .collectors import AggregatedMetric, MetricValue


class MetricsStorage:
    """指标存储基类"""

    def __init__(self, storage_path: str = ""):
        self.storage_path = storage_path

    def store_metrics(self, metrics: list[MetricValue]) -> bool:
        """存储指标"""
        raise NotImplementedError

    def query_metrics(self, metric_name: str, start_time: str, end_time: str) -> list[MetricValue]:
        """查询指标"""
        raise NotImplementedError

    def aggregate_metrics(self, metric_name: str, aggregation: str = "avg") -> AggregatedMetric | None:
        """聚合指标"""
        raise NotImplementedError

    def cleanup_old_data(self, days: int = 30) -> int:
        """清理旧数据"""
        raise NotImplementedError


class InMemoryStorage(MetricsStorage):
    """内存存储"""

    def __init__(self):
        super().__init__()
        self.metrics: dict[str, list[MetricValue]] = {}
        self.max_entries = 10000

    def store_metrics(self, metrics: list[MetricValue]) -> bool:
        """存储指标"""
        for metric in metrics:
            if metric.name not in self.metrics:
                self.metrics[metric.name] = []

            self.metrics[metric.name].append(metric)

            # 限制内存使用
            if len(self.metrics[metric.name]) > self.max_entries:
                self.metrics[metric.name] = self.metrics[metric.name][self.max_entries // 2 :]

        return True

    def query_metrics(self, metric_name: str, start_time: str, end_time: str) -> list[MetricValue]:
        """查询指标"""
        if metric_name not in self.metrics:
            return []

        start = datetime.fromisoformat(start_time)
        end = datetime.fromisoformat(end_time)

        return [m for m in self.metrics[metric_name] if start <= datetime.fromisoformat(m.timestamp) <= end]

    def aggregate_metrics(self, metric_name: str, aggregation: str = "avg") -> AggregatedMetric | None:
        """聚合指标"""
        if metric_name not in self.metrics or not self.metrics[metric_name]:
            return None

        values = [m.value for m in self.metrics[metric_name]]

        # 计算聚合值
        if aggregation == "avg":
            sum(values) / len(values)
        elif aggregation == "sum":
            sum(values)
        elif aggregation == "min":
            min(values)
        elif aggregation == "max":
            max(values)
        else:
            sum(values) / len(values)

        return AggregatedMetric(
            name=metric_name,
            count=len(values),
            min=min(values),
            max=max(values),
            avg=sum(values) / len(values),
            sum=sum(values),
            timestamps=[m.timestamp for m in self.metrics[metric_name]],
        )

    def cleanup_old_data(self, days: int = 30) -> int:
        """清理旧数据"""
        # 内存存储不需要主动清理
        return 0


class JSONStorage(MetricsStorage):
    """JSON文件存储"""

    def __init__(self, storage_path: str = "monitoring_data.json"):
        super().__init__(storage_path)
        self._ensure_storage_file()

    def _ensure_storage_file(self):
        """确保存储文件存在"""
        if not self.storage_path:
            self.storage_path = "monitoring_data.json"

        if not Path(self.storage_path).exists():
            self._write_data({})

    def _read_data(self) -> dict:
        """读取数据"""
        try:
            with open(self.storage_path, encoding="utf-8") as f:
                return json.load(f)
        except FileNotFoundError:
            return {}
        except Exception as e:
            print(f"⚠️  读取存储文件失败: {e}")
            return {}

    def _write_data(self, data: dict):
        """写入数据"""
        with open(self.storage_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def store_metrics(self, metrics: list[MetricValue]) -> bool:
        """存储指标"""
        data = self._read_data()

        for metric in metrics:
            if "metrics" not in data:
                data["metrics"] = {}

            if metric.name not in data["metrics"]:
                data["metrics"][metric.name] = []

            data["metrics"][metric.name].append(metric.to_dict())

            # 限制文件大小
            if len(data["metrics"][metric.name]) > 5000:
                data["metrics"][metric.name] = data["metrics"][metric.name][-2500:]

        self._write_data(data)
        return True

    def query_metrics(self, metric_name: str, start_time: str, end_time: str) -> list[MetricValue]:
        """查询指标"""
        data = self._read_data()

        if "metrics" not in data or metric_name not in data["metrics"]:
            return []

        start = datetime.fromisoformat(start_time)
        end = datetime.fromisoformat(end_time)

        metrics_data = data["metrics"][metric_name]

        result = []
        for metric_data in metrics_data:
            metric_time = datetime.fromisoformat(metric_data["timestamp"])
            if start <= metric_time <= end:
                result.append(MetricValue(**metric_data))

        return result

    def aggregate_metrics(self, metric_name: str, aggregation: str = "avg") -> AggregatedMetric | None:
        """聚合指标"""
        data = self._read_data()

        if "metrics" not in data or metric_name not in data["metrics"]:
            return None

        metrics_data = data["metrics"][metric_name]
        values = [m["value"] for m in metrics_data]

        # 计算聚合值
        if aggregation == "avg":
            sum(values) / len(values)
        elif aggregation == "sum":
            sum(values)
        elif aggregation == "min":
            min(values)
        elif aggregation == "max":
            max(values)
        else:
            sum(values) / len(values)

        return AggregatedMetric(
            name=metric_name,
            count=len(values),
            min=min(values),
            max=max(values),
            avg=sum(values) / len(values),
            sum=sum(values),
            timestamps=[m["timestamp"] for m in metrics_data],
        )

    def cleanup_old_data(self, days: int = 30) -> int:
        """清理旧数据"""
        data = self._read_data()

        if "metrics" not in data:
            return 0

        cutoff_time = datetime.now() - timedelta(days=days)
        cleaned_count = 0

        for metric_name, metrics in list(data["metrics"].items()):
            original_count = len(metrics)

            # 过滤旧数据
            cleaned_metrics = [m for m in metrics if datetime.fromisoformat(m["timestamp"]) >= cutoff_time]

            data["metrics"][metric_name] = cleaned_metrics
            cleaned_count += original_count - len(cleaned_metrics)

        self._write_data(data)
        return cleaned_count


# 导入必要的依赖
from datetime import timedelta


class SQLiteStorage(MetricsStorage):
    """SQLite存储"""

    def __init__(self, storage_path: str = "monitoring_data.db"):
        super().__init__(storage_path)
        self._init_database()

    def _init_database(self):
        """初始化数据库"""
        self.conn = sqlite3.connect(self.storage_path)
        cursor = self.conn.cursor()

        # 创建指标表
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS metrics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            value REAL,
            timestamp TEXT NOT NULL,
            tags TEXT,
            metadata TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)

        # 创建索引
        cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_metrics_name
        ON metrics(name)
        """)

        cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_metrics_timestamp
        ON metrics(timestamp)
        """)

        self.conn.commit()

    def store_metrics(self, metrics: list[MetricValue]) -> bool:
        """存储指标"""
        cursor = self.conn.cursor()

        for metric in metrics:
            cursor.execute(
                """
            INSERT INTO metrics (name, value, timestamp, tags, metadata)
            VALUES (?, ?, ?, ?, ?)
            """,
                (metric.name, metric.value, metric.timestamp, json.dumps(metric.tags), json.dumps(metric.metadata)),
            )

        self.conn.commit()
        return True

    def query_metrics(self, metric_name: str, start_time: str, end_time: str) -> list[MetricValue]:
        """查询指标"""
        cursor = self.conn.cursor()

        cursor.execute(
            """
        SELECT name, value, timestamp, tags, metadata
        FROM metrics
        WHERE name = ? AND timestamp >= ? AND timestamp <= ?
        ORDER BY timestamp
        """,
            (metric_name, start_time, end_time),
        )

        result = []
        for row in cursor.fetchall():
            result.append(
                MetricValue(
                    name=row[0], value=row[1], timestamp=row[2], tags=json.loads(row[3]), metadata=json.loads(row[4])
                )
            )

        return result

    def aggregate_metrics(self, metric_name: str, aggregation: str = "avg") -> AggregatedMetric | None:
        """聚合指标"""
        cursor = self.conn.cursor()

        # 确定聚合函数
        agg_func = "AVG" if aggregation == "avg" else aggregation.upper()

        cursor.execute(
            f"""
        SELECT {agg_func}(value) as agg_value, COUNT(*) as count,
               MIN(value) as min_val, MAX(value) as max_val
        FROM metrics
        WHERE name = ?
        """,
            (metric_name,),
        )

        result = cursor.fetchone()
        if not result:
            return None

        agg_value, count, min_val, max_val = result

        # 获取时间戳范围
        cursor.execute(
            """
        SELECT MIN(timestamp) as start_time, MAX(timestamp) as end_time
        FROM metrics
        WHERE name = ?
        """,
            (metric_name,),
        )

        time_range = cursor.fetchone()

        # 计算总和
        cursor.execute(
            """
        SELECT SUM(value) as total_sum
        FROM metrics
        WHERE name = ?
        """,
            (metric_name,),
        )

        total_sum = cursor.fetchone()[0] or 0

        return AggregatedMetric(
            name=metric_name,
            count=count,
            min=min_val,
            max=max_val,
            avg=agg_value,
            sum=total_sum,
            timestamps=[time_range[0], time_range[1]] if time_range else [],
        )

    def cleanup_old_data(self, days: int = 30) -> int:
        """清理旧数据"""
        cursor = self.conn.cursor()

        cutoff_time = (datetime.now() - timedelta(days=days)).isoformat()

        cursor.execute(
            """
        DELETE FROM metrics
        WHERE timestamp < ?
        """,
            (cutoff_time,),
        )

        deleted_count = cursor.rowcount
        self.conn.commit()

        return deleted_count

    def close(self):
        """关闭数据库连接"""
        self.conn.close()
