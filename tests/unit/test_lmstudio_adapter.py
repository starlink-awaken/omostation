"""Security, HTTP, and argv contracts for the LM Studio adapter."""

from __future__ import annotations

import asyncio
import json
import os
from collections.abc import Coroutine
from pathlib import Path
from typing import Any

import httpx
import pytest

import omlxc.adapters.lmstudio as lmstudio_module
from omlxc.adapters.lmstudio import (
    LmsLoadOptions,
    LmsPlatform,
    LmStudioAdapter,
    ProcessOutput,
)
from omlxc.domain.protocols import (
    AdapterErrorCode,
    BackendAdapter,
    ChatMessage,
    ChatRequest,
    EmbeddingRequest,
    ModelRuntimeState,
    OperationStatus,
    StreamEventKind,
    TuneRequest,
    TuneScope,
    TuneSettings,
)


class FakeAsyncReader:
    def __init__(self, chunks: list[bytes], *, block: bool = False) -> None:
        self._chunks = chunks
        self._block = block
        self.cancelled = False
        self.started = asyncio.Event()

    async def read(self, size: int = -1) -> bytes:
        del size
        self.started.set()
        if self._block:
            try:
                await asyncio.Event().wait()
            except asyncio.CancelledError:
                self.cancelled = True
                raise
        return self._chunks.pop(0) if self._chunks else b""


class FakeBoundedProcess:
    def __init__(self, stdout: FakeAsyncReader, stderr: FakeAsyncReader) -> None:
        self.stdout = stdout
        self.stderr = stderr
        self.returncode: int | None = None
        self.killed = False
        self.wait_count = 0

    def kill(self) -> None:
        self.killed = True
        self.returncode = -9

    async def wait(self) -> int:
        self.wait_count += 1
        if self.returncode is None:
            self.returncode = 0
        return self.returncode


class FakeExplodingReader(FakeAsyncReader):
    def __init__(self, failure: Exception) -> None:
        super().__init__([])
        self._failure = failure

    async def read(self, size: int = -1) -> bytes:
        del size
        self.started.set()
        raise self._failure


class FakeRunningProcess(FakeBoundedProcess):
    def __init__(self, stdout: FakeAsyncReader, stderr: FakeAsyncReader) -> None:
        super().__init__(stdout, stderr)
        self._released = asyncio.Event()

    def kill(self) -> None:
        super().kill()
        self._released.set()

    async def wait(self) -> int:
        self.wait_count += 1
        await self._released.wait()
        return self.returncode or 0


def _known_hosts(tmp_path: Path) -> Path:
    path = tmp_path / "known_hosts"
    path.write_text("node.invalid ssh-ed25519 AAAATEST\n", encoding="utf-8")
    path.chmod(0o600)
    return path


def _models_transport(
    *, chat_content: str = "visible", model_id: str = "model-a"
) -> httpx.MockTransport:
    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v1/models":
            return httpx.Response(200, json={"data": [{"id": model_id}]})
        if request.url.path == "/v1/chat/completions":
            return httpx.Response(
                200,
                json={"choices": [{"message": {"content": chat_content}}]},
            )
        raise AssertionError(request.url.path)

    return httpx.MockTransport(handler)


@pytest.mark.parametrize(
    "url",
    [
        "ssh://node.invalid:1234",
        "http://user:secret@node.invalid:1234",
        "http://node.invalid:1234/#fragment",
        "http://node.invalid:1234/v1",
        "http://node.invalid:1234/?proxy=yes",
    ],
)
def test_http_endpoint_rejects_ambiguous_or_credentialed_urls(url: str) -> None:
    with pytest.raises(ValueError):
        LmStudioAdapter(backend_id="lm", base_url=url)


@pytest.mark.parametrize(
    "target",
    ["-bad", "host:22", "user@host;id", "user@@host", "host name", "user@"],
)
def test_ssh_target_rejects_option_port_and_command_injection(tmp_path: Path, target: str) -> None:
    with pytest.raises(ValueError, match="target"):
        LmStudioAdapter(
            backend_id="lm",
            base_url="http://node.invalid:1234",
            ssh_target=target,
            known_hosts_file=_known_hosts(tmp_path),
        )


@pytest.mark.parametrize(
    "model_id",
    ["-model", "model name", "model\nname", "../model", "model/../other", "model;id"],
)
@pytest.mark.asyncio
async def test_model_identifier_rejects_shell_option_and_traversal(
    tmp_path: Path, model_id: str
) -> None:
    adapter = LmStudioAdapter(
        backend_id="lm",
        base_url="http://node.invalid:1234",
        ssh_target="node.invalid",
        known_hosts_file=_known_hosts(tmp_path),
        transport=_models_transport(),
    )

    result = await adapter.load_model(model_id)

    assert result.status is OperationStatus.FAILED
    assert result.error is not None
    assert result.error.code is AdapterErrorCode.INVALID_REQUEST


def test_known_hosts_must_be_absolute_regular_and_private(tmp_path: Path) -> None:
    relative = Path("known_hosts")
    with pytest.raises(ValueError, match="known_hosts"):
        LmStudioAdapter(
            backend_id="lm",
            base_url="http://node.invalid:1234",
            ssh_target="node.invalid",
            known_hosts_file=relative,
        )

    missing = (tmp_path / "missing-known-hosts").absolute()
    with pytest.raises(ValueError, match="exist"):
        LmStudioAdapter(
            backend_id="lm",
            base_url="http://node.invalid:1234",
            ssh_target="node.invalid",
            known_hosts_file=missing,
        )

    symlink = tmp_path / "known-hosts-link"
    symlink.symlink_to(_known_hosts(tmp_path))
    with pytest.raises(ValueError, match="regular"):
        LmStudioAdapter(
            backend_id="lm",
            base_url="http://node.invalid:1234",
            ssh_target="node.invalid",
            known_hosts_file=symlink,
        )

    directory = tmp_path / "directory"
    directory.mkdir()
    with pytest.raises(ValueError, match="known_hosts"):
        LmStudioAdapter(
            backend_id="lm",
            base_url="http://node.invalid:1234",
            ssh_target="node.invalid",
            known_hosts_file=directory,
        )

    writable = _known_hosts(tmp_path)
    writable.chmod(0o622)
    with pytest.raises(ValueError, match="permissions"):
        LmStudioAdapter(
            backend_id="lm",
            base_url="http://node.invalid:1234",
            ssh_target="node.invalid",
            known_hosts_file=writable,
        )


