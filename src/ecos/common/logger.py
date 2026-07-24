"""ECOS 统一日志系统"""

import json
import logging
from datetime import datetime, timezone
from typing import Optional


class ECOSFormatter(logging.Formatter):
    """结构化日志格式"""

    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        return json.dumps(log_entry, ensure_ascii=False)


_logger: Optional[logging.Logger] = None


def get_logger(name: str = "ecos") -> logging.Logger:
    """获取统一日志器"""
    global _logger
    if _logger is None:
        _logger = logging.getLogger("ecos")
        _logger.setLevel(logging.DEBUG)

        if not _logger.handlers:
            handler = logging.StreamHandler()
            handler.setFormatter(ECOSFormatter())
            _logger.addHandler(handler)

    return _logger.getChild(name)
