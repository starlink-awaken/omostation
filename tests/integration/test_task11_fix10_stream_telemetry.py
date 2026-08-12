from __future__ import annotations

import asyncio
import sqlite3
import tempfile
from collections import deque
from collections.abc import AsyncIterator, Iterator
from pathlib import Path
from typing import cast

import httpx
import pytest

from omlxc.config import (
    AppConfig,
    BackendConfig,
    DaemonConfig,
    ModelConfig,
    NodeConfig,
    PlacementConfig,
    StorageConfig,
)
from omlxc.daemon import DaemonServer, build_production_daemon
from omlxc.domain import BackendKind
from omlxc.domain.protocols import (
    AdapterError,
    AdapterErrorCode,
    BackendAdapter,
    ChatRequest,
    ChatResult,
    EmbeddingRequest,
    EmbeddingResult,
    OperationStatus,
    StreamEvent,
    StreamEventKind,
    StreamPhase,
)
from omlxc.scheduler import PlacementSnapshot
from omlxc.storage import SQLiteRuntimeStore


@pytest.fixture
def short_root() -> Iterator[Path]:
    with tempfile.TemporaryDirectory(prefix="omlxc-fix10-") as directory:
        yield Path(directory)


class ClosingStream(AsyncIterator[StreamEvent]):
    def __init__(self, request_id: str, *, block_after_content: bool) -> None:
        self._events = deque(
            [
                StreamEvent(
                    kind=StreamEventKind.CONTENT,
                    request_id=request_id,
                    content="ok",
                    emitted_content=True,
                    phase=StreamPhase.AFTER_CONTENT,
                ),
                *(
                    []
                    if block_after_content
                    else [
                        StreamEvent(
                            kind=StreamEventKind.DONE,
                            request_id=request_id,
                            emitted_content=True,
                            phase=StreamPhase.COMPLETE,
                        )
                    ]
                ),
            ]
        )
        self._block_after_content = block_after_content
        self._release = asyncio.Event()
        self.closed = asyncio.Event()
        self.close_calls = 0
        self.concurrent_close = False
        self.running = False

    def __aiter__(self) -> ClosingStream:
        return self

    async def __anext__(self) -> StreamEvent:
        self.running = True
        try:
            if self._events:
                return self._events.popleft()
            if self._block_after_content:
                await self._release.wait()
            raise StopAsyncIteration
        finally:
            self.running = False

    async def aclose(self) -> None:
        self.close_calls += 1
        self.concurrent_close = self.concurrent_close or self.running
        self._release.set()
        self.closed.set()


class SourceOwnerProbe(AsyncIterator[StreamEvent]):
    def __init__(self, source: AsyncIterator[StreamEvent]) -> None:
        self._source = source
        self.close_calls = 0
        self.concurrent_close = False
        self.running = False

    def __aiter__(self) -> SourceOwnerProbe:
        return self

    async def __anext__(self) -> StreamEvent:
        self.running = True
        try:
            return await anext(self._source)
        finally:
            self.running = False

    async def aclose(self) -> None:
        self.close_calls += 1
        self.concurrent_close = self.concurrent_close or self.running
        close = getattr(self._source, "aclose", None)
        if close is not None:
            await close()


class ProductionBackend:
    def __init__(self) -> None:
        self.stream_modes: deque[bool] = deque()
        self.streams: list[ClosingStream] = []
        self.chat_calls = 0
        self.embed_calls = 0

    async def chat(self, request: ChatRequest) -> ChatResult:
        self.chat_calls += 1
        content = cast(str, request.messages[-1].content)
        if content == "fail-secret-prompt":
            return ChatResult(
                request_id=request.request_id,
                success=False,
                error=AdapterError(
                    code=AdapterErrorCode.UNREACHABLE,
                    message="Authorization: Bearer never-persist-this-secret",
                ),
            )
        return ChatResult(request_id=request.request_id, success=True, content="answer")

    async def embed(self, request: EmbeddingRequest) -> EmbeddingResult:
        self.embed_calls += 1
        count = 1 if isinstance(request.input, str) else len(request.input)
        return EmbeddingResult(
            request_id=request.request_id,
            status=OperationStatus.SUCCEEDED,
            embeddings=tuple((1.0, 2.0) for _ in range(count)),
        )

    def stream_chat(self, request: ChatRequest) -> AsyncIterator[StreamEvent]:
        stream = ClosingStream(
            request.request_id,
            block_after_content=self.stream_modes.popleft() if self.stream_modes else False,
        )
        self.streams.append(stream)
        return stream

    async def aclose(self) -> None:
        return None