def test_known_hosts_requires_current_owner_and_private_parent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    owned = _known_hosts(tmp_path)
    monkeypatch.setattr(os, "geteuid", lambda: os.stat(owned).st_uid + 1)
    with pytest.raises(ValueError, match="owner"):
        LmStudioAdapter(
            backend_id="lm",
            base_url="http://node.invalid:1234",
            ssh_target="node.invalid",
            known_hosts_file=owned,
        )

    monkeypatch.undo()
    writable_parent = tmp_path / "writable-parent"
    writable_parent.mkdir(mode=0o700)
    parent_hosts = _known_hosts(writable_parent)
    writable_parent.chmod(0o770)
    with pytest.raises(ValueError, match="parent"):
        LmStudioAdapter(
            backend_id="lm",
            base_url="http://node.invalid:1234",
            ssh_target="node.invalid",
            known_hosts_file=parent_hosts,
        )


def test_known_hosts_rejects_symlink_in_any_path_component(tmp_path: Path) -> None:
    real_parent = tmp_path / "real-parent"
    real_parent.mkdir(mode=0o700)
    _known_hosts(real_parent)
    linked_parent = tmp_path / "linked-parent"
    linked_parent.symlink_to(real_parent, target_is_directory=True)

    with pytest.raises(ValueError, match="symlink"):
        LmStudioAdapter(
            backend_id="lm",
            base_url="http://node.invalid:1234",
            ssh_target="node.invalid",
            known_hosts_file=(linked_parent / "known_hosts").absolute(),
        )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("platform", "executable"),
    [(LmsPlatform.MACOS, "lms"), (LmsPlatform.WINDOWS, "lms.exe")],
)
async def test_ps_uses_exact_hardened_ssh_argv(
    tmp_path: Path, platform: LmsPlatform, executable: str
) -> None:
    calls: list[tuple[tuple[str, ...], float]] = []

    async def runner(argv: tuple[str, ...], timeout: float) -> ProcessOutput:
        calls.append((argv, timeout))
        return ProcessOutput(returncode=0, stdout="[]", stderr="")

    known_hosts = _known_hosts(tmp_path)
    adapter = LmStudioAdapter(
        backend_id="lm",
        base_url="http://node.invalid:1234",
        ssh_target="operator@node.invalid",
        known_hosts_file=known_hosts,
        platform=platform,
        process_runner=runner,
        transport=_models_transport(),
    )

    await adapter.list_models()

    assert calls == [
        (
            (
                "ssh",
                "-T",
                "-o",
                "BatchMode=yes",
                "-o",
                "StrictHostKeyChecking=yes",
                "-o",
                "IdentitiesOnly=yes",
                "-o",
                f"UserKnownHostsFile={known_hosts}",
                "-o",
                "GlobalKnownHostsFile=/dev/null",
                "-o",
                "ConnectTimeout=7",
                "-o",
                "ServerAliveInterval=5",
                "-o",
                "ServerAliveCountMax=2",
                "--",
                "operator@node.invalid",
                executable,
                "ps",
                "--json",
            ),
            15.0,
        )
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize("stdout", ["", "not-json", '{"half":'])
async def test_bad_ps_output_preserves_unknown_runtime_state(tmp_path: Path, stdout: str) -> None:
    async def runner(argv: tuple[str, ...], timeout: float) -> ProcessOutput:
        del argv, timeout
        return ProcessOutput(returncode=0, stdout=stdout, stderr="secret remote output")

    adapter = LmStudioAdapter(
        backend_id="lm",
        base_url="http://node.invalid:1234",
        ssh_target="node.invalid",
        known_hosts_file=_known_hosts(tmp_path),
        process_runner=runner,
        transport=_models_transport(),
    )

    models = await adapter.list_models()

    assert models[0].state is ModelRuntimeState.UNKNOWN
    assert models[0].loaded is None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "payload",
    [
        [{"modelKey": "model-a", "identifier": "model-a"}],
        {"models": [{"modelKey": "model-a", "identifier": "model-a"}]},
        {"data": [{"modelKey": "model-a", "identifier": "model-a"}]},
    ],
)
async def test_ps_accepts_list_and_single_allowlisted_wrapper(
    tmp_path: Path, payload: object
) -> None:
    async def runner(argv: tuple[str, ...], timeout: float) -> ProcessOutput:
        del argv, timeout
        return ProcessOutput(0, json.dumps(payload), "")

    adapter = LmStudioAdapter(
        backend_id="lm",
        base_url="http://node.invalid:1234",
        ssh_target="node.invalid",
        known_hosts_file=_known_hosts(tmp_path),
        process_runner=runner,
        transport=_models_transport(),
    )

    models = await adapter.list_models()

    assert [(model.id, model.loaded) for model in models] == [("model-a", True)]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "payload",
    [
        {"models": [], "data": []},
        {"items": []},
        {"models": {}},
        {"data": None},
    ],
)
async def test_ps_rejects_ambiguous_unknown_or_nonlist_wrapper(
    tmp_path: Path, payload: object
) -> None:
    async def runner(argv: tuple[str, ...], timeout: float) -> ProcessOutput:
        del argv, timeout
        return ProcessOutput(0, json.dumps(payload), "")

    adapter = LmStudioAdapter(
        backend_id="lm",
        base_url="http://node.invalid:1234",
        ssh_target="node.invalid",
        known_hosts_file=_known_hosts(tmp_path),
        process_runner=runner,
        transport=_models_transport(),
    )

    models = await adapter.list_models()

    assert models[0].state is ModelRuntimeState.UNKNOWN
    assert models[0].loaded is None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "payload",
    [
        [
            {"modelKey": "model-a", "identifier": "resident-a"},
            {"modelKey": "model-a", "identifier": "resident-b"},
        ],
        [
            {"modelKey": "model-a", "identifier": "shared-alias"},
            {"modelKey": "shared-alias", "identifier": "resident-b"},
        ],
    ],
)
async def test_control_identity_collision_fails_closed_and_blocks_lifecycle_write(
    tmp_path: Path, payload: object
) -> None:
    calls: list[tuple[str, ...]] = []

    async def runner(argv: tuple[str, ...], timeout: float) -> ProcessOutput:
        del timeout
        calls.append(argv)
        return ProcessOutput(0, json.dumps(payload), "")

    adapter = LmStudioAdapter(
        backend_id="lm",
        base_url="http://node.invalid:1234",
        ssh_target="node.invalid",
        known_hosts_file=_known_hosts(tmp_path),
        process_runner=runner,
        transport=_models_transport(),
    )

    models = await adapter.list_models()
    result = await adapter.unload_model("model-a")

    assert all(model.state is ModelRuntimeState.UNKNOWN for model in models)
    assert all(model.loaded is None for model in models)
    assert result.status is OperationStatus.FAILED
    assert all(call[-3:] == ("lms", "ps", "--json") for call in calls)


