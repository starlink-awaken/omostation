"""
SSOT Kernel — Recovery Patterns
===========================================
错误模式定义和恢复策略

功能：
1. 预定义不同类型错误的恢复模式
2. 配置恢复动作和条件
3. 关联历史学习数据
"""


from ..strategies.base import (
    BaseRecoveryStrategy,
    RecoveryAction,
    RecoveryCondition,
    RecoveryPattern,
)

# ── 错误模式定义 ───────────────────────────────────────

# 1. 内存错误恢复模式
PATTERN_MEMORY_ERROR = RecoveryPattern(
    id="pattern_memory_error",
    name="内存错误恢复",
    error_patterns=["cannot", "memory", "allocation", "out of memory", "exceeded"],
    actions=[
        RecoveryAction(
            id="clear_cache",
            name="清理缓存",
            apply_function=lambda ctx: True,
            estimated_recovery_time=2.0,
            risk_level="low",
            description="清理Python缓存，释放内存",
            side_effects=["可能导致短期内存增加", "不影响数据完整性"],
        ),
        RecoveryAction(
            id="restart_process",
            name="重启Python进程",
            apply_function=lambda ctx: True,
            estimated_recovery_time=60.0,
            risk_level="medium",
            description="重启Python进程以释放所有内存",
            side_effects=["所有内存丢失", "连接可能中断", "需要重新初始化"],
        ),
        RecoveryAction(
            id="reduce_load",
            name="减少数据加载",
            apply_function=lambda ctx: True,
            estimated_recovery_time=10.0,
            risk_level="medium",
            description="减少数据加载量以降低内存使用",
            side_effects=["功能限制", "数据完整性可能降低"],
        ),
    ],
    conditions=[
        RecoveryCondition(
            id="mem_leak_detector",
            name="内存泄漏检测",
            description="检测连续多次内存错误",
            severity="INFO",
            condition=lambda ctx: False,  # 在引擎内部判断
        )
    ],
)

# 2. 键错误恢复模式
PATTERN_KEY_ERROR = RecoveryPattern(
    id="pattern_key_error",
    name="键错误恢复",
    error_patterns=["key", '"entity', "attribute", "not found"],
    actions=[
        RecoveryAction(
            id="create_default",
            name="创建默认实体",
            apply_function=lambda ctx: True,
            estimated_recovery_time=5.0,
            risk_level="low",
            description="使用默认值创建缺失的实体",
            side_effects=["功能限制", "业务逻辑可能受限"],
        ),
        RecoveryAction(
            id="skip_current_operation",
            name="跳过当前操作",
            apply_function=lambda ctx: True,
            estimated_recovery_time=0.1,
            risk_level="low",
            description="跳过当前操作以避免错误",
            side_effects=["功能限制", "可能影响结果"],
        ),
        RecoveryAction(
            id="check_dependencies",
            name="检查依赖",
            apply_function=lambda ctx: True,
            estimated_recovery_time=15.0,
            risk_level="medium",
            description="检查实体依赖完整性",
            side_effects=["可能发现其他问题", "需要人工介入"],
        ),
    ],
)

# 3. 属性错误恢复模式
PATTERN_ATTRIBUTE_ERROR = RecoveryPattern(
    id="pattern_attribute_error",
    name="属性错误恢复",
    error_patterns=["attribute", "not found", "has no attribute"],
    actions=[
        RecoveryAction(
            id="use_default_value",
            name="使用默认值",
            apply_function=lambda ctx: True,
            estimated_recovery_time=1.0,
            risk_level="low",
            description="使用预定义的默认值",
            side_effects=["逻辑可能偏离预期"],
        ),
        RecoveryAction(
            id="skip_entity_processing",
            name="跳过实体处理",
            apply_function=lambda ctx: True,
            estimated_recovery_time=0.5,
            risk_level="low",
            description="跳过该实体的处理",
            side_effects=["该实体数据被忽略"],
        ),
    ],
)

# 4. 值错误恢复模式
PATTERN_VALUE_ERROR = RecoveryPattern(
    id="pattern_value_error",
    name="值错误恢复",
    error_patterns=["invalid literal", "type mismatch", "int()", "too many values", "none"],
    actions=[
        RecoveryAction(
            id="type_conversion",
            name="类型转换",
            apply_function=lambda ctx: True,
            estimated_recovery_time=1.0,
            risk_level="low",
            description="尝试类型转换",
            side_effects=["数据可能不准确", "可能丢失精度"],
        ),
        RecoveryAction(
            id="use_default_value",
            name="使用默认值",
            apply_function=lambda ctx: True,
            estimated_recovery_time=0.1,
            risk_level="low",
            description="使用安全的默认值",
            side_effects=["可能影响计算结果"],
        ),
    ],
)

# 5. IO错误恢复模式
PATTERN_IO_ERROR = RecoveryPattern(
    id="pattern_io_error",
    name="IO错误恢复",
    error_patterns=["io", "file", "not found", "permission denied"],
    actions=[
        RecoveryAction(
            id="skip_file_operation",
            name="跳过文件操作",
            apply_function=lambda ctx: True,
            estimated_recovery_time=0.1,
            risk_level="low",
            description="跳过有问题的文件操作",
            side_effects=["功能受限", "数据可能不同步"],
        ),
        RecoveryAction(
            id="check_permissions",
            name="检查权限",
            apply_function=lambda ctx: True,
            estimated_recovery_time=5.0,
            risk_level="medium",
            description="检查文件访问权限",
            side_effects=["可能发现其他权限问题"],
        ),
    ],
)

# ── 策略工厂函数 ──────────────────────────────────────


def get_strategy_by_name(strategy_name: str) -> BaseRecoveryStrategy:
    """根据名称获取策略"""
    if strategy_name == "auto":
        from ..strategies.auto_patterns import AutoRecoveryStrategy

        return AutoRecoveryStrategy()
    else:
        raise ValueError(f"未知策略: {strategy_name}")
