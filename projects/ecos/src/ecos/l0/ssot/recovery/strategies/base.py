"""
SSOT Kernel — Base Recovery Strategy
===========================================
恢复策略基类

功能：
1. 定义恢复策略的统一接口
2. 提供策略的元数据和方法
3. 支持策略链和决策集成
4. 提供恢复结果的标准格式
"""

from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class RecoveryStrategyType(Enum):
    """恢复策略类型"""

    AUTO = "auto"  # 自动恢复
    SEMI_AUTO = "semi_auto"  # 半自动恢复
    MANUAL = "manual"  # 人工确认恢复


class RecoveryStatus(Enum):
    """恢复状态"""

    PENDING = "pending"  # 待处理
    ANALYZING = "analyzing"  # 分析中
    READY = "ready"  # 就绪执行
    IN_PROGRESS = "in_progress"  # 执行中
    COMPLETED = "completed"  # 已完成
    FAILED = "failed"  # 失败
    SKIPPED = "skipped"  # 跳过
    ACCEPTED = "accepted"  # 已接受
    REJECTED = "rejected"  # 已拒绝


@dataclass
class RecoveryCondition:
    """恢复条件"""

    id: str
    name: str
    description: str
    condition: Callable[[Any], bool]  # 判断函数
    severity: str = "WARN"  # WARN, ERROR, CRITICAL
    category: str = "general"  # general, dependency, performance, data_quality
    enabled: bool = True

    def evaluate(self, context: dict[str, Any]) -> bool:
        """评估条件是否满足"""
        try:
            return self.condition(context)
        except Exception as e:
            print(f"⚠️  条件评估失败: {self.name}: {e}")
            return False


@dataclass
class RecoveryAction:
    """恢复动作"""

    id: str
    name: str
    description: str
    apply_function: Callable[[Any], bool]  # 执行函数
    estimated_recovery_time: float = 0.0  # 预估恢复时间（秒）
    risk_level: str = "medium"  # low, medium, high, critical
    side_effects: list[str] = field(default_factory=list)

    def apply(self, context: dict[str, Any]) -> bool:
        """执行恢复动作"""
        try:
            success = self.apply_function(context)
            return success
        except Exception as e:
            print(f"❌ 恢复动作执行失败: {self.name}: {e}")
            return False


@dataclass
class RecoveryResult:
    """恢复结果"""

    id: str
    strategy: str
    status: RecoveryStatus
    success: bool
    message: str
    error: str | None = None
    actions_executed: list[str] = field(default_factory=list)
    recovery_time_ms: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def severity(self) -> str:
        if self.status == RecoveryStatus.COMPLETED:
            return "SUCCESS"
        elif self.status == RecoveryStatus.FAILED:
            return "FAILED"
        elif self.status == RecoveryStatus.ACCEPTED:
            return "ACCEPTED"
        elif self.status == RecoveryStatus.REJECTED:
            return "REJECTED"
        elif self.status == RecoveryStatus.SKIPPED:
            return "SKIPPED"
        else:
            return "UNKNOWN"

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "id": self.id,
            "strategy": self.strategy,
            "status": self.status.value,
            "success": self.success,
            "message": self.message,
            "error": self.error,
            "actions_executed": self.actions_executed,
            "recovery_time_ms": self.recovery_time_ms,
            "metadata": self.metadata,
            "timestamp": datetime.now().isoformat(),
        }


class BaseRecoveryStrategy(ABC):
    """恢复策略基类"""

    def __init__(self, name: str, config=None):
        self.name = name
        self.config = config or RecoveryConfig()

    @property
    @abstractmethod
    def strategy_name(self) -> str:
        """策略名称"""
        pass

    @abstractmethod
    def can_handle(self, error: Exception, context: dict[str, Any]) -> bool:
        """判断是否能处理此错误"""
        pass

    @abstractmethod
    def analyze(self, error: Exception, context: dict[str, Any]) -> dict[str, Any]:
        """分析错误并生成恢复方案"""
        pass

    @abstractmethod
    def recover(self, error: Exception, context: dict[str, Any]) -> RecoveryResult:
        """执行恢复操作"""
        pass

    def _is_error_critical(self, error: Exception) -> bool:
        """判断是否为严重错误"""
        critical_types = (MemoryError, OSError, RuntimeError, SystemError)
        return isinstance(error, critical_types)

    def _get_error_info(self, error: Exception) -> dict[str, Any]:
        """获取错误信息"""
        error_type = type(error).__name__
        error_message = str(error)

        error_info = {
            "type": error_type,
            "message": error_message,
            "file": None,
            "line": None,
            "function": None,
        }

        return {
            "type": error_type,
            "message": error_message,
            "full_string": error_info.get("full_string", error_message),
        }

    def _get_legacy_error_info(self, error: Exception) -> dict[str, Any]:
        """获取传统错误信息（兼容Python < 3.8）"""
        import sys

        exc_type, exc_value, exc_traceback = sys.exc_info()

        file = None
        function = None
        line = None
        if exc_traceback is not None:
            tb_frame = exc_traceback.tb_frame
            if tb_frame is not None:
                file = tb_frame.f_lineno  # type: ignore[union-attr]
                function = tb_frame.f_code.co_name  # type: ignore[union-attr]
                line = tb_frame.f_lineno  # type: ignore[union-attr]

        return {
            "type": type(error).__name__,
            "message": str(error),
            "file": file,
            "function": function,
            "line": line,
        }


class RecoveryConfig:
    """恢复配置"""

    def __init__(self):
        self.max_retry_attempts = 3
        self.auto_retry_delay = 1.0
        self.manual_confirmation_timeout = 300
        self.learning_rate = 0.1
        self.history_size = 1000

    @staticmethod
    def _is_critical_error(error: Exception) -> bool:
        """判断是否为严重错误"""
        critical_types = (MemoryError, SystemError, KeyboardInterrupt, SystemExit)
        return isinstance(error, critical_types)

    def get_retry_count(self, error: Exception) -> int:
        """获取重试次数"""
        if self._is_critical_error(error):
            return 0  # 严重错误不重试
        return self.max_retry_attempts

    def should_retry(self, current_attempt: int, error: Exception) -> bool:
        """是否应该重试"""
        if current_attempt >= self.max_retry_attempts:
            return False

        # 检查是否是内存错误
        if isinstance(error, MemoryError):
            return False  # 内存错误不重试

        return current_attempt < self.max_retry_attempts