@pytest.mark.asyncio
async def test_control_row_matching_two_http_ids_fails_closed_and_blocks_write(
    tmp_path: Path,
) -> None:
    calls: list[tuple[str, ...]] = []

    async def runner(argv: tuple[str, ...], timeout: float) -> ProcessOutput:
        del timeout
        calls.append(argv)
        return ProcessOutput(
            0,
            '[{"modelKey":"model-a","identifier":"resident-a"}]',
            "",
        )

    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/models"
        return httpx.Response(
            200,
            json={"data": [{"id": "model-a"}, {"id": "resident-a"}]},
        )

    adapter = LmStudioAdapter(
        backend_id="lm",
        base_url="http://node.invalid:1234",
        ssh_target="node.invalid",
        known_hosts_file=_known_hosts(tmp_path),
        process_runner=runner,
        transport=httpx.MockTransport(handler),
    )

    models = await adapter.list_models()
    result = await adapter.unload_model("model-a")

    assert {model.id for model in models} == {"model-a", "resident-a"}
    assert all(model.state is ModelRuntimeState.UNKNOWN for model in models)
    assert all(model.loaded is None for model in models)
    assert result.status is OperationStatus.FAILED
    assert all(call[-3:] == ("lms", "ps", "--json") for call in calls)


@pytest.mark.asyncio
async def test_missing_control_channel_preserves_unknown_and_blocks_load() -> None:
    adapter = LmStudioAdapter(
        backend_id="lm",
        base_url="http://node.invalid:1234",
        transport=_models_transport(),
    )

    models = await adapter.list_models()
    result = await adapter.load_model("model-a")

    assert models[0].loaded is None
    assert result.status is OperationStatus.FAILED
    assert result.error is not None
    assert result.error.code is AdapterErrorCode.UNSUPPORTED


@pytest.mark.asyncio
async def test_unsupported_lms_cli_is_typed_but_unknown_lifecycle_still_fails(
    tmp_path: Path,
) -> None:
    async def runner(argv: tuple[str, ...], timeout: float) -> ProcessOutput:
        del argv, timeout
        return ProcessOutput(2, "", "unknown option --json remote-secret")

    adapter = LmStudioAdapter(
        backend_id="lm",
        base_url="http://node.invalid:1234",
        ssh_target="node.invalid",
        known_hosts_file=_known_hosts(tmp_path),
        process_runner=runner,
        transport=_models_transport(),
    )

    models = await adapter.list_models()
    result = await adapter.load_model("model-a")

    assert models[0].state is ModelRuntimeState.UNKNOWN
    assert result.status is OperationStatus.FAILED
    assert result.error is not None
    assert result.error.code is AdapterErrorCode.UNSUPPORTED
    assert "remote-secret" not in result.model_dump_json()


@pytest.mark.asyncio
async def test_load_uses_typed_options_then_verifies_runtime_state(tmp_path: Path) -> None:
    calls: list[tuple[str, ...]] = []
    outputs = iter(
        [
            ProcessOutput(returncode=0, stdout="[]", stderr=""),
            ProcessOutput(returncode=0, stdout="loaded", stderr=""),
            ProcessOutput(
                returncode=0,
                stdout='[{"modelKey":"model-a","identifier":"resident-a"}]',
                stderr="",
            ),
        ]
    )

    async def runner(argv: tuple[str, ...], timeout: float) -> ProcessOutput:
        del timeout
        calls.append(argv)
        return next(outputs)

    adapter = LmStudioAdapter(
        backend_id="lm",
        base_url="http://node.invalid:1234",
        ssh_target="node.invalid",
        known_hosts_file=_known_hosts(tmp_path),
        process_runner=runner,
        load_options=LmsLoadOptions(
            context_length=32768,
            parallel=2,
            ttl_seconds=3600,
            identifier="resident-a",
            yes=True,
        ),
        transport=_models_transport(),
    )

    result = await adapter.load_model("model-a", idempotency_key="idem-a")

    assert result.status is OperationStatus.SUCCEEDED
    assert result.changed is True
    assert calls[1][-12:] == (
        "lms",
        "load",
        "model-a",
        "-c",
        "32768",
        "--parallel",
        "2",
        "--ttl",
        "3600",
        "--identifier",
        "resident-a",
        "-y",
    )


@pytest.mark.asyncio
async def test_unload_windows_layout_and_postcondition_mismatch_fails(tmp_path: Path) -> None:
    calls: list[tuple[str, ...]] = []
    loaded = '[{"modelKey":"model-a","identifier":"resident-a"}]'
    outputs = iter(
        [
            ProcessOutput(0, loaded, ""),
            ProcessOutput(0, "unloaded", ""),
            ProcessOutput(0, loaded, ""),
        ]
    )

    async def runner(argv: tuple[str, ...], timeout: float) -> ProcessOutput:
        del timeout
        calls.append(argv)
        return next(outputs)

    adapter = LmStudioAdapter(
        backend_id="lm",
        base_url="http://node.invalid:1234",
        ssh_target="node.invalid",
        known_hosts_file=_known_hosts(tmp_path),
        platform=LmsPlatform.WINDOWS,
        process_runner=runner,
        transport=_models_transport(),
    )

    result = await adapter.unload_model("model-a")

    assert calls[1][-3:] == ("lms.exe", "unload", "resident-a")
    assert result.status is OperationStatus.FAILED
    assert result.error is not None
    assert result.error.code is AdapterErrorCode.BAD_RESPONSE


