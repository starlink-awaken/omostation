"""Strict OpenAI-compatible tool-call parsing shared by backend adapters."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from typing import cast

from pydantic import ValidationError

from omlxc.domain.protocols import ChatToolCall, ToolCallDelta


def parse_tool_calls(value: object) -> tuple[ChatToolCall, ...]:
    if value is None:
        return ()
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise ValueError("tool_calls must be a bounded array")
    items = cast(Sequence[object], value)
    if len(items) > 128:
        raise ValueError("tool_calls must be a bounded array")
    try:
        return tuple(ChatToolCall.model_validate(item) for item in items)
    except ValidationError as exc:
        raise ValueError("tool_calls contain an invalid item") from exc


def parse_tool_call_deltas(value: object) -> tuple[ToolCallDelta, ...]:
    if value is None:
        return ()
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise ValueError("tool call deltas must be a bounded array")
    items = cast(Sequence[object], value)
    if len(items) > 128:
        raise ValueError("tool call deltas must be a bounded array")
    try:
        return tuple(ToolCallDelta.model_validate(item) for item in items)
    except ValidationError as exc:
        raise ValueError("tool call deltas contain an invalid item") from exc


def tools_payload(request: object) -> dict[str, object]:
    tools = getattr(request, "tools", ())
    choice = getattr(request, "tool_choice", None)
    payload: dict[str, object] = {}
    if tools:
        payload["tools"] = [tool.model_dump(mode="json") for tool in tools]
    if choice is not None:
        payload["tool_choice"] = (
            choice if isinstance(choice, str) else choice.model_dump(mode="json")
        )
    return payload


def parse_ollama_tool_calls(value: object) -> tuple[ChatToolCall, ...]:
    if value is None:
        return ()
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise ValueError("Ollama tool_calls must be a bounded array")
    items = cast(Sequence[object], value)
    if len(items) > 128:
        raise ValueError("Ollama tool_calls must be a bounded array")
    calls: list[ChatToolCall] = []
    for index, item in enumerate(items):
        if not isinstance(item, Mapping):
            raise ValueError("Ollama tool call must be an object")
        item_mapping = cast(Mapping[object, object], item)
        function = item_mapping.get("function")
        if not isinstance(function, Mapping):
            raise ValueError("Ollama tool call must include a function")
        function_mapping = cast(Mapping[object, object], function)
        name = function_mapping.get("name")
        arguments = function_mapping.get("arguments", {})
        if not isinstance(name, str):
            raise ValueError("Ollama tool call name is invalid")
        if isinstance(arguments, str):
            encoded_arguments = arguments
        else:
            try:
                encoded_arguments = json.dumps(
                    arguments,
                    ensure_ascii=True,
                    allow_nan=False,
                    separators=(",", ":"),
                )
            except (TypeError, ValueError) as exc:
                raise ValueError("Ollama tool call arguments are invalid") from exc
        digest = hashlib.sha256(f"{index}:{name}:{encoded_arguments}".encode()).hexdigest()[:24]
        try:
            calls.append(
                ChatToolCall.model_validate(
                    {
                        "id": f"call_{digest}",
                        "type": "function",
                        "function": {"name": name, "arguments": encoded_arguments},
                    }
                )
            )
        except ValidationError as exc:
            raise ValueError("Ollama tool call is invalid") from exc
    return tuple(calls)
