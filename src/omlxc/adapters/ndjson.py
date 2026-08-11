"""Backend-neutral incremental newline-delimited JSON framing."""

from __future__ import annotations

import codecs
import json
from collections.abc import Mapping
from typing import cast


class NDJSONDecodeError(ValueError):
    """A framing or JSON-shape error that never includes remote input."""

    def __init__(self, message: str = "invalid NDJSON stream") -> None:
        super().__init__(message)


class NDJSONDecoder:
    """Decode UTF-8 bytes into one JSON object per LF or CRLF-delimited line."""

    def __init__(self) -> None:
        decoder_factory = codecs.getincrementaldecoder("utf-8")
        self._decoder: codecs.IncrementalDecoder = decoder_factory(errors="strict")
        self._text = ""

    def feed(self, chunk: bytes) -> tuple[dict[str, object], ...]:
        try:
            self._text += self._decoder.decode(chunk, final=False)
        except UnicodeDecodeError as exc:
            raise NDJSONDecodeError("NDJSON stream contains invalid UTF-8") from exc
        return self._drain(final=False)

    def finish(self) -> tuple[dict[str, object], ...]:
        try:
            self._text += self._decoder.decode(b"", final=True)
        except UnicodeDecodeError as exc:
            raise NDJSONDecodeError("NDJSON stream contains invalid UTF-8") from exc
        return self._drain(final=True)

    def _drain(self, *, final: bool) -> tuple[dict[str, object], ...]:
        documents: list[dict[str, object]] = []
        while True:
            newline = self._text.find("\n")
            if newline < 0:
                break
            line = self._text[:newline]
            self._text = self._text[newline + 1 :]
            if line.endswith("\r"):
                line = line[:-1]
            if line:
                documents.append(self._parse(line))
        if final and self._text:
            tail = self._text
            self._text = ""
            documents.append(self._parse(tail))
        return tuple(documents)

    @staticmethod
    def _parse(line: str) -> dict[str, object]:
        try:
            value = cast(object, json.loads(line))
        except json.JSONDecodeError as exc:
            raise NDJSONDecodeError() from exc
        if not isinstance(value, Mapping):
            raise NDJSONDecodeError("NDJSON record must be a JSON object")
        mapping = cast(Mapping[object, object], value)
        return {str(key): item for key, item in mapping.items()}
