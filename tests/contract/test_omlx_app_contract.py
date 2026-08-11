"""Run the shared adapter contract against the oMLX App implementation."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator

import httpx

from .backend_adapter_contract import (
    BackendAdapterContract,
    ContractHarness,
    ContractScenario,
)


class BrokenSSEStream(httpx.AsyncByteStream):
    def __init__(self, first_chunk: bytes | None) -> None:
        self._first_chunk = first_chunk

    async def __aiter__(self) -> AsyncIterator[bytes]:
        if self._first_chunk is not None:
            yield self._first_chunk
        raise httpx.ReadError("synthetic half response")


class TestOmlxAppContract(BackendAdapterContract):
    __test__ = True

    @staticmethod
    def make_harness(scenario: ContractScenario) -> ContractHarness:
        from omlxc.adapters.omlx_app import OmlxAppAdapter

        requests: list[httpx.Request] = []

        async def handler(request: httpx.Request) -> httpx.Response:
            requests.append(request)
            if request.url.path == "/api/status":
                return httpx.Response(200, json={"status": "running", "version": "0.5.7"})
            if request.url.path == "/v1/models":
                if scenario is ContractScenario.HEALTH_ONLY:
                    return httpx.Response(404, json={"detail": "not found"})
                loaded = scenario in {
                    ContractScenario.GENERATION_READY,
                    ContractScenario.MODEL_ALREADY_LOADED,
                }
                return httpx.Response(
                    200,
                    json={
                        "object": "list",
                        "data": [
                            {
                                "id": "model-a",
                                "object": "model",
                                "owned_by": "omlx",
                                "loaded": loaded,
                            }
                        ],
                    },
                )
            if request.url.path == "/v1/models/status":
                return httpx.Response(200, json={"models": []})
            if request.url.path == "/v1/embeddings":
                return httpx.Response(404, json={"detail": "unsupported"})
            if request.url.path == "/v1/chat/completions" and request.method == "POST":
                if scenario is ContractScenario.STREAM_SUCCESS:
                    body = (
                        'data: {"choices":[{"delta":{"content":"hello"}}]}\n\n'
                        'data: {"choices":[],"usage":{"prompt_tokens":2,'
                        '"completion_tokens":1,"total_tokens":3}}\n\n'
                        "data: [DONE]\n\n"
                    )
                    return httpx.Response(
                        200,
                        content=body,
                        headers={"content-type": "text/event-stream"},
                    )
                if scenario is ContractScenario.STREAM_EMPTY:
                    return httpx.Response(
                        200,
                        content=b"",
                        headers={"content-type": "text/event-stream"},
                    )
                if scenario is ContractScenario.STREAM_NON_JSON:
                    return httpx.Response(200, content=b"data: not-json\n\n")
                if scenario is ContractScenario.STREAM_BREAK_BEFORE_CONTENT:
                    return httpx.Response(200, stream=BrokenSSEStream(None))
                if scenario is ContractScenario.STREAM_BREAK_AFTER_CONTENT:
                    chunk = b'data: {"choices":[{"delta":{"content":"hello"}}]}\n\n'
                    return httpx.Response(200, stream=BrokenSSEStream(chunk))
                if scenario is ContractScenario.REASONING_RESPONSE:
                    return httpx.Response(
                        200,
                        json={
                            "id": "chatcmpl-test",
                            "object": "chat.completion",
                            "choices": [
                                {
                                    "index": 0,
                                    "message": {
                                        "role": "assistant",
                                        "reasoning_content": "hidden-reasoning",
                                        "content": "<think>hidden-reasoning</think>visible",
                                    },
                                    "finish_reason": "stop",
                                }
                            ],
                            "usage": {
                                "prompt_tokens": 1,
                                "completion_tokens": 1,
                                "total_tokens": 2,
                            },
                        },
                    )
                payload = json.loads(request.content)
                assert payload["max_tokens"] == 1
                return httpx.Response(
                    200,
                    json={"choices": [{"message": {"content": "O"}, "finish_reason": "length"}]},
                )
            raise AssertionError(f"unexpected request: {request.method} {request.url.path}")

        transport = httpx.MockTransport(handler)
        adapter = OmlxAppAdapter(
            backend_id="mbp-omlx",
            base_url="http://omlx.invalid",
            probe_model_id="model-a",
            transport=transport,
        )
        return ContractHarness(adapter=adapter, requests=requests)
