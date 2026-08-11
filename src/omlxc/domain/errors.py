"""Stable error envelope, sanitization, and process exit mapping."""

from __future__ import annotations

import re
from collections.abc import Mapping
from types import MappingProxyType
from typing import Any, cast

from pydantic import JsonValue, field_serializer, field_validator

from .models import DomainModel

EXIT_SUCCESS = 0
EXIT_CONFIG = 2
EXIT_DAEMON = 3
EXIT_CAPACITY = 4
EXIT_TIMEOUT = 5
EXIT_PARTIAL = 6
EXIT_SECURITY = 7
EXIT_INTERNAL = 10

_SECRET_ASSIGNMENT = re.compile(r"(?i)(secret|token|api[_-]?key|password)\s*[:=]\s*([^\s,;]+)")
_URL_AUTH = re.compile(r"(?i)([a-z][a-z0-9+.-]*://)[^/@\s]+@")
_BEARER = re.compile(r"(?i)(authorization\s*:\s*bearer\s+)[^\s,;]+")
_SENSITIVE_KEYS = re.compile(r"(?i)(secret|token|api[_-]?key|password|authorization)")


def sanitize_sensitive(value: object) -> object:
    """Recursively redact authentication material without logging the input."""
    if isinstance(value, str):
        result = _URL_AUTH.sub(r"\1[REDACTED]@", value)
        result = _BEARER.sub(r"\1[REDACTED]", result)
        return _SECRET_ASSIGNMENT.sub(r"\1=[REDACTED]", result)
    if isinstance(value, dict):
        mapping = cast(dict[object, object], value)
        return {
            str(key): "[REDACTED]" if _SENSITIVE_KEYS.search(str(key)) else sanitize_sensitive(item)
            for key, item in mapping.items()
        }
    if isinstance(value, (list, tuple)):
        sequence = cast(list[object] | tuple[object, ...], value)
        sanitized = tuple(sanitize_sensitive(item) for item in sequence)
        return list(sanitized) if isinstance(value, list) else sanitized
    return value


class ErrorEnvelope(DomainModel):
    code: str = "E900"
    message: str
    technical_detail: str | None = None
    suggested_action: str | None = None
    request_id: str
    retryable: bool = False
    affected_resources: tuple[str, ...] = ()
    partial_result: Mapping[str, JsonValue] | None = None

    @field_validator("*", mode="before")
    @classmethod
    def redact_auth_material(cls, value: Any) -> Any:
        return sanitize_sensitive(value)

    @field_validator("partial_result")
    @classmethod
    def freeze_partial_result(
        cls, value: Mapping[str, JsonValue] | None
    ) -> Mapping[str, JsonValue] | None:
        return None if value is None else MappingProxyType(dict(value))

    @field_serializer("partial_result")
    def serialize_partial_result(
        self, value: Mapping[str, JsonValue] | None
    ) -> dict[str, JsonValue] | None:
        return None if value is None else dict(value)


def error_exit_code(code: str) -> int:
    if code.startswith("E1"):
        return EXIT_CONFIG
    if code.startswith("E2") or (code.startswith("E3") and code != "E305"):
        return EXIT_DAEMON
    if code == "E305":
        return EXIT_TIMEOUT
    if code.startswith("E4"):
        return EXIT_CAPACITY
    if code.startswith("E5"):
        return EXIT_PARTIAL
    if code.startswith("E7"):
        return EXIT_SECURITY
    return EXIT_INTERNAL
