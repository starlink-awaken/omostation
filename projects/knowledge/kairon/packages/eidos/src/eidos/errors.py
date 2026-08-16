"""Unified error codes for Eidos.

Usage:
    from eidos.errors import EidosError, ErrorCode
    raise EidosError(ErrorCode.VALIDATION_FAILED, "Card missing required field 'id'")
"""

from __future__ import annotations

from enum import StrEnum


class ErrorCode(StrEnum):
    """Standard error codes for all Eidos operations."""

    # ── Schema errors ──
    SCHEMA_NOT_FOUND = "SCHEMA_NOT_FOUND"
    INVALID_SCHEMA = "INVALID_SCHEMA"
    SCHEMA_REGISTRY_ERROR = "SCHEMA_REGISTRY_ERROR"
    SCHEMA_VERSION_MISMATCH = "SCHEMA_VERSION_MISMATCH"
    SCHEMA_MIGRATION_FAILED = "SCHEMA_MIGRATION_FAILED"

    # ── Validation errors ──
    VALIDATION_FAILED = "VALIDATION_FAILED"
    INVALID_TYPE = "INVALID_TYPE"
    MISSING_FIELD = "MISSING_FIELD"

    # ── Storage errors ──
    STORAGE_WRITE_FAILED = "STORAGE_WRITE_FAILED"
    STORAGE_READ_FAILED = "STORAGE_READ_FAILED"
    STORAGE_CONNECTION_ERROR = "STORAGE_CONNECTION_ERROR"

    # ── Pipeline errors ──
    PIPELINE_STEP_FAILED = "PIPELINE_STEP_FAILED"
    PIPELINE_UNKNOWN_TOOL = "PIPELINE_UNKNOWN_TOOL"

    # ── MCP errors ──
    MCP_UNKNOWN_TOOL = "MCP_UNKNOWN_TOOL"
    MCP_UNKNOWN_METHOD = "MCP_UNKNOWN_METHOD"
    MCP_INVALID_REQUEST = "MCP_INVALID_REQUEST"
    MCP_EXPORT_FAILED = "MCP_EXPORT_FAILED"

    # ── Type / Protocol errors ──
    TYPE_UNSUPPORTED = "TYPE_UNSUPPORTED"
    TYPE_CONVERSION_FAILED = "TYPE_CONVERSION_FAILED"

    # ── General errors ──
    FILE_NOT_FOUND = "FILE_NOT_FOUND"
    INVALID_JSON = "INVALID_JSON"
    INTERNAL_ERROR = "INTERNAL_ERROR"


class EidosError(Exception):
    """Base exception for all Eidos errors with structured error code."""

    def __init__(self, code: ErrorCode, message: str, details: dict | None = None) -> None:
        self.code = code
        self.details = details or {}
        super().__init__(f"[{code.value}] {message}")

    def to_dict(self) -> dict:
        return {"code": self.code.value, "message": self.args[0], "details": self.details}


class EidosWarning(UserWarning):
    """Non-fatal warning for degraded but operable states.

    Examples: LLM fallback, storage fallback, deprecated path.
    """

    def __init__(self, code: ErrorCode, message: str, details: dict | None = None) -> None:
        self.code = code
        self.details = details or {}
        super().__init__(f"[{code.value}] {message}")
