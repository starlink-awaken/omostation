"""
SSOT Kernel — Recovery Module
==================================
智能错误恢复模块

功能：
1. 智能错误检测和分类
2. 多种恢复策略
3. 恢复历史学习机制
4. 恢复决策树
5. 自动化恢复和半自动恢复
"""

from .decision_tree import RecoveryDecisionTree
from .history import RecoveryHistoryManager
from .recovery_framework import (
    IntelligentRecoverySystem,
    RecoveryConfig,
    RecoveryResult,
    RecoveryStatus,
    RecoveryStrategyType,
)
from .strategies.auto_patterns import AutoRecoveryStrategy
from .strategies.base import BaseRecoveryStrategy

__all__ = [
    # Framework
    "IntelligentRecoverySystem",
    "RecoveryConfig",
    "RecoveryResult",
    "RecoveryStatus",
    # Strategies
    "RecoveryStrategyType",
    "AutoRecoveryStrategy",
    "SemiAutoRecoveryStrategy",
    "ManualRecoveryStrategy",
    "BaseRecoveryStrategy",
    # History & Learning
    "RecoveryHistoryManager",
    # Decision Making
    "RecoveryDecisionTree",
    # Dependencies
    "RecoveryHistory",
]
