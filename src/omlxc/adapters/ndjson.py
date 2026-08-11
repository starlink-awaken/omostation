"""Backend-neutral incremental newline-delimited JSON framing."""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import cast


class NDJSONDecodeError(ValueError):
    """A framing or JSON-shape error that never includes remote input."""

    def __init__(self, message: str = "invalid NDJSON stream") -> None:
        super().__init__(message)


class NDJSONLimitError(NDJSONDecodeError):
    """A fixed-message record or aggregate stream size violation."""

    def __init__(self) -> None:
        super().__init__("NDJSON stream exceeds its configured byte limit")


class NDJSONDecoder:
    """Decode UTF-8 bytes into one JSON object per LF or CRLF-delimited line."""

    def __init__(
        self,
        *,
        max_record_bytes: int = 1_048_576,
        max_total_bytes: int = 16_777_216,
    ) -> None:
        if (
            type(max_record_bytes) is not int
            or type(max_total_bytes) is not int
            or max_record_bytes <= 0
            or max_total_bytes < max_record_bytes
        ):
            raise ValueError("NDJSON limits must be positive and total must cover one record")
        self._max_record_bytes = max_record_bytes
        self._max_total_bytes = max_total_bytes
        self._record = bytearray()
        self._total_bytes = 0

    def feed(self, chunk: bytes) -> tuple[dict[str, object], ...]:
        self._total_bytes += len(chunk)
        if self._total_bytes > self._max_total_bytes:
            raise NDJSONLimitError()
        documents: list[dict[str, object]] = []
        start = 0
        while True:
            newline = chunk.find(b"\n", start)
            if newline < 0:
                self._append(chunk[start:])
                break
            self._append(chunk[start:newline])
            if self._record.endswith(b"\r"):
                del self._record[-1]
            if self._record:
                documents.append(self._parse(bytes(self._record)))
            self._record.clear()
            start = newline + 1
        return tuple(documents)

    def finish(self) -> tuple[dict[str, object], ...]:
        if not self._record:
            return ()
        record = bytes(self._record)
        self._record.clear()
        return (self._parse(record),)

    def _append(self, value: bytes) -> None:
        if len(self._record) + len(value) > self._max_record_bytes:
            raise NDJSONLimitError()
        self._record.extend(value)

    @staticmethod
    def _parse(line: bytes) -> dict[str, object]:
        try:
            text = line.decode("utf-8", errors="strict")
            value = cast(object, json.loads(text))
        except UnicodeDecodeError as exc:
            raise NDJSONDecodeError("NDJSON stream contains invalid UTF-8") from exc
        except json.JSONDecodeError as exc:
            raise NDJSONDecodeError() from exc
        if not isinstance(value, Mapping):
            raise NDJSONDecodeError("NDJSON record must be a JSON object")
        mapping = cast(Mapping[object, object], value)
        return {str(key): item for key, item in mapping.items()}