def _config(root: Path) -> AppConfig:
    return AppConfig(
        daemon=DaemonConfig(socket_path=root / "daemon.sock", probe_interval_seconds=60),
        storage=StorageConfig(database_path=root / "state.db"),
        nodes=(
            NodeConfig(
                id="node",
                display_name="Node",
                platform="macos",
                memory_gb=16,
            ),
        ),
        backends=(
            BackendConfig(
                id="backend",
                node_id="node",
                kind=BackendKind.OMLX_APP,
                base_url="http://127.0.0.1:8000",
            ),
        ),
        models=(ModelConfig(id="local/model", category="llm", role="chat", engine="omlx"),),
        placements=(
            PlacementConfig(
                id="placement",
                model_id="local/model",
                backend_id="backend",
                backend_model_id="physical/model",
                context_limit=8192,
                memory_gb=2,
            ),
        ),
    )


def _snapshot() -> PlacementSnapshot:
    return PlacementSnapshot(
        placement_id="placement",
        model_id="local/model",
        backend_id="backend",
        backend_model_id="physical/model",
        node_id="node",
        fresh=True,
        available=True,
        authorized=True,
        capabilities=frozenset({"chat", "streaming", "embedding"}),
        context_limit=8192,
        memory_admitted=True,
        loaded=True,
        ttft_ms=1,
        throughput_tps=10,
        queue_depth=0,
        error_rate=0,
        network_cost_ms=0,
        affinity=1,
        available_concurrency=1,
        local=True,
        security_allowed=True,
    )


async def _client(socket_path: Path) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        transport=httpx.AsyncHTTPTransport(uds=str(socket_path)),
        base_url="http://omlxc",
        timeout=1,
    )


def _chat_body(*, stream: bool, content: str = "hello") -> dict[str, object]:
    return {
        "model": "local/model",
        "messages": [{"role": "user", "content": content}],
        "stream": stream,
        "timeout_seconds": 0.5,
    }


@pytest.mark.asyncio
async def test_production_stream_owner_closes_once_and_releases_capacity_after_done_and_disconnect(
    short_root: Path,
) -> None:
    config = _config(short_root)
    backend = ProductionBackend()
    backend.stream_modes.extend((False, True))
    composition = build_production_daemon(
        config,
        adapters={"backend": cast(BackendAdapter, backend)},
        snapshots=(_snapshot(),),
    )
    probes: list[SourceOwnerProbe] = []
    original_stream = composition.inference.stream_chat

    def tracked_stream(*args: object, **kwargs: object) -> AsyncIterator[StreamEvent]:
        probe = SourceOwnerProbe(original_stream(*args, **kwargs))  # type: ignore[arg-type]
        probes.append(probe)
        return probe

    composition.inference.stream_chat = tracked_stream  # type: ignore[method-assign]
    loop = asyncio.get_running_loop()
    original_handler = loop.get_exception_handler()
    loop_errors: list[dict[str, object]] = []
    loop.set_exception_handler(lambda _loop, context: loop_errors.append(dict(context)))
    server = DaemonServer(composition.app, socket_path=config.daemon.socket_path)
    await server.start()
    try:
        async with await _client(config.daemon.socket_path) as client:
            complete = await client.post(
                "/openai/v1/chat/completions",
                headers={"X-OMLXC-Request-ID": "fix10.done"},
                json=_chat_body(stream=True),
            )
            after_done = await client.post(
                "/openai/v1/chat/completions",
                headers={"X-OMLXC-Request-ID": "fix10.after-done"},
                json=_chat_body(stream=False),
            )
            async with client.stream(
                "POST",
                "/openai/v1/chat/completions",
                headers={"X-OMLXC-Request-ID": "fix10.cancel"},
                json=_chat_body(stream=True),
            ) as response:
                assert response.status_code == 200
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        break
            await asyncio.wait_for(backend.streams[-1].closed.wait(), timeout=0.5)
            after_cancel = await client.post(
                "/openai/v1/chat/completions",
                headers={"X-OMLXC-Request-ID": "fix10.after-cancel"},
                json=_chat_body(stream=False),
            )
        await asyncio.sleep(0)
        assert complete.status_code == after_done.status_code == after_cancel.status_code == 200
        assert [probe.close_calls for probe in probes] == [1, 1]
        assert not any(probe.concurrent_close for probe in probes)
        assert [stream.close_calls for stream in backend.streams] == [1, 1]
        assert not any(stream.concurrent_close for stream in backend.streams)
        assert loop_errors == []
        assert backend.chat_calls == 2
    finally:
        await server.stop()
        loop.set_exception_handler(original_handler)

    assert composition.runtime.task_settled
    with sqlite3.connect(config.storage.database_path) as connection:
        terminal = connection.execute(
            "SELECT request_id, success FROM request_metrics ORDER BY sequence"
        ).fetchall()
        route_ids = connection.execute(
            "SELECT request_id FROM route_audits ORDER BY sequence"
        ).fetchall()
    assert terminal == [
        ("fix10.done", 1),
        ("fix10.after-done", 1),
        ("fix10.cancel", 0),
        ("fix10.after-cancel", 1),
    ]
    assert route_ids == [
        ("fix10.done",),
        ("fix10.after-done",),
        ("fix10.cancel",),
        ("fix10.after-cancel",),
    ]


