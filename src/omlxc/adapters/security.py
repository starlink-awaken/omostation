"""Fail-closed redaction and safe adapter exceptions."""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import cast

from omlxc.domain.errors import sanitize_sensitive
from omlxc.domain.protocols import AdapterError, AdapterErrorCode, StreamPhase

_LOCAL_PATH = re.compile(
    r"(?<![A-Za-z0-9])(?:file://)?(?:/Users/[^/\s,;]+|/Volumes/[^/\s,;]+)"
    r"(?:/[^\s,;]*)?"
)


def redact_adapter_text(value: str) -> str:
    sanitized = sanitize_sensitive(value)
    assert isinstance(sanitized, str)
    return _LOCAL_PATH.sub("[REDACTED_PATH]", sanitized)


def redact_adapter_data(value: object) -> object:
    """Recursively remove credentials, URL userinfo, and local model paths."""
    if isinstance(value, str):
        return redact_adapter_text(value)
    if isinstance(value, Mapping):
        mapping = cast(Mapping[object, object], value)
        sanitized = sanitize_sensitive(mapping)
        assert isinstance(sanitized, dict)
        sanitized_mapping = cast(Mapping[object, object], sanitized)
        return {str(key): redact_adapter_data(item) for key, item in sanitized_mapping.items()}
    if isinstance(value, (list, tuple)):
        sequence = cast(list[object] | tuple[object, ...], value)
        redacted = tuple(redact_adapter_data(item) for item in sequence)
        return list(redacted) if isinstance(value, list) else redacted
    return value


class AdapterFailure(Exception):
    """Exception boundary carrying only a typed and already-redacted error."""

    def __init__(self, error: AdapterError) -> None:
        self.error = error
        super().__init__(error.message)

    @classmethod
    def from_detail(
        cls,
        *,
        code: AdapterErrorCode,
        message: str,
        detail: object,
        retryable: bool = False,
        http_status: int | None = None,
        endpoint: str | None = None,
        emitted_content: bool = False,
        phase: StreamPhase = StreamPhase.BEFORE_CONTENT,
    ) -> AdapterFailure:
        safe_detail = redact_adapter_data(detail)
        safe_message = redact_adapter_text(message)
        if safe_detail not in ({}, (), [], None, ""):
            safe_message = f"{safe_message}: {safe_detail!r}"
        return cls(
            AdapterError(
                code=code,
                message=safe_message,
                retryable=retryable,
                http_status=http_status,
                endpoint=None if endpoint is None else redact_adapter_text(endpoint),
                emitted_content=emitted_content,
                phase=phase,
            )
        )

    def __repr__(self) -> str:
        return f"AdapterFailure({self.error.model_dump_json()})"
