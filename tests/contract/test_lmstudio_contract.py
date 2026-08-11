"""Run the shared backend contract against LM Studio / LM Link."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from pathlib import Path

import httpx

from omlxc.adapters.lmstudio import (
    LmsPlatform,
    LmStudioAdapter,
    ProcessOutput,
)

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


class TestLmStudioContract(BackendAdapterContract):
    __test__ = True

    @staticmethod
    def make_harness(scenario: ContractScenario) -> ContractHarness:
        async def runner(argv: tuple[str, ...], timeout: float) -> ProcessOutput:
            del argv, timeout
            loaded = scenario in {
                ContractScenario.GENERATION_READY,
                ContractScenario.MODEL_ALREADY_LOADED,
            }
            rows = [{"modelKey": "model-a", "identifier": "model-a"}] if loaded else []
            return ProcessOutput(returncode=0, stdout=json.dumps(rows), stderr="")

        async def handler(request: httpx.Request) -> httpx.Response:
            if request.url.path == "/v1/models":
                if scenario is ContractScenario.HEALTH_ONLY:
                    return httpx.Response(404, json={"error": "not found"})
                return httpx.Response(200, json={"data": [{"id": "model-a"}]})
            if request.url.path == "/v1/embeddings":
                return httpx.Response(404, json={"error": "unsupported"})
            if request.url.path == "/v1/chat/completions":
                if scenario is ContractScenario.STREAM_SUCCESS:
                    return httpx.Response(
                        200,
                        content=(
                            'data: {"choices":[{"delta":{"content":"hello"}}]}\n\n'
                            'data: {"choices":[],"usage":{"prompt_tokens":2,'
                            '"completion_tokens":1,"total_tokens":3}}\n\n'
                            "data: [DONE]\n\n"
                        ),
                    )
                if scenario is ContractScenario.STREAM_EMPTY:
                    return httpx.Response(200, content=b"")
                if scenario is ContractScenario.STREAM_NON_JSON:
                    return httpx.Response(200, content=b"data: not-json\n\n")
                if scenario is ContractScenario.STREAM_BREAK_BEFORE_CONTENT:
                    return httpx.Response(200, stream=BrokenSSEStream(None))
                if scenario is ContractScenario.STREAM_BREAK_AFTER_CONTENT:
                    return httpx.Response(
                        200,
                        stream=BrokenSSEStream(
                            b'data: {"choices":[{"delta":{"content":"hello"}}]}\n\n'
                        ),
                    )
                if scenario is ContractScenario.REASONING_RESPONSE:
                    return httpx.Response(
                        200,
                        json={
                            "choices": [
                                {
                                    "message": {
                                        "content": "<think>hidden-reasoning</think>visible",
                                        "reasoning_content": "hidden-reasoning",
                                    },
                                    "finish_reason": "stop",
                                }
                            ]
                        },
                    )
                payload = json.loads(request.content)
                assert payload["max_tokens"] == 1
                return httpx.Response(
                    200,
                    json={"choices": [{"message": {"content": "O"}}]},
                )
            raise AssertionError(f"unexpected request: {request.method} {request.url.path}")

        known_hosts = Path(__file__).resolve()
        adapter = LmStudioAdapter(
            backend_id="remote-lmstudio",
            base_url="https://lmstudio.invalid",
            probe_model_id="model-a",
            ssh_target="node.invalid",
            known_hosts_file=known_hosts,
            platform=LmsPlatform.MACOS,
            process_runner=runner,
            transport=httpx.MockTransport(handler),
        )
        return ContractHarness(adapter=adapter)
