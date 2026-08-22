"""Run the shared backend contract against LM Studio / LM Link."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from pathlib import Path

import httpx
import pytest

from omlxc.adapters.lmstudio import (
    LmsLoadOptions,
    LmsPlatform,
    LmStudioAdapter,
    ProcessOutput,
)
from omlxc.domain.protocols import ChatMessage, ChatRequest

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
                        stream=BrokenSSEStream(b'data: {"choices":[{"delta":{"content":"hello"}}]}\n\n'),
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
                # 预算必须覆盖 reasoning 模型的思维链前缀 (1 token 时 content
                # 必空 → generation_ready 永假的线上 bug, 2026-08-20 实测)
                assert payload["max_tokens"] == 100
                return httpx.Response(
                    200,
                    json={
                        "choices": [
                            {
                                "message": {
                                    "content": "<think>user asked for O, I should just comply</think>O",
                                    "reasoning_content": "user asked for O, I should just comply",
                                },
                                "finish_reason": "stop",
                            }
                        ]
                    },
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

    @pytest.mark.asyncio
    async def test_chat_loads_unloaded_model_via_controlled_lms_load_not_jit(self) -> None:
        """stale-loaded 竞态回归: discover 过且模型未加载时, chat 必须先走
        SSH 受控 lms load (带 -c), 禁止裸 HTTP 触发 LM Studio JIT (按全局
        defaultContextLength 失控加载, 2026-08-22 实测打穿内存)。"""
        calls: list[tuple[str, ...]] = []
        load_state = {"loaded": False}

        async def runner(argv: tuple[str, ...], timeout: float) -> ProcessOutput:
            del timeout
            calls.append(argv)
            if "ps" in argv:  # lms ps --json
                rows = [{"modelKey": "model-a", "identifier": "model-a"}] if load_state["loaded"] else []
                return ProcessOutput(returncode=0, stdout=json.dumps(rows), stderr="")
            if "load" in argv:  # 受控加载
                load_state["loaded"] = True
                return ProcessOutput(returncode=0, stdout="loaded", stderr="")
            raise AssertionError(f"unexpected argv: {argv}")

        async def handler(request: httpx.Request) -> httpx.Response:
            if request.url.path == "/v1/models":
                return httpx.Response(200, json={"data": [{"id": "model-a"}]})
            if request.url.path == "/v1/chat/completions":
                return httpx.Response(200, json={"choices": [{"message": {"content": "O"}, "finish_reason": "stop"}]})
            raise AssertionError(f"unexpected request: {request.url.path}")

        adapter = LmStudioAdapter(
            backend_id="remote-lmstudio",
            base_url="https://lmstudio.invalid",
            ssh_target="node.invalid",
            known_hosts_file=Path(__file__).resolve(),
            platform=LmsPlatform.MACOS,
            load_options=LmsLoadOptions(context_length=16384),
            process_runner=runner,
            transport=httpx.MockTransport(handler),
        )
        # 先 discover: 目录有模型、均未加载 → 缓存有效且 loaded 集为空
        snapshot = await adapter.discover()
        assert snapshot.model_available is True
        assert adapter._loaded_cache_valid is True

        result = await adapter.chat(
            ChatRequest(
                request_id="req-guard",
                model="model-a",
                messages=(ChatMessage(role="user", content="Reply O only"),),
            )
        )
        assert result.success is True
        load_calls = [c for c in calls if "load" in c]
        assert len(load_calls) == 1, "chat 前必须恰好触发一次受控 lms load"
        argv = load_calls[0]
        assert "-c" in argv and "16384" in argv, f"受控加载必须带 -c 16384: {argv}"
