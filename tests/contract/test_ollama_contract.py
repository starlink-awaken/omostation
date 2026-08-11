"""Run the shared backend contract against native Ollama HTTP."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator

import httpx

from .backend_adapter_contract import (
    BackendAdapterContract,
    ContractHarness,
    ContractScenario,
)


class BrokenNDJSONStream(httpx.AsyncByteStream):
    def __init__(self, first_chunk: bytes | None) -> None:
        self._first_chunk = first_chunk

    async def __aiter__(self) -> AsyncIterator[bytes]:
        if self._first_chunk is not None:
            yield self._first_chunk
        raise httpx.ReadError("synthetic half response")


class TestOllamaContract(BackendAdapterContract):
    __test__ = True

    @staticmethod
    def make_harness(scenario: ContractScenario) -> ContractHarness:
        from omlxc.adapters.ollama import OllamaAdapter

        async def handler(request: httpx.Request) -> httpx.Response:
            if request.url.path == "/api/version":
                return httpx.Response(200, json={"version": "0.12.6"})
            if request.url.path == "/api/tags":
                if scenario is ContractScenario.HEALTH_ONLY:
                    return httpx.Response(404, json={"error": "not found"})
                return httpx.Response(
                    200,
                    json={
                        "models": [
                            {
                                "name": "model-a",
                                "model": "model-a",
                                "digest": "sha256:model-a",
                            }
                        ]
                    },
                )
            if request.url.path == "/api/ps":
                loaded = scenario in {
                    ContractScenario.GENERATION_READY,
                    ContractScenario.MODEL_ALREADY_LOADED,
                }
                models = (
                    [
                        {
                            "name": "model-a",
                            "model": "model-a",
                            "digest": "sha256:model-a",
                        }
                    ]
                    if loaded
                    else []
                )
                return httpx.Response(200, json={"models": models})
            if request.url.path == "/api/embed":
                return httpx.Response(404, json={"error": "unsupported"})
            if request.url.path == "/api/chat":
                payload = json.loads(request.content)
                assert payload["think"] is False
                if scenario is ContractScenario.STREAM_SUCCESS:
                    return httpx.Response(
                        200,
                        content=(
                            b'{"message":{"content":"hello"},"done":false}\n'
                            b'{"message":{"content":""},"done":true,'
                            b'"done_reason":"stop","prompt_eval_count":2,"eval_count":1}\n'
                        ),
                    )
                if scenario is ContractScenario.STREAM_EMPTY:
                    return httpx.Response(200, content=b"")
                if scenario is ContractScenario.STREAM_NON_JSON:
                    return httpx.Response(200, content=b"not-json\n")
                if scenario is ContractScenario.STREAM_BREAK_BEFORE_CONTENT:
                    return httpx.Response(200, stream=BrokenNDJSONStream(None))
                if scenario is ContractScenario.STREAM_BREAK_AFTER_CONTENT:
                    return httpx.Response(
                        200,
                        stream=BrokenNDJSONStream(
                            b'{"message":{"content":"hello"},"done":false}\n'
                        ),
                    )
                if scenario is ContractScenario.REASONING_RESPONSE:
                    return httpx.Response(
                        200,
                        json={
                            "message": {
                                "content": "<think>hidden-reasoning</think>visible",
                                "thinking": "hidden-reasoning",
                            },
                            "thinking": "hidden-reasoning",
                            "done": True,
                        },
                    )
                assert payload["stream"] is False
                assert payload["options"]["num_predict"] == 1
                return httpx.Response(
                    200,
                    json={"message": {"content": "O"}, "done": True},
                )
            raise AssertionError(f"unexpected request: {request.method} {request.url.path}")

        adapter = OllamaAdapter(
            backend_id="remote-ollama",
            base_url="https://ollama.invalid",
            probe_model_id="model-a",
            transport=httpx.MockTransport(handler),
        )
        return ContractHarness(adapter=adapter)
