"""统一错误处理 — Agora CLI | v1.0
=====================================
提供 CLI 专用的异常体系，含 actionable 错误建议和装饰器。

用法:
    from agora.cli.errors import CLIError, handle_cli_error

    raise CLIError("服务不存在", suggestion="使用 'agora list' 查看")

    @handle_cli_error
    def cmd_register(args):
        ...
"""

from __future__ import annotations

import sys
import traceback


class CLIError(Exception):
    """CLI 统一基异常 — 包含 exit_code 和 actionable suggestion"""

    exit_code: int = 1
    suggestion: str = ""

    def __init__(
        self, message: str, exit_code: int | None = None, suggestion: str = ""
    ):
        super().__init__(message)
        self.message = message
        if exit_code is not None:
            self.exit_code = exit_code
        self.suggestion = suggestion or self.__class__.suggestion


# ── 专用异常子类 ──


class ServiceNotFoundError(CLIError):
    """服务不存在"""

    exit_code = 1
    suggestion = "使用 'agora list' 查看所有已注册服务"


class RegistrationError(CLIError):
    """注册失败"""

    exit_code = 1
    suggestion = "检查服务配置是否正确，或使用 --no-governance 跳过校验"


class ConfigError(CLIError):
    """配置错误"""

    exit_code = 1
    suggestion = "运行 'agora config' 检查配置，或 'agora init' 重新初始化"


class ToolNotFoundError(CLIError):
    """工具不存在"""

    exit_code = 1
    suggestion = (
        "使用 'agora repo list' 查看已有工具，或 'agora repo discover' 发现新工具"
    )


class AuthError(CLIError):
    """认证/授权错误"""

    exit_code = 1
    suggestion = "检查 API Key 是否有效: agora key list"


# ── 装饰器 ──


def handle_cli_error(func):
    """装饰器：捕获异常，格式化输出，返回正确 exit code。

    支持的异常类型:
    - CLIError 及其子类 → 格式化错误 + suggestion
    - KeyboardInterrupt  → 友好中断消息
    - Exception           → 普通错误 + --debug 提示
    """

    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except CLIError as e:
            _print_formatted_error(e.message, e.suggestion)
            return e.exit_code
        except KeyboardInterrupt:
            print("\n中断。", file=sys.stderr)
            return 130
        except Exception as e:
            _print_formatted_error(
                str(e), "使用 'agora --help' 获取帮助，或检查日志了解详情"
            )
            if "AGORA_DEBUG" in os.environ:
                traceback.print_exc()
            return 1

    return wrapper


def _print_formatted_error(message: str, suggestion: str = "") -> None:
    """统一的错误输出格式"""
    print(f"\nError: {message}", file=sys.stderr)
    if suggestion:
        print(f"  Hint: {suggestion}", file=sys.stderr)
    print(file=sys.stderr)


# ── 工具函数 ──

import os  # noqa: E402


def safe_exit(exit_code: int, message: str = "") -> None:
    """安全退出，确保输出最后一条消息"""
    if message:
        print(message)
    sys.exit(exit_code)
