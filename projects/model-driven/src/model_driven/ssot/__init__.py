"""
model_driven.ssot — SSOT 全生命周期化

提供生命周期、价值体系、过程的单一事实源管理。
"""

from .lifecycle_ssot import (
    CrossStageConsistencyChecker,
    LifecycleSSOT,
    ProcessSSOT,
    SSOTSnapshot,
    ValueSSOT,
)

__all__ = [
    "SSOTSnapshot",
    "LifecycleSSOT",
    "ValueSSOT",
    "ProcessSSOT",
    "CrossStageConsistencyChecker",
]