@pytest.mark.asyncio
async def test_nonzero_and_timeout_are_typed_without_remote_output_leak(tmp_path: Path) -> None:
    secret = "token=remote-secret /Users/private/models/model.gguf"

    async def nonzero(argv: tuple[str, ...], timeout: float) -> ProcessOutput:
        del argv, timeout
        return ProcessOutput(returncode=255, stdout=secret, stderr=secret)

    adapter = LmStudioAdapter(
        backend_id="lm",
        base_url="http://node.invalid:1234",
        ssh_target="node.invalid",
        known_hosts_file=_known_hosts(tmp_path),
        process_runner=nonzero,
        transport=_models_transport(),
    )
    result = await adapter.load_model("model-a")
    serialized = result.model_dump_json()
    assert result.error is not None
    assert secret not in serialized
    assert "remote-secret" not in serialized
    assert "/Users/private" not in serialized

    async def timeout(argv: tuple[str, ...], timeout: float) -> ProcessOutput:
        del argv, timeout
        raise TimeoutError(secret)

    timed = LmStudioAdapter(
        backend_id="lm",
        base_url="http://node.invalid:1234",
        ssh_target="node.invalid",
        known_hosts_file=_known_hosts(tmp_path),
        process_runner=timeout,
        transport=_models_transport(),
    )
    timed_result = await timed.load_model("model-a")
    assert timed_result.error is not None
    assert timed_result.error.code is AdapterErrorCode.TIMEOUT
    assert "remote-secret" not in timed_result.model_dump_json()


@pytest.mark.asyncio
async def test_cancellation_propagates_from_process_runner(tmp_path: Path) -> None:
    async def cancelled(argv: tuple[str, ...], timeout: float) -> ProcessOutput:
        del argv, timeout
        raise asyncio.CancelledError

    adapter = LmStudioAdapter(
        backend_id="lm",
        base_url="http://node.invalid:1234",
        ssh_target="node.invalid",
        known_hosts_file=_known_hosts(tmp_path),
        process_runner=cancelled,
        transport=_models_transport(),
    )

    with pytest.raises(asyncio.CancelledError):
        await adapter.list_models()


@pytest.mark.asyncio
async def test_http_chat_uses_only_openai_compatible_fields_and_filters_reasoning() -> None:
    requests: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": "<think>secret</think>visible",
                            "reasoning_content": "secret",
                        }
                    }
                ]
            },
        )

    adapter = LmStudioAdapter(
        backend_id="lm",
        base_url="https://node.invalid:1234",
        transport=httpx.MockTransport(handler),
    )
    assert isinstance(adapter, BackendAdapter)
    result = await adapter.chat(
        ChatRequest(
            request_id="req-a",
            model="model-a",
            messages=(ChatMessage(role="user", content="hello"),),
        )
    )

    payload = json.loads(requests[0].content)
    assert set(payload) == {"model", "messages", "max_tokens", "temperature", "stream"}
    assert result.content == "visible"
    assert "secret" not in result.model_dump_json()


@pytest.mark.asyncio
@pytest.mark.parametrize("content", ["", "<think>secret"])
async def test_chat_fails_closed_on_empty_or_unclosed_reasoning_content(content: str) -> None:
    adapter = LmStudioAdapter(
        backend_id="lm",
        base_url="https://node.invalid:1234",
        transport=_models_transport(chat_content=content),
    )

    result = await adapter.chat(
        ChatRequest(
            request_id="req-empty",
            model="model-a",
            messages=(ChatMessage(role="user", content="hello"),),
        )
    )

    assert result.success is False
    assert result.content == ""
    assert result.error is not None
    assert result.error.code is AdapterErrorCode.BAD_RESPONSE
    assert "secret" not in result.model_dump_json()


@pytest.mark.asyncio
async def test_stream_done_without_visible_content_fails_closed() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        del request
        return httpx.Response(200, content=b"data: [DONE]\n\n")

    adapter = LmStudioAdapter(
        backend_id="lm",
        base_url="https://node.invalid:1234",
        transport=httpx.MockTransport(handler),
    )
    request = ChatRequest(
        request_id="req-stream-empty",
        model="model-a",
        messages=(ChatMessage(role="user", content="hello"),),
    )

    events = [event async for event in adapter.stream_chat(request)]

    assert len(events) == 1
    assert events[0].kind.value == "error"
    assert events[0].error is not None
    assert events[0].error.code is AdapterErrorCode.BAD_RESPONSE


@pytest.mark.asyncio
async def test_stream_preserves_finish_reason_from_empty_terminal_frame() -> None:
    body = (
        'data: {"choices":[{"delta":{"content":"partial"}}]}\n\n'
        'data: {"usage":{"prompt_tokens":2,"completion_tokens":1,"total_tokens":3},'
        '"choices":[]}\n\n'
        'data: {"choices":[{"delta":{},"finish_reason":"length"}]}\n\n'
        "data: [DONE]\n\n"
    )
    adapter = LmStudioAdapter(
        backend_id="lm",
        base_url="https://node.invalid:1234",
        transport=httpx.MockTransport(lambda _request: httpx.Response(200, content=body)),
    )
    request = ChatRequest(
        request_id="req-stream-length",
        model="model-a",
        messages=(ChatMessage(role="user", content="hello"),),
    )

    events = [event async for event in adapter.stream_chat(request)]

    assert [event.kind for event in events] == [
        StreamEventKind.CONTENT,
        StreamEventKind.USAGE,
        StreamEventKind.DONE,
    ]
    assert events[-1].finish_reason == "length"


@pytest.mark.asyncio
async def test_tune_rejects_unknown_fields_without_running_control(tmp_path: Path) -> None:
    calls: list[tuple[str, ...]] = []

    async def runner(argv: tuple[str, ...], timeout: float) -> ProcessOutput:
        del timeout
        calls.append(argv)
        return ProcessOutput(0, "[]", "")

    adapter = LmStudioAdapter(
        backend_id="lm",
        base_url="http://node.invalid:1234",
        ssh_target="node.invalid",
        known_hosts_file=_known_hosts(tmp_path),
        process_runner=runner,
        transport=_models_transport(),
    )

    result = await adapter.tune(
        TuneRequest(
            scope=TuneScope.MODEL,
            model_id="model-a",
            settings=TuneSettings(temperature=0.3),
        )
    )

    assert result.status is OperationStatus.UNSUPPORTED
    assert calls == []


