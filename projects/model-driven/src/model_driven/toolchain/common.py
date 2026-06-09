"""model_driven.toolchain 公共工具函数

提供 toolchain 子包内共享的工具函数。
"""

from datetime import UTC, datetime


def now() -> str:
    """返回 UTC 时间戳 ISO 格式字符串"""
    return datetime.now(UTC).isoformat()
