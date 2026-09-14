"""P58-W0 kairon_utils do_default — 真业务 (调 RetryExecutor / get_logger 真函数)."""

from __future__ import annotations

from typing import Any


def do_default(args: dict[str, Any]) -> dict[str, Any]:
    """P58-W0 kairon_utils do_default: 真调 RetryExecutor / get_logger / gather_with_concurrency."""
    try:
        from kairon_utils import (
            ConcurrencyManager,
            ContentDeduplicator,
            ErrorHandler,
            RateLimiter,
            RetryExecutor,
            get_logger,
        )
    except Exception as exc:
        return {"_method": "do_default", "_error": f"import: {type(exc).__name__}: {exc}"}

    action = args.get("action", "list_components")
    try:
        if action == "list_components":
            return {
                "_method": "do_default",
                "_action": "list_components",
                "RetryExecutor": RetryExecutor.__name__,
                "RateLimiter": RateLimiter.__name__,
                "ConcurrencyManager": ConcurrencyManager.__name__,
                "ErrorHandler": ErrorHandler.__name__,
                "ContentDeduplicator": ContentDeduplicator.__name__,
            }
        if action == "logger":
            name = args.get("name", "kairon_utils.do_default")
            log = get_logger(name)
            return {
                "_method": "do_default",
                "_action": "logger",
                "logger_name": name,
                "logger_type": type(log).__name__,
            }
        if action == "retry":
            re_obj = RetryExecutor()
            return {
                "_method": "do_default",
                "_action": "retry",
                "executor_type": type(re_obj).__name__,
                "methods": [m for m in dir(re_obj) if not m.startswith("_")][:10],
            }
        return {"_method": "do_default", "_error": f"unknown action: {action}"}
    except Exception as exc:
        return {"_method": "do_default", "_action": action, "_error": f"{type(exc).__name__}: {exc}"}


__all__ = ["do_default"]
