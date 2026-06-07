"""
SSOT Kernel — Auto Recovery Strategy
===========================================
自动恢复策略

功能：
1. 识别可自动恢复的错误类型
2. 查找历史恢复模式
3. 自动应用已验证的修复方案
4. 记录恢复结果用于学习
"""

from dataclasses import dataclass, field
from typing import Any

from .strategies.base import (
    BaseRecoveryStrategy,
    RecoveryAction,
    RecoveryCondition,
    RecoveryConfig,
    RecoveryResult,
    RecoveryStatus,
)


@dataclass
class RecoveryPattern:
    """恢复模式"""

    id: str
    name: str
    error_pattern: str  # Python错误类型或模式匹配
    success_count: int = 0
    failure_count: int = 0
    actions: list[RecoveryAction] = field(default_factory=list)
    conditions: list[RecoveryCondition] = field(default_factory=list)
    created_at: str = ""
    last_used: str = ""
    success_rate: float = 0.0


class AutoRecoveryStrategy(BaseRecoveryStrategy):
    """自动恢复策略"""

    def __init__(self, config: RecoveryConfig | None = None):
        super().__init__("自动恢复", config)
        self.patterns: dict[str, RecoveryPattern] = {}
        self.learning_rate = 0.8  # 学习率

    @property
    def strategy_name(self) -> str:
        return "auto"

    def can_handle(self, error: Exception, context: dict[str, Any]) -> bool:
        """判断是否能处理此错误"""
        # 内存错误不自动恢复
        if isinstance(error, MemoryError):
            return False

        # 部分错误类型可以处理
        handleable_types = [
            (AttributeError, True),  # 属性缺失错误
            (KeyError, True),  # 键缺失错误
            (ValueError, True),  # 值类型错误
            (TypeError, True),  # 类型错误
            (RuntimeError, True),
        ]

        for error_type, can_recover in handleable_types:
            if isinstance(error, error_type):
                return can_recover

        return False

    def analyze(self, error: Exception, context: dict[str, Any]) -> dict[str, Any]:
        """分析错误并生成恢复方案"""
        error_info = self._get_error_info(error)

        analysis = {
            "error_type": error_info["type"],
            "error_message": error_info["message"],
            "file": error_info.get("file"),
            "function": error_info.get("function"),
            "line": error_info.get("line"),
            "context": {
                "domain_entities": len(context.get("domain", {}).get("entities", [])),
                "domain_facts": len(context.get("domain", {}).get("facts", [])),
                "execution_time_ms": context.get("execution_time_ms", 0),
                "environment": self.monitor.environment_type.value if hasattr(self, "monitor") else "unknown",
            },
        }

        # 查找匹配的恢复模式
        matching_pattern = self._find_matching_pattern(error_info)

        if matching_pattern:
            analysis["matched_pattern"] = matching_pattern.name
            analysis["recovery_patterns"] = self._list_available_patterns()
            analysis["suggested_actions"] = [action.name for action in matching_pattern.actions]
        else:
            analysis["matched_pattern"] = None
            analysis["suggested_actions"] = []

        # 查找历史恢复记录
        history_matches = self._find_history_matches(error_info)
        analysis["history_matches"] = history_matches

        return analysis

    def _find_matching_pattern(self, error_info: dict[str, Any]) -> RecoveryPattern | None:
        """查找匹配的错误模式"""
        error_info["type"]
        error_message = error_info["message"].lower()

        # 模式匹配表
        pattern_mappings = {
            "memoryerror": {
                "pattern_id": "pattern_memory_error",
                "name": "内存错误恢复",
                "error_patterns": ["cannot", "memory", "allocation", "out of memory", "exceeded"],
            },
            "keyerror": {
                "pattern_id": "pattern_key_error",
                "name": "键错误恢复",
                "error_patterns": ["key", '"', "'entity", "attribute", "not found"],
            },
            "attributeerror": {
                "pattern_id": "pattern_attribute_error",
                "name": "属性错误恢复",
                "error_patterns": ["attribute", "not found", "has no attribute"],
            },
            "valueerror": {
                "pattern_id": "pattern_value_error",
                "name": "值错误恢复",
                "error_patterns": ["invalid literal", "type mismatch", "int()", "too many values", "none"],
            },
            "ioerror": {
                "pattern_id": "pattern_io_error",
                "name": "IO错误恢复",
                "error_patterns": ["io", "file", "not found", "permission denied"],
            },
        }

        # 查找匹配
        for error_category, pattern_info in pattern_mappings.items():
            for pattern_text in pattern_info["error_patterns"]:
                if pattern_text in error_message:
                    # 查找匹配的模式
                    from ..strategies.patterns.auto_patterns import auto_patterns

                    return auto_patterns.get(pattern_info["pattern_id"])

        return None

    def _list_available_patterns(self) -> list[str]:
        """列出可用的恢复模式"""
        return [
            "pattern_memory_error",
            "pattern_key_error",
            "pattern_attribute_error",
            "pattern_value_error",
            "pattern_io_error",
        ]

    def _find_history_matches(self, error_info: dict[str, Any]) -> list[dict[str, Any]]:
        """查找历史恢复记录"""
        # 简化版本：从测试数据中查找类似错误
        matches: list[dict[str, Any]] = []

        [
            {"error_type": error_info["type"], "solution": "创建默认实体", "time": "1-3分钟"},
            {"error_type": error_info["type"], "solution": "检查规则依赖", "time": "3-5分钟"},
        ]

        return matches

    def recover(self, error: Exception, context: dict[str, Any]) -> RecoveryResult:
        """执行自动恢复"""
        error_info = self._get_error_info(error)

        # 查找匹配的模式
        matching_pattern = self._find_matching_pattern(error_info)

        if not matching_pattern:
            # 没有匹配的模式
            return RecoveryResult(
                id=f"auto_{error_info.get('type', 'unknown')}",
                strategy=self.strategy_name,
                status=RecoveryStatus.SKIPPED,
                success=False,
                message=f"无匹配的恢复模式: {error_info['type']}",
                error=error_info["full_string"],
            )

        # 选择恢复动作
        recovery_actions = matching_pattern.actions

        if not recovery_actions:
            return RecoveryResult(
                id=f"auto_{error_info.get('type', 'unknown')}",
                strategy=self.strategy_name,
                status=RecoveryStatus.COMPLETED,
                success=True,
                message=f"发现匹配模式: {matching_pattern.name}, 但无恢复动作",
            )

        # 选择最合适的动作
        best_action = self._select_best_action(recovery_actions, error_info, context)

        if best_action:
            print(f"🔧 自动执行恢复动作: {best_action.name}")

            # 执行恢复
            success = best_action.apply(context)

            # 记录结果
            self._record_recovery_result(error_info, best_action, success)

            if success:
                return RecoveryResult(
                    id=f"auto_{error_info.get('type', 'unknown')}",
                    strategy=self.strategy_name,
                    status=RecoveryStatus.COMPLETED,
                    success=True,
                    message=f"自动恢复成功: {best_action.name}",
                    recovery_time_ms=best_action.estimated_recovery_time,
                    actions_executed=[best_action.name],
                )
            else:
                return RecoveryResult(
                    id=f"auto_{error_info.get('type', 'unknown')}",
                    strategy=self.strategy_name,
                    status=RecoveryStatus.FAILED,
                    success=False,
                    message=f"自动恢复失败: {best_action.name}",
                    error=f"执行失败: {error_info['full_string']}",
                )
        else:
            return RecoveryResult(
                id=f"auto_{error_info.get('type', 'unknown')}",
                strategy=self.strategy_name,
                status=RecoveryStatus.COMPLETED,
                success=True,
                message="无恢复动作，但记录模式匹配",
            )

    def _select_best_action(
        self, actions: list[RecoveryAction], error_info: dict[str, Any], context: dict[str, Any]
    ) -> RecoveryAction | None:
        """选择最佳恢复动作"""
        # 按风险和复杂度排序
        scored_actions = []

        for action in actions:
            score = 0

            # 风险越低越好
            if action.risk_level == "low":
                score += 30
            elif action.risk_level == "medium":
                score += 20
            elif action.risk_level == "high":
                score += 10
            else:
                score += 0

            # 成功率越高越好
            if action.estimated_recovery_time > 0:
                # 成功率95%以上，+20分
                if action.estimated_recovery_time < 1000:
                    score += 20
                else:
                    score -= 10

            # 历史成功率越高越好
            if action.id in self.patterns:
                pattern = self.patterns[action.id]
                if pattern.success_rate > 0.8:  # 成功率>80%
                    score += 15
                elif pattern.success_rate > 0.6:  # 成功率>60%
                    score += 10
                elif pattern.success_rate > 0.4:  # 成功率>40%
                    score += 5

            # 优先选择快速动作
            if action.estimated_recovery_time < 10:
                score += 10
            elif action.estimated_recovery_time < 30:
                score += 5
            else:
                score -= 5

            # 优先选择成功率高的
            if action.id in self.patterns:
                pattern = self.patterns[action.id]
                confidence = pattern.success_rate if pattern else 0.0
                if confidence > 0.7:
                    score += 10
                elif confidence > 0.5:
                    score += 5
                else:
                    score -= 5

            scored_actions.append((score, action))

        # 按分数排序，返回最优策略
        if scored_actions:
            scored_actions.sort(key=lambda x: x[0], reverse=True)
            return scored_actions[0][1] if scored_actions else None
        return None

    def _record_recovery_result(self, error_info: dict[str, Any], action: RecoveryAction, success: bool):
        """记录恢复结果用于学习"""
        # 如果有对应的模式，更新成功/失败率
        if action.id in self.patterns:
            pattern = self.patterns[action.id]
            if success:
                pattern.success_count += 1
            else:
                pattern.failure_count += 1

            # 更新成功率
            total = pattern.success_count + pattern.failure_count
            if total > 0:
                pattern.success_rate = pattern.success_count / total
                print(f"📈 更新模式成功率: {pattern.success_rate * 100:.1f}%")

    def get_recovery_summary(self) -> dict[str, Any]:
        """获取恢复摘要"""
        total_patterns = len(self.patterns)
        active_patterns = [p for p in self.patterns.values() if p.failure_count > 0]

        successful_patterns = [p for p in self.patterns.values() if p.success_count > 0]

        return {
            "strategy": self.strategy_name,
            "total_patterns": total_patterns,
            "active_patterns": len(active_patterns),
            "successful_patterns": len(successful_patterns),
            "average_success_rate": sum(
                p.success_count / (p.success_count + p.failure_count)
                for p in self.patterns.values()
                if p.success_count + p.failure_count > 0
            ),
            "learning_rate": self.learning_rate,
        }