@pytest.mark.asyncio
async def test_tune_uses_confirmed_unload_load_and_verifies(tmp_path: Path) -> None:
    calls: list[tuple[str, ...]] = []
    current = (
        '[{"modelKey":"model-a","identifier":"model-a",'
        '"contextLength":4096,"parallel":2,"ttlMs":60000}]'
    )
    desired = (
        '[{"modelKey":"model-a","identifier":"model-a",'
        '"contextLength":8192,"parallel":2,"ttlMs":120000}]'
    )
    outputs = iter(
        [
            ProcessOutput(0, current, ""),
            ProcessOutput(0, "unloaded", ""),
            ProcessOutput(0, "[]", ""),
            ProcessOutput(0, "loaded", ""),
            ProcessOutput(0, desired, ""),
        ]
    )

    async def runner(argv: tuple[str, ...], timeout: float) -> ProcessOutput:
        del timeout
        calls.append(argv)
        return next(outputs)

    adapter = LmStudioAdapter(
        backend_id="lm",
        base_url="http://node.invalid:1234",
        ssh_target="node.invalid",
        known_hosts_file=_known_hosts(tmp_path),
        process_runner=runner,
        transport=_models_transport(),
    )

    result = await adapter.tune(
        TuneRequest(
            scope=TuneScope.MODEL,
            model_id="model-a",
            settings=TuneSettings(max_context_window=8192, ttl_seconds=120),
        )
    )

    assert result.status is OperationStatus.SUCCEEDED
    assert result.changed_fields == ("max_context_window", "ttl_seconds")
    assert calls[1][-3:] == ("lms", "unload", "model-a")
    assert calls[3][-12:] == (
        "lms",
        "load",
        "model-a",
        "-c",
        "8192",
        "--parallel",
        "2",
        "--ttl",
        "120",
        "--identifier",
        "model-a",
        "-y",
    )


@pytest.mark.asyncio
async def test_tune_uses_canonical_http_identifier_and_control_source(
    tmp_path: Path,
) -> None:
    calls: list[tuple[str, ...]] = []
    current = (
        '[{"modelKey":"source-model","identifier":"public-model",'
        '"contextLength":4096,"parallel":2,"ttlMs":60000}]'
    )
    desired = (
        '[{"modelKey":"source-model","identifier":"public-model",'
        '"contextLength":8192,"parallel":2,"ttlMs":60000}]'
    )
    outputs = iter(
        [
            ProcessOutput(0, current, ""),
            ProcessOutput(0, "unloaded", ""),
            ProcessOutput(0, "[]", ""),
            ProcessOutput(0, "loaded", ""),
            ProcessOutput(0, desired, ""),
        ]
    )

    async def runner(argv: tuple[str, ...], timeout: float) -> ProcessOutput:
        del timeout
        calls.append(argv)
        return next(outputs)

    adapter = LmStudioAdapter(
        backend_id="lm",
        base_url="http://node.invalid:1234",
        ssh_target="node.invalid",
        known_hosts_file=_known_hosts(tmp_path),
        process_runner=runner,
        transport=_models_transport(model_id="public-model"),
    )

    result = await adapter.tune(
        TuneRequest(
            scope=TuneScope.MODEL,
            model_id="public-model",
            settings=TuneSettings(max_context_window=8192),
        )
    )

    assert result.status is OperationStatus.SUCCEEDED
    assert result.changed_fields == ("max_context_window",)
    assert calls[1][-3:] == ("lms", "unload", "public-model")
    assert calls[3][-12:] == (
        "lms",
        "load",
        "source-model",
        "-c",
        "8192",
        "--parallel",
        "2",
        "--ttl",
        "60",
        "--identifier",
        "public-model",
        "-y",
    )


@pytest.mark.asyncio
async def test_tune_canonical_unload_verification_failure_does_not_load(
    tmp_path: Path,
) -> None:
    calls: list[tuple[str, ...]] = []
    current = (
        '[{"modelKey":"source-model","identifier":"public-model",'
        '"contextLength":4096,"parallel":2,"ttlMs":60000}]'
    )
    outputs = iter(
        [
            ProcessOutput(0, current, ""),
            ProcessOutput(0, "unloaded", ""),
            ProcessOutput(0, current, ""),
        ]
    )

    async def runner(argv: tuple[str, ...], timeout: float) -> ProcessOutput:
        del timeout
        calls.append(argv)
        return next(outputs)

    adapter = LmStudioAdapter(
        backend_id="lm",
        base_url="http://node.invalid:1234",
        ssh_target="node.invalid",
        known_hosts_file=_known_hosts(tmp_path),
        process_runner=runner,
        transport=_models_transport(model_id="public-model"),
    )

    result = await adapter.tune(
        TuneRequest(
            scope=TuneScope.MODEL,
            model_id="public-model",
            settings=TuneSettings(max_context_window=8192),
        )
    )

    assert result.status is OperationStatus.FAILED
    assert result.error is not None
    assert result.error.code is AdapterErrorCode.BAD_RESPONSE
    assert len(calls) == 3
    assert calls[1][-3:] == ("lms", "unload", "public-model")
    assert all("load" not in call[-11:] for call in calls)


@pytest.mark.asyncio
async def test_tune_canonical_load_verification_failure_is_partial(
    tmp_path: Path,
) -> None:
    calls: list[tuple[str, ...]] = []
    current = (
        '[{"modelKey":"source-model","identifier":"public-model",'
        '"contextLength":4096,"parallel":2,"ttlMs":60000}]'
    )
    outputs = iter(
        [
            ProcessOutput(0, current, ""),
            ProcessOutput(0, "unloaded", ""),
            ProcessOutput(0, "[]", ""),
            ProcessOutput(0, "loaded", ""),
            ProcessOutput(0, "[]", ""),
        ]
    )

    async def runner(argv: tuple[str, ...], timeout: float) -> ProcessOutput:
        del timeout
        calls.append(argv)
        return next(outputs)

    adapter = LmStudioAdapter(
        backend_id="lm",
        base_url="http://node.invalid:1234",
        ssh_target="node.invalid",
        known_hosts_file=_known_hosts(tmp_path),
        process_runner=runner,
        transport=_models_transport(model_id="public-model"),
    )

    result = await adapter.tune(
        TuneRequest(
            scope=TuneScope.MODEL,
            model_id="public-model",
            settings=TuneSettings(max_context_window=8192),
        )
    )

    assert result.status is OperationStatus.FAILED
    assert result.error is not None
    assert result.error.code is AdapterErrorCode.PARTIAL_FAILURE
    assert calls[1][-3:] == ("lms", "unload", "public-model")
    assert calls[3][-12:-9] == ("lms", "load", "source-model")


