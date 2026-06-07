"""
SSOT Kernel — Intelligent Recovery System
=======================================
智能错误恢复系统

功能：
1. 智能错误检测和分类
2. 多种恢复策略
3. 恢复历史学习
4. 自动决策和执行恢复
"""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any

from .history import RecoveryHistoryManager
from .patterns import get_strategy_by_name


class RecoverySeverity(Enum):
    """恢复严重程度"""

    INFO = "INFO"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"
    FATAL = "FATAL"


@dataclass
class RecoveryContext:
    """恢复上下文"""

    error: Exception | None = None
    domain_config: Any = None
    report: Any = None
    execution_time_ms: float = 0.0
    available_strategies: list[str] = None  # type: ignore[assignment]
    current_strategy: str | None = None
    history_matches: list[dict] = None  # type: ignore[assignment]
    performance_metrics: dict[str, Any] = None  # type: ignore[assignment]
    metadata: dict[str, Any] = None  # type: ignore[assignment]
    timestamp: str = ""

    def __post_init__(self):
        self.timestamp = datetime.now().isoformat()
        if self.available_strategies is None:
            self.available_strategies = ["auto", "semi_auto", "manual"]
        if self.history_matches is None:
            self.history_matches = []
        if self.performance_metrics is None:
            self.performance_metrics = {}
        if self.metadata is None:
            self.metadata = {}

        if self.domain_config:
            entities = getattr(self.domain_config, 'entities', [])
            facts = getattr(self.domain_config, 'facts', [])
            rules = getattr(self.domain_config, 'rules', [])
            self.performance_metrics["entity_count"] = len(entities)
            self.performance_metrics["fact_count"] = len(facts)
            self.performance_metrics["rule_count"] = len(rules)

    @property
    def severity(self) -> RecoverySeverity:
        """评估错误严重程度"""
        if not self.error:
            return RecoverySeverity.INFO

        # 检查错误类型
        critical_types = ("SystemError", "OSError", "RuntimeError", "MemoryError", "KeyboardInterrupt")

        if any(t in self.error.__class__.__name__ for t in critical_types):
            return RecoverySeverity.CRITICAL

        # 检查错误消息
        error_msg = str(self.error).lower()

        critical_keywords = ["segmentation fault", "core dump", "deadlock", "system crashed", "kernel panic"]

        if any(keyword in error_msg for keyword in critical_keywords):
            return RecoverySeverity.CRITICAL

        if self.execution_time_ms > 10000:
            return RecoverySeverity.HIGH

        if self.execution_time_ms > 30000:
            return RecoverySeverity.MEDIUM

        if self.report:
            blocker = getattr(self.report, 'blocker', 0)
            error_count = getattr(self.report, 'error', 0)
            if blocker > 0:
                return RecoverySeverity.HIGH
            if error_count > 0:
                return RecoverySeverity.MEDIUM

        return RecoverySeverity.LOW

    def get_available_strategies(self) -> list[str]:
        """获取可用的恢复策略"""
        return self.available_strategies

    def set_current_strategy(self, strategy_name: str) -> bool:
        """设置当前策略"""
        if strategy_name in self.available_strategies:
            self.current_strategy = strategy_name
            return True
        return False

    def get_context_summary(self) -> dict[str, Any]:
        """获取上下文摘要"""
        return {
            "timestamp": self.timestamp,
            "severity": self.severity.value if hasattr(self, "severity") else "UNKNOWN",
            "error_type": self.error.__class__.__name__ if self.error else "None",
            "strategy": self.current_strategy,
            "execution_time_ms": self.execution_time_ms,
            "available_strategies": len(self.available_strategies),
            "history_matches": len(self.history_matches),
            "performance_metrics": self.performance_metrics,
            "metadata": self.metadata,
        }

    @property
    def error_info(self) -> dict[str, Any]:
        """获取错误信息字典"""
        if self.error:
            return {
                "type": self.error.__class__.__name__,
                "message": str(self.error),
            }
        return {"type": "None", "message": ""}


