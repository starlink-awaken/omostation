"""
SSOT Kernel — Recovery History Manager
================================
历史记录管理系统

功能：
1. 记录所有恢复操作
2. 支持模式匹配和学习
3. 历史查询和统计分析
4. 学习最优恢复策略
"""

import json
import threading
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass
class RecoveryRecord:
    """恢复记录"""

    id: str
    timestamp: str
    error_type: str
    error_message: str
    error_info: dict[str, Any]
    pattern_id: str
    strategy: str
    action_id: str
    status: str  # analyzing, applying, completed, failed
    success: bool
    recovery_time_ms: float
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "id": self.id,
            "timestamp": self.timestamp,
            "error_type": self.error_type,
            "error_message": self.error_message,
            "error_info": self.error_info,
            "pattern_id": self.pattern_id,
            "strategy": self.strategy,
            "action_id": self.action_id,
            "status": self.status,
            "success": self.success,
            "recovery_time_ms": self.recovery_time_ms,
            "metadata": self.metadata,
        }


class RecoveryHistoryManager:
    """恢复历史管理器"""

    def __init__(self, storage_path: str = "recovery_history.json"):
        self.storage_path = Path(storage_path)
        self.records: list[RecoveryRecord] = []
        self.patterns: dict[str, Any] = {}
        self.lock = threading.Lock()
        self.max_records = 10000  # 最大记录数

        self._load_from_disk()

    def _load_from_disk(self):
        """从磁盘加载历史"""
        if not self.storage_path.exists():
            return

        try:
            with open(self.storage_path, encoding="utf-8") as f:
                data = json.load(f)
                records = [RecoveryRecord(**item) for item in data.get("records", [])]
                self.records = records[-self.max_records :]

        except Exception as e:
            print(f"⚠️  加载历史记录失败: {e}")
            self.records = []

    def save_to_disk(self):
        """保存历史到磁盘"""
        try:
            data = {
                "version": "1.0",
                "updated_at": datetime.now().isoformat(),
                "total_records": len(self.records),
                "records": [r.to_dict() for r in self.records],
            }

            # 写入临时文件
            temp_path = self.storage_path + ".tmp"
            with open(temp_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

            # 原子文件
            if Path(temp_path).exists():
                import shutil

                shutil.move(temp_path, self.storage_path)

            print(f"📄 历史记录已保存 ({len(self.records)} 条)")

        except Exception as e:
            print(f"⚠️️ 保存历史记录失败: {e}")

    def add_record(self, record: RecoveryRecord):
        """添加恢复记录"""
        with self.lock:
            self.records.append(record)

            # 超过最大记录数
            if len(self.records) > self.max_records:
                self.records = self.records[-self.max_records :]

            # 保存到磁盘
            self.save_to_disk()

    def get_history_summary(self) -> dict[str, Any]:
        """获取历史摘要"""
        total_records = len(self.records)
        successful_records = len([r for r in self.records if r.success])
        failed_records = len([r for r in self.records if not r.success])

        # 模式统计
        pattern_counts = {}
        for pattern_name in self.patterns:
            self.patterns[pattern_name]
            count = len([r for r in self.records if r.pattern_id == pattern_name])
            pattern_counts[pattern_name] = {
                "total": count,
                "successful": len([r for r in self.records if r.pattern_id == pattern_name and r.success]),
                "failed": len([r for r in self.records if r.pattern_id == pattern_name and not r.success]),
            }

        return {
            "total_records": total_records,
            "successful_records": successful_records,
            "failed_records": failed_records,
            "pattern_counts": pattern_counts,
            "record_types": self._get_record_type_counts(),
            "average_recovery_time_ms": self._get_avg_recovery_time(),
            "updated_at": datetime.now().isoformat(),
        }

    def _get_record_type_counts(self) -> dict[str, int]:
        """记录类型统计"""
        type_counts: dict[str, int] = {}
        for record in self.records:
            type_counts[record.error_type] = type_counts.get(record.error_type, 0) + 1
        return type_counts

    def _get_avg_recovery_time(self) -> float:
        """获取平均恢复时间"""
        successful_records = [r for r in self.records if r.success and r.recovery_time_ms > 0]
        if not successful_records:
            return 0.0

        return sum(r.recovery_time_ms for r in successful_records) / len(successful_records)

    def find_similar_errors(self, current_error_info: dict[str, Any]) -> list[RecoveryRecord]:
        """查找相似的历史记录"""
        current_error_type = current_error_info.get("type", "")
        current_error_msg = current_error_info.get("message", "").lower()

        similar_records = []

        for record in self.records:
            if record.error_type == current_error_type:
                # 检查消息相似性（简单关键词匹配）
                if any(keyword in current_error_msg for keyword in record.error_message.lower()):
                    similar_records.append(record)

        # 按时间排序，最近的优先
        similar_records.sort(key=lambda r: r.timestamp, reverse=True)

        return similar_records[:5]  # 最多返回5个

    def get_learning_metrics(self) -> dict[str, Any]:
        """获取学习指标"""
        return {
            "total_patterns": len(self.patterns),
            "total_records": len(self.records),
            "learning_rate": self._calculate_learning_rate(),
            "best_performing_patterns": self._get_best_performing_patterns(),
            "worst_performing_patterns": self._get_worst_performing_patterns(),
            "most_recent_errors": self._get_most_recent_errors(5),
        }

    def _calculate_learning_rate(self) -> float:
        """计算学习率"""
        total_records = len(self.records)
        if total_records == 0:
            return 0.0

        learning_opportunities = 0

        for pattern_name, pattern in self.patterns.items():
            success_count = len([r for r in self.records if r.pattern_id == pattern_name and r.success])
            total_count = len([r for r in self.records if r.pattern_id == pattern_name])

            if total_count > 5:  # 至少5次才评估
                if success_count / total_count > 0.6:  # 成功率>60%
                    learning_opportunities += 1

        if learning_opportunities == 0:
            return 0.0

        return learning_opportunities / learning_opportunities

    def _get_best_performing_patterns(self) -> list[tuple[str, float]]:
        """获取最佳表现的恢复模式"""
        pattern_scores = []

        for pattern_name, pattern in self.patterns.items():
            records = [r for r in self.records if r.pattern_id == pattern_name]
            if len(records) > 0:
                # 计算平均成功率
                success_count = len([r for r in records if r.success])
                avg_success_rate = success_count / len(records)

                pattern_scores.append((pattern_name, avg_success_rate))

        # 按成功率排序
        pattern_scores.sort(key=lambda x: x[1], reverse=True)
        return pattern_scores[:5]  # 返回前5个

    def _get_worst_performing_patterns(self) -> list[tuple[str, float]]:
        """获取表现最差的恢复模式"""
        pattern_scores = []

        for pattern_name, pattern in self.patterns.items():
            records = [r for r in self.records if r.pattern_id == pattern_name]
            if len(records) > 0:
                # 计算平均成功率
                success_count = len([r for r in records if r.success])
                avg_success_rate = success_count / len(records)

                pattern_scores.append((pattern_name, avg_success_rate))

        # 按成功率排序（最差的在前）
        pattern_scores.sort(key=lambda x: x[1])
        return pattern_scores[:5]  # 返回前5个

    def _get_most_recent_errors(self, limit: int = 5) -> list[dict[str, Any]]:
        """获取最近的错误"""
        recent_errors: list[dict[str, Any]] = []

        for record in reversed(self.records):
            if len(recent_errors) >= limit:
                break

            recent_errors.append(
                {
                    "timestamp": record.timestamp,
                    "error_type": record.error_type,
                    "error_message": record.error_message,
                    "pattern_id": record.pattern_id,
                    "action_id": record.action_id,
                    "success": record.success,
                }
            )

        return recent_errors
