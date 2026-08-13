from __future__ import annotations

import json

import httpx
import pytest

from omlxc.adapters.lmstudio import LmStudioAdapter
from omlxc.adapters.omlx_app import OmlxAppAdapter
from omlxc.domain.protocols import (
    ChatMessage,
    ChatRequest,
    ChatTool,
    ChatToolCall,
    ChatToolFunction,
    ChatToolFunctionCall,
    StreamEventKind,
)


def _request() -> ChatRequest:
    call = ChatToolCall(
        id="call_read",
        function=ChatToolFunctionCall(name="read", arguments='{"filePath":"README.md"}'),
    )
    return ChatRequest(
        request_id="req-agent",
        model="coding",
        messages=(
            ChatMessage(role="user", content="inspect"),
            ChatMessage(role="assistant", content="", tool_calls=(call,)),
            ChatMessage(role="tool", content="first line", tool_call_id="call_read"),
        ),
        tools=(
            ChatTool(
                function=ChatToolFunction(
                    name="read",
                    description="read one file",
                    parameters={"type": "object", "properties": {}},
                )
            ),
        ),
        tool_choice="auto",
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("adapter_type", [OmlxAppAdapter, LmStudioAdapter])
async def test_openai_adapters_forward_and_parse_tool_calls(adapter_type: type[object]) -> None:
    captured: dict[str, object] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        captured.update(json.loads(request.content))
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": "",
                            "tool_calls": [
                                {
                                    "id": "call_write",
                                    "type": "function",
                                    "function": {"name": "write", "arguments": "{}"},
                                }
                            ],
                        },
                        "finish_reason": "tool_calls",
                    }
                ]
            },
        )

    adapter = adapter_type(  # type: ignore[call-arg]
        backend_id="backend",
        base_url="http://backend.invalid",
        transport=httpx.MockTransport(handler),
    )
    result = await adapter.chat(_request())  # type: ignore[attr-defined]

    assert captured["tools"] == [
        {
            "type": "function",
            "function": {
                "name": "read",
                "description": "read one file",
                "parameters": {"type": "object", "properties": {}},
            },
        }
    ]
    assert captured["tool_choice"] == "auto"
    assert captured["messages"][1]["tool_calls"][0]["id"] == "call_read"  # type: ignore[index]
    assert captured["messages"][2]["tool_call_id"] == "call_read"  # type: ignore[index]
    assert result.success is True
    assert result.content == ""
    assert result.finish_reason == "tool_calls"
    assert result.tool_calls[0].function.name == "write"


@pytest.mark.asyncio
@pytest.mark.parametrize("adapter_type", [OmlxAppAdapter, LmStudioAdapter])
async def test_openai_adapters_stream_tool_call_deltas(adapter_type: type[object]) -> None:
    frames = "".join(
        (
            "data: "
            + json.dumps(
                {
                    "choices": [
                        {
                            "delta": {
                                "tool_calls": [
                                    {
                                        "index": 0,
                                        "id": "call_read",
                                        "type": "function",
                                        "function": {
                                            "name": "read",
                                            "arguments": '{"filePath":"',
                                        },
                                    }
                                ]
                            },
                            "finish_reason": None,
                        }
                    ]
                }
            )
            + "\n\n",
            "data: "
            + json.dumps(
                {
                    "choices": [
                        {
                            "delta": {
                                "tool_calls": [
                                    {
                                        "index": 0,
                                        "function": {"arguments": 'README.md"}'},
                                    }
                                ]
                            },
                            "finish_reason": "tool_calls",
                        }
                    ]
                }
            )
            + "\n\n",
            "data: [DONE]\n\n",
        )
    ).encode()
    adapter = adapter_type(  # type: ignore[call-arg]
        backend_id="backend",
        base_url="http://backend.invalid",
        transport=httpx.MockTransport(lambda _request: httpx.Response(200, content=frames)),
    )

    events = [event async for event in adapter.stream_chat(_request())]  # type: ignore[attr-defined]

    assert [event.kind for event in events] == [
        StreamEventKind.TOOL_CALL,
        StreamEventKind.TOOL_CALL,
        StreamEventKind.DONE,
    ]
    assert events[0].tool_calls[0].function.name == "read"
    assert events[1].tool_calls[0].function.arguments == 'README.md"}'
    assert events[-1].finish_reason == "tool_calls"


@pytest.mark.asyncio
@pytest.mark.parametrize("adapter_type", [OmlxAppAdapter, LmStudioAdapter])
async def test_openai_adapters_turn_malformed_tool_delta_into_typed_error(
    adapter_type: type[object],
) -> None:
    frame = b'data: {"choices":[{"delta":{"tool_calls":[{"index":-1}]}}]}\n\n'
    adapter = adapter_type(  # type: ignore[call-arg]
        backend_id="backend",
        base_url="http://backend.invalid",
        transport=httpx.MockTransport(lambda _request: httpx.Response(200, content=frame)),
    )

    events = [event async for event in adapter.stream_chat(_request())]  # type: ignore[attr-defined]

    assert len(events) == 1
    assert events[0].kind is StreamEventKind.ERROR
    assert events[0].error is not None
    assert events[0].error.code.value == "bad_response"
