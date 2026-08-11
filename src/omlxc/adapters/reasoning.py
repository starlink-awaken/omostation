"""Backend-neutral response filter for exact ``<think>`` reasoning blocks."""

from __future__ import annotations

_THINK_OPEN = "<think>"
_THINK_CLOSE = "</think>"


def _partial_tag_length(value: str, tag: str) -> int:
    lowered = value.lower()
    for length in range(min(len(value), len(tag) - 1), 0, -1):
        if lowered[-length:] == tag[:length]:
            return length
    return 0


class ReasoningFilter:
    """Remove exact think blocks without leaking tags split across chunks."""

    def __init__(self) -> None:
        self._buffer = ""
        self._depth = 0
        self._saw_reasoning = False

    @property
    def saw_reasoning(self) -> bool:
        return self._saw_reasoning

    def feed(self, chunk: str) -> str:
        self._buffer += chunk
        output: list[str] = []
        while self._buffer:
            lowered = self._buffer.lower()
            if self._depth:
                candidates: list[tuple[int, str]] = [
                    (position, tag)
                    for position, tag in (
                        (lowered.find(_THINK_OPEN), _THINK_OPEN),
                        (lowered.find(_THINK_CLOSE), _THINK_CLOSE),
                    )
                    if position >= 0
                ]
                if candidates:
                    position, tag = min(candidates, key=lambda item: item[0])
                    self._buffer = self._buffer[position + len(tag) :]
                    self._depth += 1 if tag == _THINK_OPEN else -1
                    continue
                keep = max(
                    _partial_tag_length(self._buffer, _THINK_OPEN),
                    _partial_tag_length(self._buffer, _THINK_CLOSE),
                )
                self._buffer = self._buffer[-keep:] if keep else ""
                return "".join(output)

            open_at = lowered.find(_THINK_OPEN)
            if open_at >= 0:
                self._saw_reasoning = True
                output.append(self._buffer[:open_at])
                self._buffer = self._buffer[open_at + len(_THINK_OPEN) :]
                self._depth = 1
                continue

            keep = _partial_tag_length(self._buffer, _THINK_OPEN)
            if keep:
                output.append(self._buffer[:-keep])
                self._buffer = self._buffer[-keep:]
            else:
                output.append(self._buffer)
                self._buffer = ""
            return "".join(output)
        return "".join(output)

    def finish(self) -> tuple[str, bool]:
        if self._depth:
            self._buffer = ""
            return "", True
        remaining = self._buffer
        self._buffer = ""
        return remaining, False
