"""Exit code contract for Cockpit CLI."""

from enum import IntEnum


class ExitCode(IntEnum):
    """Standardized machine exit codes for Cockpit commands."""

    SUCCESS = 0  # 正常完成
    GENERAL_FAILURE = 1  # 业务逻辑断言失败或未捕获通用异常
    USAGE_ERROR = 2  # 命令行参数语法错误 / 未知子命令
    PERMISSION_DENIED = 3  # 鉴权失败或 RBAC 域权限受限
    RESOURCE_NOT_FOUND = 4  # 目标资源、文件或微服务不存在
    UPSTREAM_ERROR = 5  # 下游微服务超时、熔断或不可达

    # Tier-1 兼容别名
    GENERAL_ERROR = 1
    INVALID_ARGS = 2
    CONFIG_ERROR = 1
    SERVICE_UNAVAILABLE = 5
    RESOURCE_EXHAUSTED = 1