@pytest.mark.asyncio
async def test_tune_reports_partial_failure_after_verified_unload_then_load_failure(
    tmp_path: Path,
) -> None:
    calls: list[tuple[str, ...]] = []
    current = (
        '[{"modelKey":"model-a","identifier":"model-a",'
        '"contextLength":4096,"parallel":2,"ttlMs":60000}]'
    )
    outputs = iter(
        [
            ProcessOutput(0, current, ""),
            ProcessOutput(0, "unloaded", ""),
            ProcessOutput(0, "[]", ""),
            ProcessOutput(2, "remote-token", "remote-secret"),
        ]
    )

    async def runner(argv: tuple[str, ...], timeout: float) -> ProcessOutput:
        del timeout
        calls.append(argv)
        return next(outputs)

    adapter = LmStudioAdapter(
        backend_id="lm",
        base_url="http://node.invalid:1234",
        ssh_target="node.invalid",
        known_hosts_file=_known_hosts(tmp_path),
        process_runner=runner,
        transport=_models_transport(),
    )

    result = await adapter.tune(
        TuneRequest(
            scope=TuneScope.MODEL,
            model_id="model-a",
            settings=TuneSettings(max_context_window=8192),
        )
    )

    assert result.status is OperationStatus.FAILED
    assert result.error is not None
    assert result.error.code is AdapterErrorCode.PARTIAL_FAILURE
    assert "remote-token" not in result.model_dump_json()
    assert "remote-secret" not in result.model_dump_json()
    assert calls[-1][-2:] != ("ps", "--json")


def test_load_options_are_positive_and_bounded() -> None:
    with pytest.raises(ValueError):
        LmsLoadOptions(context_length=0)
    with pytest.raises(ValueError):
        LmsLoadOptions(parallel=65)
    with pytest.raises(ValueError):
        LmsLoadOptions(ttl_seconds=2_592_001)
    with pytest.raises(ValueError):
        LmsLoadOptions(identifier="bad identifier")


@pytest.mark.asyncio
async def test_constructor_rejects_unsafe_optional_inputs() -> None:
    client = httpx.AsyncClient()
    with pytest.raises(ValueError, match="mutually exclusive"):
        LmStudioAdapter(
            backend_id="lm",
            base_url="http://node.invalid:1234",
            client=client,
            transport=httpx.MockTransport(lambda request: httpx.Response(200)),
        )
    with pytest.raises(ValueError, match="safe"):
        LmStudioAdapter(
            backend_id="lm",
            base_url="http://node.invalid:1234",
            probe_model_id="bad model",
        )
    with pytest.raises(ValueError):
        LmStudioAdapter(
            backend_id="lm",
            base_url="http://node.invalid:1234",
            platform="linux",  # type: ignore[arg-type]
        )
    await client.aclose()


@pytest.mark.asyncio
async def test_adapter_closes_only_its_owned_http_client() -> None:
    owned = LmStudioAdapter(backend_id="owned", base_url="http://node.invalid:1234")
    await owned.aclose()
    assert owned._client.is_closed is True

    client = httpx.AsyncClient()
    borrowed = LmStudioAdapter(
        backend_id="borrowed",
        base_url="http://node.invalid:1234",
        client=client,
    )
    await borrowed.aclose()
    assert client.is_closed is False
    await client.aclose()


def test_process_output_repr_never_echoes_remote_streams() -> None:
    output = ProcessOutput(
        returncode=1,
        stdout="token=remote-secret",
        stderr="/Users/private/models/model.gguf",
    )

    rendered = repr(output)

    assert "remote-secret" not in rendered
    assert "/Users/private" not in rendered
    assert "returncode=1" in rendered


def test_known_hosts_test_does_not_depend_on_process_umask(tmp_path: Path) -> None:
    path = _known_hosts(tmp_path)
    assert os.stat(path).st_mode & 0o077 == 0


@pytest.mark.asyncio
async def test_default_process_runner_uses_exec_argv_and_decodes_streams(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, ...]] = []

    class FakeProcess(FakeBoundedProcess):
        def __init__(self) -> None:
            super().__init__(FakeAsyncReader([b"stdout"]), FakeAsyncReader([b"stderr"]))
            self.returncode = 7

        def kill(self) -> None:
            raise AssertionError("successful process must not be killed")

    async def fake_exec(*argv: str, **kwargs: object) -> FakeProcess:
        calls.append(argv)
        assert kwargs == {
            "stdout": asyncio.subprocess.PIPE,
            "stderr": asyncio.subprocess.PIPE,
            "env": None,
        }
        return FakeProcess()

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_exec)

    output = await lmstudio_module._default_process_runner(("ssh", "-T"), 1.0)

    assert calls == [("ssh", "-T")]
    assert output == ProcessOutput(7, "stdout", "stderr")


@pytest.mark.asyncio
async def test_default_process_runner_kills_on_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    process = FakeBoundedProcess(FakeAsyncReader([], block=True), FakeAsyncReader([], block=True))

    async def fake_exec(*argv: str, **kwargs: object) -> FakeBoundedProcess:
        del argv, kwargs
        return process

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_exec)

    with pytest.raises(TimeoutError):
        await lmstudio_module._default_process_runner(("ssh",), 0.001)

    assert process.killed is True
    assert process.wait_count >= 1
    assert process.stdout.cancelled is True
    assert process.stderr.cancelled is True