@pytest.mark.asyncio
async def test_production_chat_embed_stream_and_error_telemetry_is_restart_safe_and_redacted(
    short_root: Path,
) -> None:
    config = _config(short_root)
    backend = ProductionBackend()
    composition = build_production_daemon(
        config,
        adapters={"backend": cast(BackendAdapter, backend)},
        snapshots=(_snapshot(),),
    )
    server = DaemonServer(composition.app, socket_path=config.daemon.socket_path)
    await server.start()
    try:
        async with await _client(config.daemon.socket_path) as client:
            chat = await client.post(
                "/openai/v1/chat/completions",
                headers={
                    "Authorization": "Bearer request-identity-never-persist",
                    "X-OMLXC-Request-ID": "fix10.chat",
                    "X-User-ID": "private-user-identity",
                },
                json=_chat_body(stream=False, content="private-chat-body"),
            )
            embedding = await client.post(
                "/openai/v1/embeddings",
                headers={"X-OMLXC-Request-ID": "fix10.embed"},
                json={"model": "local/model", "input": "private-embedding-body"},
            )
            stream = await client.post(
                "/openai/v1/chat/completions",
                headers={"X-OMLXC-Request-ID": "fix10.stream"},
                json=_chat_body(stream=True, content="private-stream-body"),
            )
            failed = await client.post(
                "/openai/v1/chat/completions",
                headers={"X-OMLXC-Request-ID": "fix10.error"},
                json=_chat_body(stream=False, content="fail-secret-prompt"),
            )
        assert chat.status_code == embedding.status_code == stream.status_code == 200
        assert failed.status_code == 503
    finally:
        await server.stop()

    assert composition.runtime.task_settled
    async with await SQLiteRuntimeStore.open(config.storage.database_path) as reopened:
        audits = await reopened.list_route_audits(after_sequence=0)
        metric_count = await reopened.metric_count()
    assert [audit.request_id for audit in audits] == [
        "fix10.chat",
        "fix10.embed",
        "fix10.stream",
        "fix10.error",
    ]
    assert metric_count == 4
    with sqlite3.connect(config.storage.database_path) as connection:
        terminal = connection.execute(
            "SELECT request_id, success FROM request_metrics ORDER BY sequence"
        ).fetchall()
    assert terminal == [
        ("fix10.chat", 1),
        ("fix10.embed", 1),
        ("fix10.stream", 1),
        ("fix10.error", 0),
    ]
    persisted = config.storage.database_path.read_bytes()
    for secret in (
        b"private-chat-body",
        b"private-embedding-body",
        b"private-stream-body",
        b"fail-secret-prompt",
        b"never-persist-this-secret",
        b"request-identity-never-persist",
        b"private-user-identity",
        b"http://127.0.0.1:8000",
    ):
        assert secret not in persisted