class IntelligentRecoverySystem:
    """
    智能错误恢复系统

    功能：
    1. 智能错误检测和分类
    2. 多种恢复策略（自动/半自动/人工）
    3. 恢复历史学习
    4. 自动决策和恢复执行
    """

    def __init__(self, storage_path: str = "recovery_history.json"):
        self.storage_path = storage_path
        self.history_manager = RecoveryHistoryManager(storage_path)

        self.patterns = []

        # 系统状态
        self.status = "active"
        self.total_recoveries = 0
        self.successful_recoveries = 0
        self.failed_recoveries = 0

        # 性能统计
        self.performance_stats: dict[str, Any] = {
            "avg_recovery_time_ms": 0.0,
            "max_recovery_time_ms": 0.0,
            "total_patterns": len(self.patterns),
            "learning_rate": 0.0,
        }

        print("🛡️  智能错误恢复系统初始化完成")
        print(f"   模式数量: {len(self.patterns)}")
        print(f"   存储路径: {self.storage_path}")

    def handle_error(
        self,
        error: Exception,
        domain_config: Any = None,
        report: Any = None,
        execution_time_ms: float = 0.0,
    ) -> bool:
        """处理错误"""
        print(f"\n🚨 错误发生: {error.__class__.__name__}: {error}")

        # 创建上下文
        context = RecoveryContext(
            error=error, domain_config=domain_config, report=report, execution_time_ms=execution_time_ms
        )

        # 评估严重程度
        severity = context.severity

        # 选择恢复策略
        strategy_name = self._select_recovery_strategy(context, severity)

        if not strategy_name:
            print(f"⚠️   {context.error_info.get('type')}: 无可用恢复策略")
            self._record_failure(error, context, "no_available_strategy")
            return False

        # 获取策略
        try:
            strategy = self._get_strategy(strategy_name)
        except ValueError as e:
            print(f"❌ 策略加载失败: {e}")
            self._record_failure(error, context, "strategy_load_failed")
            return False

        # 执行恢复
        print(f"🔧 使用策略: {strategy_name}")

        try:
            result = strategy.recover(error, context)

            # 记录结果
            self.history_manager.add_record(result)

            # 更新系统状态
            self._record_recovery_attempt(error, context, result.success)

            return result.success

        except Exception as e:
            print(f"❌ 恢复执行失败: {e}")
            self._record_failure(error, context, "execution_exception")
            return False

    def _get_strategy(self, strategy_name: str) -> Any:
        """获取恢复策略"""
        try:
            return get_strategy_by_name(strategy_name)
        except (ImportError, AttributeError) as _e:
            raise ValueError(f"Unknown strategy: {strategy_name}")

    def _select_recovery_strategy(self, context: RecoveryContext, severity: RecoverySeverity) -> str | None:
        """根据上下文选择最佳策略"""
        # 查找历史成功模式
        similar_history = self.history_manager.find_similar_errors(context.error_info)

        # 如果有历史记录，使用成功率最高的策略
        if similar_history:
            best_record = sorted(similar_history, key=lambda r: r.success_rate, reverse=True)[0]
            if best_record.success_rate > 0.7:  # 成功率>70%
                return best_record.action_id

        # 根据严重程度选择
        if severity == RecoverySeverity.CRITICAL:
            # 严重错误：使用manual策略
            print("🔴 严重错误，使用人工确认模式")
            return "manual"
        elif severity == RecoverySeverity.HIGH:
            # 高度错误：使用半自动策略
            print("🟠 高度错误，使用半自动策略")
            return "semi_auto"
        elif severity == RecoverySeverity.MEDIUM:
            # 中度错误：使用自动策略
            print("🟡 中度错误，使用自动策略")
            return "auto"
        else:
            # 低严重错误：使用自动策略
            print("🟢 低严重错误，使用自动策略")
            return "auto"

    def _record_recovery_attempt(self, error: Exception, context: RecoveryContext, success: bool):
        """记录恢复尝试"""
        self.total_recoveries += 1

        if success:
            self.successful_recoveries += 1
        else:
            self.failed_recoveries += 1

        # 更新性能统计
        if success and context.execution_time_ms > 0:
            # 更新平均恢复时间
            current_avg = self.performance_stats["avg_recovery_time_ms"]
            new_avg = (current_avg * self.total_recoveries + context.execution_time_ms) / (self.total_recoveries + 1)
            self.performance_stats["avg_recovery_time_ms"] = new_avg

        # 严重错误记录到文件
        if context.severity in [RecoverySeverity.CRITICAL, RecoverySeverity.FATAL]:
            self._record_critical_failure(error, context)

    def _record_failure(self, error: Exception, context: RecoveryContext, reason: str):
        """记录失败记录"""
        failure_record = {
            "error_type": error.__class__.__name__,
            "error_message": str(error),
            "timestamp": context.timestamp,
            "reason": reason,
            "context_summary": {
                "domain_entities": len(context.domain_config.entities) if context.domain_config else 0,
                "execution_time_ms": context.execution_time_ms,
                "environment": context.metadata.get("environment", "unknown"),
            },
        }

        # 保存失败日志
        self._save_failure_log(failure_record)

    def _record_critical_failure(self, error: Exception, context: RecoveryContext):
        """记录严重失败"""
        log_file = self.storage_path.replace(".json", "_critical_failures.log")

        with open(log_file, "a", encoding="utf-8") as f:
            log_entry = f"[{datetime.now().isoformat()}] CRITICAL: {context.error_info.get('type')}: {str(error)}\n"
            f.write(log_entry)

        print(f"🚨 严重错误已记录到: {log_file}")

    def _save_failure_log(self, failure_record: dict):
        """保存失败日志"""
        log_file = self.storage_path.replace(".json", "_failures.log")

        with open(log_file, "a", encoding="utf-8") as f:
            log_entry = (
                f"[{datetime.now().isoformat()}] FAILED: {failure_record['error_type']}: {failure_record['error_message']}\n"
            )
            f.write(log_entry)

    def get_system_health_status(self) -> dict[str, Any]:
        """获取系统健康状态"""
        return {
            "status": self.status,
            "total_recoveries": self.total_recoveries,
            "successful_recoveries": self.successful_recoveries,
            "failed_recoveries": self.failed_recoveries,
            "success_rate": self.successful_recoveries / self.total_recoveries if self.total_recoveries > 0 else 0,
            "performance_stats": self.performance_stats,
            "available_patterns": len(self.patterns),
            "timestamp": datetime.now().isoformat(),
        }
