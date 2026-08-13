from __future__ import annotations

import json
from collections.abc import AsyncIterator

import httpx
import pytest

from omlxc.api import create_app
from omlxc.dataplane import ChatExecution
from omlxc.domain import RouteProfile
from omlxc.domain.protocols import (
    ChatRequest,
    ChatResult,
    ChatToolCall,
    ChatToolFunctionCall,
    StreamEvent,
    StreamEventKind,
    StreamPhase,
    ToolCallDelta,
    ToolFunctionDelta,
)


class AgentProtocolService:
    def __init__(self) -> None:
        self.requests: list[ChatRequest] = []
        self.result = ChatResult(request_id="unused", success=True, content="answer")
        self.events: tuple[StreamEvent, ...] = ()
        self.routes: list[object] = []

    async def list_openai_models(self) -> tuple[str, ...]:
        return ("coding",)

    async def chat(self, route: object, request: ChatRequest, *, deadline: float) -> ChatExecution:
        del deadline
        self.routes.append(route)
        self.requests.append(request)
        return ChatExecution(
            request_id=request.request_id,
            model_id=request.model,
            success=True,
            placement_id="placement-local",
            attempted_placements=("placement-local",),
            result=self.result.model_copy(update={"request_id": request.request_id}),
            backend_id="backend-local",
            profile=RouteProfile.INTERACTIVE,
        )

    def stream_chat(
        self, route: object, request: ChatRequest, *, deadline: float
    ) -> AsyncIterator[StreamEvent]:
        del route, deadline
        self.requests.append(request)

        async def source() -> AsyncIterator[StreamEvent]:
            for event in self.events:
                yield event.model_copy(update={"request_id": request.request_id})

        return source()


def _tools(count: int = 79) -> list[dict[str, object]]:
    return [
        {
            "type": "function",
            "function": {
                "name": f"tool_{index}",
                "description": "bounded test tool",
                "parameters": {
                    "type": "object",
                    "properties": {"path": {"type": "string"}},
                    "required": ["path"],
                },
            },
        }
        for index in range(count)
    ]


@pytest.mark.asyncio
async def test_openai_agent_request_accepts_large_system_tools_and_tool_result_roundtrip() -> None:
    service = AgentProtocolService()
    transport = httpx.ASGITransport(app=create_app(inference=service))
    messages = [
        {"role": "system", "content": "s" * 152_468},
        {"role": "user", "content": "inspect"},
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {
                    "id": "call_read",
                    "type": "function",
                    "function": {"name": "tool_0", "arguments": '{"path":"README.md"}'},
                }
            ],
        },
        {"role": "tool", "tool_call_id": "call_read", "content": "first line"},
    ]
    async with httpx.AsyncClient(transport=transport, base_url="http://omlxc") as client:
        response = await client.post(
            "/openai/v1/chat/completions",
            json={
                "model": "coding",
                "messages": messages,
                "tools": _tools(),
                "tool_choice": "auto",
                "max_tokens": 32_000,
            },
        )

    assert response.status_code == 200
    captured = service.requests[0]
    assert len(captured.tools) == 79
    assert captured.tool_choice == "auto"
    assert captured.messages[0].content == "s" * 152_468
    assert captured.messages[2].tool_calls[0].function.name == "tool_0"
    assert captured.messages[3].tool_call_id == "call_read"
    assert service.routes[0].context_tokens > 32_000  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_openai_nonstream_and_stream_preserve_typed_tool_calls() -> None:
    service = AgentProtocolService()
    tool_call = ChatToolCall(
        id="call_read",
        function=ChatToolFunctionCall(name="read", arguments='{"filePath":"README.md"}'),
    )
    service.result = ChatResult(
        request_id="unused",
        success=True,
        content="",
        tool_calls=(tool_call,),
        finish_reason="tool_calls",
    )
    transport = httpx.ASGITransport(app=create_app(inference=service))
    request = {
        "model": "coding",
        "messages": [{"role": "user", "content": "inspect"}],
        "tools": _tools(1),
        "tool_choice": "auto",
    }
    async with httpx.AsyncClient(transport=transport, base_url="http://omlxc") as client:
        nonstream = await client.post("/openai/v1/chat/completions", json=request)

        service.events = (
            StreamEvent(
                kind=StreamEventKind.TOOL_CALL,
                request_id="unused",
                tool_calls=(
                    ToolCallDelta(
                        index=0,
                        id="call_read",
                        type="function",
                        function=ToolFunctionDelta(name="read", arguments='{"filePath":"'),
                    ),
                ),
                emitted_content=True,
                phase=StreamPhase.AFTER_CONTENT,
                placement_id="placement-local",
                backend_id="backend-local",
            ),
            StreamEvent(
                kind=StreamEventKind.TOOL_CALL,
                request_id="unused",
                tool_calls=(
                    ToolCallDelta(
                        index=0,
                        function=ToolFunctionDelta(arguments='README.md"}'),
                    ),
                ),
                emitted_content=True,
                phase=StreamPhase.AFTER_CONTENT,
                placement_id="placement-local",
                backend_id="backend-local",
            ),
            StreamEvent(
                kind=StreamEventKind.DONE,
                request_id="unused",
                finish_reason="tool_calls",
                emitted_content=True,
                phase=StreamPhase.COMPLETE,
                placement_id="placement-local",
                backend_id="backend-local",
            ),
        )
        stream = await client.post("/openai/v1/chat/completions", json={**request, "stream": True})

    message = nonstream.json()["choices"][0]["message"]
    assert message == {
        "role": "assistant",
        "content": "",
        "tool_calls": [tool_call.model_dump(mode="json")],
    }
    data = [
        json.loads(line.removeprefix("data: "))
        for line in stream.text.splitlines()
        if line.startswith("data: {")
    ]
    assert data[0]["choices"][0]["delta"]["tool_calls"][0]["function"]["name"] == "read"
    assert data[1]["choices"][0]["delta"]["tool_calls"][0]["function"]["arguments"] == 'README.md"}'
    assert data[2]["choices"][0]["finish_reason"] == "tool_calls"
    assert stream.text.count("data: [DONE]") == 1
