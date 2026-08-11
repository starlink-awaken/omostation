"""MockTransport integration flow for native Ollama discovery and inference."""

from __future__ import annotations

import json

import httpx
import pytest

from omlxc.adapters.ollama import OllamaAdapter
from omlxc.domain.protocols import (
    ChatMessage,
    ChatRequest,
    EmbeddingRequest,
    OperationStatus,
    StreamEventKind,
)


@pytest.mark.asyncio
async def test_ollama_native_discover_lifecycle_chat_embed_and_stream_flow() -> None:
    loaded = False

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal loaded
        if request.url.path == "/api/version":
            return httpx.Response(200, json={"version": "0.12.6"})
        if request.url.path == "/api/tags":
            return httpx.Response(
                200,
                json={
                    "models": [
                        {
                            "name": "library/model:latest",
                            "model": "library/model:latest",
                            "digest": "sha256:integration",
                        }
                    ]
                },
            )
        if request.url.path == "/api/ps":
            models = (
                [
                    {
                        "name": "library/model:latest",
                        "model": "library/model:latest",
                        "digest": "sha256:integration",
                    }
                ]
                if loaded
                else []
            )
            return httpx.Response(200, json={"models": models})
        if request.url.path == "/api/generate":
            payload = json.loads(request.content)
            loaded = payload["keep_alive"] != 0
            return httpx.Response(200, json={"done": True, "response": ""})
        if request.url.path == "/api/embed":
            return httpx.Response(
                200,
                json={"embeddings": [[1.0, 2.0]], "prompt_eval_count": 1},
            )
        if request.url.path == "/api/chat":
            payload = json.loads(request.content)
            assert payload["think"] is False
            if payload["stream"]:
                return httpx.Response(
                    200,
                    content=(
                        b'{"message":{"content":"he"},"done":false}\n'
                        b'{"message":{"content":"llo"},"done":false}\n'
                        b'{"message":{"content":""},"done":true,'
                        b'"done_reason":"stop","prompt_eval_count":1,"eval_count":2}\n'
                    ),
                )
            return httpx.Response(
                200,
                json={
                    "message": {"content": "visible"},
                    "done": True,
                    "done_reason": "stop",
                    "prompt_eval_count": 1,
                    "eval_count": 1,
                },
            )
        raise AssertionError(request.url.path)

    adapter = OllamaAdapter(
        backend_id="integration-ollama",
        base_url="https://ollama.invalid",
        probe_model_id="library/model:latest",
        keep_alive_seconds=120,
        transport=httpx.MockTransport(handler),
    )
    request = ChatRequest(
        request_id="integration-chat",
        model="library/model:latest",
        messages=(ChatMessage(role="user", content="hello"),),
    )
    try:
        cold = await adapter.discover()
        load = await adapter.load_model("library/model:latest")
        ready = await adapter.discover()
        chat = await adapter.chat(request)
        embedding = await adapter.embed(
            EmbeddingRequest(
                request_id="integration-embed",
                model="library/model:latest",
                input="hello",
            )
        )
        stream = [event async for event in adapter.stream_chat(request)]
        unload = await adapter.unload_model("library/model:latest")
    finally:
        await adapter.aclose()

    assert cold.generation_ready is False
    assert load.status is OperationStatus.SUCCEEDED
    assert ready.generation_ready is True
    assert chat.content == "visible"
    assert embedding.embeddings == ((1.0, 2.0),)
    assert [event.kind for event in stream] == [
        StreamEventKind.CONTENT,
        StreamEventKind.CONTENT,
        StreamEventKind.USAGE,
        StreamEventKind.DONE,
    ]
    assert unload.status is OperationStatus.SUCCEEDED