@pytest.mark.asyncio
@pytest.mark.parametrize("flood_stream", ["stdout", "stderr"])
async def test_default_process_runner_caps_each_output_stream_and_reaps(
    monkeypatch: pytest.MonkeyPatch, flood_stream: str
) -> None:
    stdout = FakeAsyncReader([b"1234", b"56789"] if flood_stream == "stdout" else [b"ok"])
    stderr = FakeAsyncReader([b"1234", b"56789"] if flood_stream == "stderr" else [b"ok"])
    process = FakeBoundedProcess(stdout, stderr)

    async def fake_exec(*argv: str, **kwargs: object) -> FakeBoundedProcess:
        del argv, kwargs
        return process

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_exec)

    with pytest.raises(lmstudio_module.ProcessOutputLimitError):
        await lmstudio_module._default_process_runner(("ssh",), 1.0, output_limit=8)

    assert process.killed is True
    assert process.wait_count >= 1


@pytest.mark.asyncio
async def test_default_process_runner_drains_both_streams_without_deadlock(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    process = FakeBoundedProcess(
        FakeAsyncReader([b"1234", b"5678"]),
        FakeAsyncReader([b"abcd", b"efgh"]),
    )

    async def fake_exec(*argv: str, **kwargs: object) -> FakeBoundedProcess:
        del argv, kwargs
        return process

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_exec)

    output = await lmstudio_module._default_process_runner(("ssh",), 1.0, output_limit=8)

    assert output.stdout == "12345678"
    assert output.stderr == "abcdefgh"
    assert process.killed is False


@pytest.mark.asyncio
async def test_default_process_runner_cancellation_kills_reaps_and_cleans_readers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    process = FakeBoundedProcess(FakeAsyncReader([], block=True), FakeAsyncReader([], block=True))

    async def fake_exec(*argv: str, **kwargs: object) -> FakeBoundedProcess:
        del argv, kwargs
        return process

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_exec)
    task = asyncio.create_task(
        lmstudio_module._default_process_runner(("ssh",), 10.0, output_limit=8)
    )
    await process.stdout.started.wait()
    await process.stderr.started.wait()

    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    assert process.killed is True
    assert process.wait_count >= 1
    assert process.stdout.cancelled is True
    assert process.stderr.cancelled is True


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("failing_stream", "failure"),
    [
        ("stdout", OSError("stdout-reader-secret")),
        ("stderr", RuntimeError("stderr-reader-secret")),
    ],
)
async def test_default_process_runner_reader_exception_kills_reaps_and_settles_tasks(
    monkeypatch: pytest.MonkeyPatch,
    failing_stream: str,
    failure: Exception,
) -> None:
    blocker = FakeAsyncReader([], block=True)
    exploding = FakeExplodingReader(failure)
    process = FakeRunningProcess(
        exploding if failing_stream == "stdout" else blocker,
        exploding if failing_stream == "stderr" else blocker,
    )
    created_tasks: list[asyncio.Task[Any]] = []
    real_create_task = asyncio.create_task

    def tracked_create_task(
        coroutine: Coroutine[Any, Any, Any],
    ) -> asyncio.Task[Any]:
        task = real_create_task(coroutine)
        created_tasks.append(task)
        return task

    async def fake_exec(*argv: str, **kwargs: object) -> FakeRunningProcess:
        del argv, kwargs
        return process

    loop = asyncio.get_running_loop()
    loop_errors: list[dict[str, Any]] = []
    previous_handler = loop.get_exception_handler()

    def capture_loop_error(event_loop: asyncio.AbstractEventLoop, context: dict[str, Any]) -> None:
        del event_loop
        loop_errors.append(context)

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_exec)
    monkeypatch.setattr(asyncio, "create_task", tracked_create_task)
    loop.set_exception_handler(capture_loop_error)
    try:
        with pytest.raises(type(failure), match="reader-secret"):
            await lmstudio_module._default_process_runner(("ssh",), 1.0)
        await asyncio.sleep(0)
        killed_before_test_cleanup = process.killed
        reaped_before_test_cleanup = process.wait_count >= 1
        tasks_done_before_test_cleanup = all(task.done() for task in created_tasks)
        blocker_cancelled_before_test_cleanup = blocker.cancelled
        loop_errors_before_test_cleanup = tuple(loop_errors)
    finally:
        for task in created_tasks:
            if not task.done():
                task.cancel()
        await asyncio.gather(*created_tasks, return_exceptions=True)
        if not process.killed:
            process.kill()
        await process.wait()
        loop.set_exception_handler(previous_handler)

    assert killed_before_test_cleanup is True
    assert reaped_before_test_cleanup is True
    assert tasks_done_before_test_cleanup is True
    assert blocker_cancelled_before_test_cleanup is True
    assert loop_errors_before_test_cleanup == ()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("failing_stream", "failure"),
    [
        ("stdout", OSError("stdout-reader-remote-secret")),
        ("stderr", RuntimeError("stderr-reader-remote-secret")),
    ],
)
async def test_adapter_maps_default_runner_reader_failure_without_remote_detail(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    failing_stream: str,
    failure: Exception,
) -> None:
    blocker = FakeAsyncReader([], block=True)
    exploding = FakeExplodingReader(failure)
    process = FakeRunningProcess(
        exploding if failing_stream == "stdout" else blocker,
        exploding if failing_stream == "stderr" else blocker,
    )

    async def fake_exec(*argv: str, **kwargs: object) -> FakeRunningProcess:
        del argv, kwargs
        return process

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_exec)
    adapter = LmStudioAdapter(
        backend_id="lm",
        base_url="http://node.invalid:1234",
        ssh_target="node.invalid",
        known_hosts_file=_known_hosts(tmp_path),
        transport=_models_transport(),
    )

    result = await adapter.load_model("model-a")

    assert result.status is OperationStatus.FAILED
    assert result.error is not None
    assert result.error.code is AdapterErrorCode.BAD_RESPONSE
    assert str(failure) not in result.model_dump_json()
    assert process.killed is True
    assert process.wait_count >= 1
    assert blocker.cancelled is True


@pytest.mark.asyncio
async def test_adapter_keeps_default_process_spawn_failure_unreachable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def fake_exec(*argv: str, **kwargs: object) -> FakeRunningProcess:
        del argv, kwargs
        raise OSError("spawn-remote-secret")

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_exec)
    adapter = LmStudioAdapter(
        backend_id="lm",
        base_url="http://node.invalid:1234",
        ssh_target="node.invalid",
        known_hosts_file=_known_hosts(tmp_path),
        transport=_models_transport(),
    )

    result = await adapter.load_model("model-a")

    assert result.status is OperationStatus.FAILED
    assert result.error is not None
    assert result.error.code is AdapterErrorCode.UNREACHABLE
    assert "spawn-remote-secret" not in result.model_dump_json()


