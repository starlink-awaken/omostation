"""Backend-neutral bounded asynchronous subprocess execution."""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from contextlib import suppress
from dataclasses import dataclass, field
from typing import Protocol, cast

DEFAULT_PROCESS_OUTPUT_LIMIT = 1024 * 1024


@dataclass(frozen=True, slots=True)
class ProcessOutput:
    returncode: int
    stdout: str = field(repr=False)
    stderr: str = field(repr=False)


class ProcessRunner(Protocol):
    async def __call__(self, argv: tuple[str, ...], timeout: float) -> ProcessOutput: ...


class ProcessOutputLimitError(Exception):
    """Raised without captured bytes when either process stream exceeds its cap."""


class ProcessSpawnError(Exception):
    """Distinguish process creation failure from post-spawn stream failure."""


class ProcessOutputDecodeError(UnicodeError):
    """Sanitized rejection of undecodable or PowerShell diagnostic output."""


def decode_process_output(payload: bytes) -> str:
    """Decode bounded UTF-8/UTF-16 output and reject CLIXML diagnostics."""
    if not payload:
        return ""
    try:
        if payload.startswith((b"\xff\xfe", b"\xfe\xff")):
            decoded = payload.decode("utf-16", errors="strict")
        else:
            try:
                decoded = payload.decode("utf-8", errors="strict")
            except UnicodeDecodeError:
                if len(payload) % 2 != 0 or b"\x00" not in payload:
                    raise
                encoding = (
                    "utf-16-le" if payload[1::2].count(0) >= payload[::2].count(0) else "utf-16-be"
                )
                decoded = payload.decode(encoding, errors="strict")
    except UnicodeDecodeError:
        raise ProcessOutputDecodeError("process output encoding is unsupported") from None
    normalized = decoded.lstrip("\ufeff\r\n \t")
    if normalized.startswith("#< CLIXML") or normalized.startswith("<Objs"):
        raise ProcessOutputDecodeError("PowerShell CLIXML output is not accepted")
    return decoded.lstrip("\ufeff")


@dataclass(frozen=True, slots=True)
class BoundedProcessRunner:
    output_limit: int
    env: Mapping[str, str] | None = None

    async def __call__(self, argv: tuple[str, ...], timeout: float) -> ProcessOutput:
        return await default_process_runner(
            argv,
            timeout,
            output_limit=self.output_limit,
            env=self.env,
        )


async def _read_bounded(stream: asyncio.StreamReader, output_limit: int) -> bytes:
    captured = bytearray()
    while True:
        chunk = await stream.read(65536)
        if not chunk:
            return bytes(captured)
        captured.extend(chunk)
        if len(captured) > output_limit:
            raise ProcessOutputLimitError


async def _kill_reap_and_cleanup(
    process: asyncio.subprocess.Process, tasks: tuple[asyncio.Task[object], ...]
) -> None:
    with suppress(ProcessLookupError):
        process.kill()
    for task in tasks:
        if not task.done():
            task.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)
    with suppress(ProcessLookupError):
        await process.wait()


async def default_process_runner(
    argv: tuple[str, ...],
    timeout: float,
    *,
    output_limit: int = DEFAULT_PROCESS_OUTPUT_LIMIT,
    env: Mapping[str, str] | None = None,
) -> ProcessOutput:
    """Execute an argv without a shell and settle every subprocess task on exit."""
    if output_limit <= 0:
        raise ValueError("process output limit must be positive")
    try:
        process = await asyncio.create_subprocess_exec(
            *argv,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
        )
    except OSError as exc:
        raise ProcessSpawnError from exc
    if process.stdout is None or process.stderr is None:
        await _kill_reap_and_cleanup(process, ())
        raise RuntimeError("subprocess pipes were not created")
    stdout_task = asyncio.create_task(_read_bounded(process.stdout, output_limit))
    stderr_task = asyncio.create_task(_read_bounded(process.stderr, output_limit))
    wait_task = asyncio.create_task(process.wait())
    tasks = cast(
        tuple[asyncio.Task[object], ...],
        (stdout_task, stderr_task, wait_task),
    )
    try:
        stdout, stderr, _ = await asyncio.wait_for(
            asyncio.gather(stdout_task, stderr_task, wait_task), timeout=timeout
        )
    except BaseException:
        await _kill_reap_and_cleanup(process, tasks)
        raise
    return ProcessOutput(
        returncode=process.returncode or 0,
        stdout=decode_process_output(stdout),
        stderr=decode_process_output(stderr),
    )
