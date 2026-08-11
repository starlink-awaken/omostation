"""Small standards-compliant Server-Sent Events framing decoder."""

from __future__ import annotations

import codecs
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SSEFinish:
    events: tuple[str, ...]
    incomplete_event: bool


class SSEDecoder:
    """Incrementally frame UTF-8 SSE bytes into joined data payloads."""

    def __init__(self) -> None:
        decoder_factory = codecs.getincrementaldecoder("utf-8")
        self._decoder: codecs.IncrementalDecoder = decoder_factory(errors="strict")
        self._text = ""
        self._data_lines: list[str] = []

    def feed(self, chunk: bytes) -> tuple[str, ...]:
        self._text += self._decoder.decode(chunk, final=False)
        return self._drain_lines(final=False)

    def finish(self) -> SSEFinish:
        self._text += self._decoder.decode(b"", final=True)
        events = self._drain_lines(final=True)
        return SSEFinish(events=events, incomplete_event=bool(self._data_lines))

    def _drain_lines(self, *, final: bool) -> tuple[str, ...]:
        events: list[str] = []
        while self._text:
            boundary = self._next_boundary(final=final)
            if boundary is None:
                if final:
                    self._process_line(self._text, events)
                    self._text = ""
                break
            index, width = boundary
            line = self._text[:index]
            self._text = self._text[index + width :]
            self._process_line(line, events)
        return tuple(events)

    def _next_boundary(self, *, final: bool) -> tuple[int, int] | None:
        for index, character in enumerate(self._text):
            if character == "\n":
                return index, 1
            if character != "\r":
                continue
            if index + 1 == len(self._text) and not final:
                return None
            width = 2 if self._text[index + 1 : index + 2] == "\n" else 1
            return index, width
        return None

    def _process_line(self, line: str, events: list[str]) -> None:
        if not line:
            if self._data_lines:
                events.append("\n".join(self._data_lines))
                self._data_lines.clear()
            return
        if line.startswith(":"):
            return
        field, separator, value = line.partition(":")
        if separator and value.startswith(" "):
            value = value[1:]
        if field == "data":
            self._data_lines.append(value)
