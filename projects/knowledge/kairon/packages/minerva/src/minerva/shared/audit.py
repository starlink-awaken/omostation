"""Audit logging — structured, immutable records of all MCP and Web API operations.

Usage:
    from minerva.shared.audit import audit

    audit.info("mcp_tool_called", tool="research_now", query="...", task_id="a1b2c3d4")
    audit.info("web_api_request", method="POST", path="/api/research", ip="127.0.0.1")
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

import structlog

logger = structlog.get_logger("audit")

# Write audit events to a structured JSONL log file
_AUDIT_DIR = Path(os.environ.get("MINERVA_AUDIT_DIR", Path.home() / ".minerva" / "audit"))
_audit_dir_ready = False


def _ensure_audit_dir() -> None:
    global _audit_dir_ready
    if not _audit_dir_ready:
        try:
            _AUDIT_DIR.mkdir(parents=True, exist_ok=True)
            _audit_dir_ready = True
        except Exception:
            pass


def _write_event(level: str, event: str, **kwargs: Any) -> None:
    """Write a structured audit event to the JSONL log."""
    record = {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "level": level,
        "event": event,
        **kwargs,
    }
    _ensure_audit_dir()
    try:
        log_file = _AUDIT_DIR / f"audit-{time.strftime('%Y%m%d')}.jsonl"
        with open(log_file, "a") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception:
        pass  # Audit failure must never break the application


class AuditLogger:
    """Structured audit logger for security-relevant events."""

    def info(self, event: str, **kwargs: Any) -> None:
        logger.info(event, **kwargs)
        _write_event("INFO", event, **kwargs)

    def warning(self, event: str, **kwargs: Any) -> None:
        logger.warning(event, **kwargs)
        _write_event("WARNING", event, **kwargs)

    def error(self, event: str, **kwargs: Any) -> None:
        logger.error(event, **kwargs)
        _write_event("ERROR", event, **kwargs)

    # Convenience methods for specific events

    def mcp_tool_called(self, tool: str, **params: Any) -> None:
        self.info("mcp_tool_called", tool=tool, **{k: str(v)[:200] for k, v in params.items()})

    def web_api_request(self, method: str, path: str, ip: str, status: int, duration_ms: float = 0) -> None:
        self.info(
            "web_api_request",
            method=method,
            path=path,
            ip=ip,
            status=status,
            duration_ms=round(duration_ms, 2),
        )

    def auth_failure(self, path: str, ip: str, reason: str) -> None:
        self.warning("auth_failure", path=path, ip=ip, reason=reason)

    def rate_limit_hit(self, ip: str, path: str) -> None:
        self.warning("rate_limit_hit", ip=ip, path=path)

    def ssrf_blocked(self, url: str, caller: str) -> None:
        self.warning("ssrf_blocked", url=url, caller=caller)

    def config_change(self, key: str, source: str) -> None:
        self.info("config_change", key=key, source=source)


# Singleton
audit = AuditLogger()