@pytest.mark.asyncio
async def test_adapter_maps_default_runner_flood_to_typed_output_limit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def fake_exec(*argv: str, **kwargs: object) -> FakeBoundedProcess:
        del argv, kwargs
        return FakeBoundedProcess(FakeAsyncReader([b"1234", b"56789"]), FakeAsyncReader([b""]))

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_exec)
    adapter = LmStudioAdapter(
        backend_id="lm",
        base_url="http://node.invalid:1234",
        ssh_target="node.invalid",
        known_hosts_file=_known_hosts(tmp_path),
        process_output_limit=8,
        transport=_models_transport(),
    )

    result = await adapter.load_model("model-a")

    assert result.status is OperationStatus.FAILED
    assert result.error is not None
    assert result.error.code is AdapterErrorCode.OUTPUT_LIMIT
    assert "1234" not in result.model_dump_json()


@pytest.mark.asyncio
async def test_discover_distinguishes_transport_and_incompatible_inventory() -> None:
    async def unreachable(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("credential-value", request=request)

    offline = LmStudioAdapter(
        backend_id="lm",
        base_url="https://node.invalid:1234",
        transport=httpx.MockTransport(unreachable),
    )
    offline_snapshot = await offline.discover()
    assert offline_snapshot.reachable is False
    assert offline_snapshot.compatible is False
    assert "credential-value" not in offline_snapshot.model_dump_json()

    async def incompatible(request: httpx.Request) -> httpx.Response:
        del request
        return httpx.Response(200, json={"data": {"not": "a-list"}})

    drifted = LmStudioAdapter(
        backend_id="lm",
        base_url="https://node.invalid:1234",
        transport=httpx.MockTransport(incompatible),
    )
    drifted_snapshot = await drifted.discover()
    assert drifted_snapshot.reachable is True
    assert drifted_snapshot.compatible is False


@pytest.mark.asyncio
async def test_embedding_success_and_malformed_vector_are_typed() -> None:
    responses = iter(
        [
            httpx.Response(
                200,
                json={
                    "data": [{"embedding": [1, 2.5]}],
                    "usage": {"prompt_tokens": 2, "total_tokens": 2},
                },
            ),
            httpx.Response(200, json={"data": [{"embedding": [True]}]}),
        ]
    )

    async def handler(request: httpx.Request) -> httpx.Response:
        del request
        return next(responses)

    adapter = LmStudioAdapter(
        backend_id="lm",
        base_url="https://node.invalid:1234",
        transport=httpx.MockTransport(handler),
    )
    request = EmbeddingRequest(request_id="embed", model="model-a", input="hello")

    success = await adapter.embed(request)
    malformed = await adapter.embed(request.model_copy(update={"request_id": "bad"}))

    assert success.status is OperationStatus.SUCCEEDED
    assert success.embeddings == ((1.0, 2.5),)
    assert success.usage is not None and success.usage.total_tokens == 2
    assert malformed.status is OperationStatus.FAILED
    assert malformed.error is not None
    assert malformed.error.code is AdapterErrorCode.BAD_RESPONSE


@pytest.mark.asyncio
async def test_runtime_known_hosts_drift_and_malformed_control_item_fail_closed(
    tmp_path: Path,
) -> None:
    calls = 0

    async def runner(argv: tuple[str, ...], timeout: float) -> ProcessOutput:
        nonlocal calls
        del argv, timeout
        calls += 1
        return ProcessOutput(0, "[null]", "")

    known_hosts = _known_hosts(tmp_path)
    adapter = LmStudioAdapter(
        backend_id="lm",
        base_url="http://node.invalid:1234",
        ssh_target="node.invalid",
        known_hosts_file=known_hosts,
        process_runner=runner,
        transport=_models_transport(),
    )
    malformed = await adapter.list_models()
    assert malformed[0].state is ModelRuntimeState.UNKNOWN
    assert calls == 1

    known_hosts.chmod(0o622)
    drifted = await adapter.list_models()
    assert drifted[0].state is ModelRuntimeState.UNKNOWN
    assert calls == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", [OSError("missing ssh"), RuntimeError("runner drift")])
async def test_process_start_and_runner_failures_preserve_unknown(
    tmp_path: Path, failure: Exception
) -> None:
    async def runner(argv: tuple[str, ...], timeout: float) -> ProcessOutput:
        del argv, timeout
        raise failure

    adapter = LmStudioAdapter(
        backend_id="lm",
        base_url="http://node.invalid:1234",
        ssh_target="node.invalid",
        known_hosts_file=_known_hosts(tmp_path),
        process_runner=runner,
        transport=_models_transport(),
    )

    models = await adapter.list_models()
    result = await adapter.load_model("model-a")

    assert models[0].state is ModelRuntimeState.UNKNOWN
    assert result.status is OperationStatus.FAILED
    assert result.error is not None
    assert result.error.code in {
        AdapterErrorCode.UNREACHABLE,
        AdapterErrorCode.BAD_RESPONSE,
    }
    assert str(failure) not in result.model_dump_json()


@pytest.mark.asyncio
async def test_stream_http_error_and_invalid_utf8_are_typed() -> None:
    responses = iter(
        [
            httpx.Response(503, json={"error": "credential-value"}),
            httpx.Response(200, content=b"data: \xff\n\n"),
        ]
    )

    async def handler(request: httpx.Request) -> httpx.Response:
        del request
        return next(responses)

    adapter = LmStudioAdapter(
        backend_id="lm",
        base_url="https://node.invalid:1234",
        transport=httpx.MockTransport(handler),
    )
    request = ChatRequest(
        request_id="stream-errors",
        model="model-a",
        messages=(ChatMessage(role="user", content="hello"),),
    )

    http_events = [event async for event in adapter.stream_chat(request)]
    utf8_events = [event async for event in adapter.stream_chat(request)]

    assert http_events[-1].error is not None
    assert http_events[-1].error.code is AdapterErrorCode.BAD_RESPONSE
    assert "credential-value" not in http_events[-1].model_dump_json()
    assert utf8_events[-1].error is not None
    assert utf8_events[-1].error.code is AdapterErrorCode.BAD_RESPONSE
