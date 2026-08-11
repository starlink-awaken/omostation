"""LM Studio / LM Link adapter with direct HTTP inference and hardened SSH control."""

from __future__ import annotations

import asyncio
import json
import re
import stat
from collections.abc import AsyncIterator, Callable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Literal, Protocol, cast
from urllib.parse import urlsplit

import httpx
from pydantic import Field, field_validator

from omlxc.domain.models import DomainModel
from omlxc.domain.protocols import (
    AdapterCapability,
    AdapterError,
    AdapterErrorCode,
    CapabilitySnapshot,
    ChatMessage,
    ChatRequest,
    ChatResult,
    EmbeddingRequest,
    EmbeddingResult,
    LifecycleResult,
    ModelRuntime,
    ModelRuntimeState,
    OperationStatus,
    StreamEvent,
    StreamEventKind,
    StreamPhase,
    TokenUsage,
    TuneRequest,
    TuneResult,
    TuneScope,
)

from .reasoning import ReasoningFilter
from .security import AdapterFailure
from .sse import SSEDecoder

_TIMEOUT = httpx.Timeout(connect=2.0, read=30.0, write=10.0, pool=2.0)
_UNSUPPORTED_STATUSES = frozenset({404, 405, 501})
_SAFE_TARGET_PART = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9._-]{0,252}[A-Za-z0-9])?$")
_SAFE_MODEL = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/+@-]{0,511}$")


class LmsPlatform(StrEnum):
    MACOS = "macos"
    WINDOWS = "windows"


@dataclass(frozen=True, slots=True)
class ProcessOutput:
    returncode: int
    stdout: str = field(repr=False)
    stderr: str = field(repr=False)


class ProcessRunner(Protocol):
    async def __call__(self, argv: tuple[str, ...], timeout: float) -> ProcessOutput: ...


class LmsLoadOptions(DomainModel):
    """Strictly typed subset of the documented ``lms load`` control flags."""

    context_length: int | None = Field(default=None, ge=1, le=2_000_000)
    parallel: int | None = Field(default=None, ge=1, le=64)
    ttl_seconds: int | None = Field(default=None, ge=1, le=2_592_000)
    identifier: str | None = None
    yes: Literal[True] = True

    @field_validator("identifier")
    @classmethod
    def validate_identifier(cls, value: str | None) -> str | None:
        if value is not None:
            _validate_model_token(value, label="identifier")
        return value


@dataclass(frozen=True, slots=True)
class _ControlRow:
    model_id: str
    identifier: str
    context_length: int | None
    parallel: int | None
    ttl_seconds: int | None


def _mapping(value: object) -> Mapping[str, object] | None:
    if not isinstance(value, Mapping):
        return None
    raw = cast(Mapping[object, object], value)
    return {str(key): item for key, item in raw.items()}


def _list(value: object) -> list[object] | None:
    return cast(list[object], value) if isinstance(value, list) else None


def _validate_model_token(value: str, *, label: str = "model") -> None:
    if not _SAFE_MODEL.fullmatch(value):
        raise ValueError(f"{label} is not a safe lms argument")
    if any(segment == ".." for segment in value.split("/")):
        raise ValueError(f"{label} must not contain path traversal")


def _validate_target(value: str) -> None:
    if value.startswith("-") or value.count("@") > 1:
        raise ValueError("SSH target is invalid")
    user, separator, host = value.rpartition("@")
    if not separator:
        host = value
        user = ""
    if not host or not _SAFE_TARGET_PART.fullmatch(host):
        raise ValueError("SSH target is invalid")
    if ".." in host:
        raise ValueError("SSH target is invalid")
    if user and not _SAFE_TARGET_PART.fullmatch(user):
        raise ValueError("SSH target is invalid")


def _validate_known_hosts(path: Path) -> None:
    if not path.is_absolute():
        raise ValueError("known_hosts file must use an absolute path")
    try:
        metadata = path.lstat()
    except OSError as exc:
        raise ValueError("known_hosts file must exist") from exc
    if not stat.S_ISREG(metadata.st_mode):
        raise ValueError("known_hosts path must be a regular file")
    if metadata.st_mode & 0o022:
        raise ValueError("known_hosts file permissions must reject group/world writes")


async def _default_process_runner(argv: tuple[str, ...], timeout: float) -> ProcessOutput:
    process = await asyncio.create_subprocess_exec(
        *argv,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout)
    except asyncio.CancelledError:
        process.kill()
        await process.wait()
        raise
    except TimeoutError:
        process.kill()
        await process.wait()
        raise
    return ProcessOutput(
        returncode=process.returncode or 0,
        stdout=stdout.decode("utf-8", errors="replace"),
        stderr=stderr.decode("utf-8", errors="replace"),
    )


class LmStudioAdapter:
    """OpenAI-compatible LM Studio inference plus fail-closed ``lms`` control."""

    def __init__(
        self,
        *,
        backend_id: str,
        base_url: str,
        probe_model_id: str | None = None,
        ssh_target: str | None = None,
        known_hosts_file: Path | None = None,
        platform: LmsPlatform = LmsPlatform.MACOS,
        process_runner: ProcessRunner | None = None,
        load_options: LmsLoadOptions | None = None,
        client: httpx.AsyncClient | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        parsed = urlsplit(base_url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("base_url must use http or https")
        if parsed.username is not None or parsed.password is not None:
            raise ValueError("base_url must not contain userinfo")
        if parsed.query or parsed.fragment or parsed.path not in {"", "/"}:
            raise ValueError("base_url must not contain a query, fragment, or API path")
        if client is not None and transport is not None:
            raise ValueError("client and transport are mutually exclusive")
        if (ssh_target is None) != (known_hosts_file is None):
            raise ValueError("SSH target and known_hosts file must be configured together")
        if ssh_target is not None:
            _validate_target(ssh_target)
            assert known_hosts_file is not None
            _validate_known_hosts(known_hosts_file)
        if probe_model_id is not None:
            _validate_model_token(probe_model_id, label="probe model")

        self._backend_id = backend_id
        self._base_url = httpx.URL(base_url.rstrip("/") + "/")
        self._probe_model_id = probe_model_id
        self._ssh_target = ssh_target
        self._known_hosts_file = known_hosts_file
        self._platform = LmsPlatform(platform)
        self._runner = process_runner or _default_process_runner
        self._load_options = load_options or LmsLoadOptions()
        self._clock = clock or (lambda: datetime.now(UTC))
        self._owns_client = client is None
        self._client = client or httpx.AsyncClient(transport=transport)
        self._timeout = _TIMEOUT

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    def _url(self, path: str) -> httpx.URL:
        return self._base_url.join(path.removeprefix("/"))

    async def _send(
        self,
        method: str,
        path: str,
        *,
        payload: Mapping[str, object] | None = None,
    ) -> httpx.Response:
        try:
            return await self._client.request(
                method,
                self._url(path),
                json=payload,
                timeout=self._timeout,
            )
        except httpx.TimeoutException as exc:
            raise AdapterFailure.from_detail(
                code=AdapterErrorCode.TIMEOUT,
                message="LM Studio request timed out",
                detail={},
                retryable=True,
                endpoint=path,
            ) from exc
        except httpx.TransportError as exc:
            raise AdapterFailure.from_detail(
                code=AdapterErrorCode.UNREACHABLE,
                message="LM Studio transport is unreachable",
                detail={},
                retryable=True,
                endpoint=path,
            ) from exc

    @staticmethod
    def _json_object(response: httpx.Response, *, endpoint: str) -> dict[str, object]:
        if not response.content:
            raise AdapterFailure.from_detail(
                code=AdapterErrorCode.BAD_RESPONSE,
                message="LM Studio returned an empty response",
                detail={},
                http_status=response.status_code,
                endpoint=endpoint,
            )
        try:
            parsed = cast(object, json.loads(response.content))
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise AdapterFailure.from_detail(
                code=AdapterErrorCode.BAD_RESPONSE,
                message="LM Studio returned non-JSON data",
                detail={},
                http_status=response.status_code,
                endpoint=endpoint,
            ) from exc
        if not isinstance(parsed, dict):
            raise AdapterFailure.from_detail(
                code=AdapterErrorCode.BAD_RESPONSE,
                message="LM Studio returned an unexpected JSON shape",
                detail={},
                http_status=response.status_code,
                endpoint=endpoint,
            )
        return cast(dict[str, object], parsed)

    @staticmethod
    def _http_error(response: httpx.Response, *, endpoint: str) -> AdapterFailure:
        code = (
            AdapterErrorCode.UNSUPPORTED
            if response.status_code in _UNSUPPORTED_STATUSES
            else AdapterErrorCode.BAD_RESPONSE
        )
        return AdapterFailure.from_detail(
            code=code,
            message=(
                "LM Studio endpoint is unsupported"
                if code is AdapterErrorCode.UNSUPPORTED
                else "LM Studio returned an HTTP error"
            ),
            detail={},
            retryable=response.status_code >= 500,
            http_status=response.status_code,
            endpoint=endpoint,
        )

    def _ssh_argv(self, arguments: tuple[str, ...]) -> tuple[str, ...]:
        if self._ssh_target is None or self._known_hosts_file is None:
            raise AdapterFailure.from_detail(
                code=AdapterErrorCode.UNSUPPORTED,
                message="LM Studio control channel is not configured",
                detail={},
            )
        try:
            _validate_known_hosts(self._known_hosts_file)
        except ValueError as exc:
            raise AdapterFailure.from_detail(
                code=AdapterErrorCode.INVALID_REQUEST,
                message="known_hosts validation failed",
                detail={},
            ) from exc
        executable = "lms" if self._platform is LmsPlatform.MACOS else "lms.exe"
        return (
            "ssh",
            "-T",
            "-o",
            "BatchMode=yes",
            "-o",
            "StrictHostKeyChecking=yes",
            "-o",
            "IdentitiesOnly=yes",
            "-o",
            f"UserKnownHostsFile={self._known_hosts_file}",
            "-o",
            "ConnectTimeout=7",
            "-o",
            "ServerAliveInterval=5",
            "-o",
            "ServerAliveCountMax=2",
            "--",
            self._ssh_target,
            executable,
            *arguments,
        )

    async def _run_control(self, arguments: tuple[str, ...], *, timeout: float) -> ProcessOutput:
        argv = self._ssh_argv(arguments)
        try:
            output = await self._runner(argv, timeout)
        except asyncio.CancelledError:
            raise
        except TimeoutError as exc:
            raise AdapterFailure.from_detail(
                code=AdapterErrorCode.TIMEOUT,
                message="LM Studio control command timed out",
                detail={},
                retryable=True,
            ) from exc
        except OSError as exc:
            raise AdapterFailure.from_detail(
                code=AdapterErrorCode.UNREACHABLE,
                message="LM Studio control process is unavailable",
                detail={},
                retryable=True,
            ) from exc
        except Exception as exc:
            raise AdapterFailure.from_detail(
                code=AdapterErrorCode.BAD_RESPONSE,
                message="LM Studio control runner failed",
                detail={},
                retryable=True,
            ) from exc
        if output.returncode != 0:
            remote_detail = f"{output.stderr}\n{output.stdout}".lower()
            unsupported = any(
                marker in remote_detail
                for marker in ("unknown command", "unknown option", "not recognized", "unsupported")
            )
            raise AdapterFailure.from_detail(
                code=(
                    AdapterErrorCode.UNSUPPORTED if unsupported else AdapterErrorCode.BAD_RESPONSE
                ),
                message=(
                    "LM Studio CLI version does not support this command"
                    if unsupported
                    else "LM Studio control command failed"
                ),
                detail={},
                retryable=not unsupported,
            )
        if not output.stdout.strip():
            raise AdapterFailure.from_detail(
                code=AdapterErrorCode.BAD_RESPONSE,
                message="LM Studio control command returned empty output",
                detail={},
            )
        return output

    async def _probe_control(self) -> tuple[tuple[_ControlRow, ...] | None, AdapterError | None]:
        if self._ssh_target is None:
            return (
                None,
                AdapterError(
                    code=AdapterErrorCode.UNSUPPORTED,
                    message="LM Studio control channel is not configured",
                ),
            )
        try:
            output = await self._run_control(("ps", "--json"), timeout=15.0)
            parsed = cast(object, json.loads(output.stdout))
        except asyncio.CancelledError:
            raise
        except AdapterFailure as failure:
            return None, failure.error
        except (json.JSONDecodeError, UnicodeDecodeError):
            return (
                None,
                AdapterError(
                    code=AdapterErrorCode.BAD_RESPONSE,
                    message="LM Studio control inventory is not valid JSON",
                ),
            )
        raw_rows = _list(parsed)
        if raw_rows is None:
            return (
                None,
                AdapterError(
                    code=AdapterErrorCode.BAD_RESPONSE,
                    message="LM Studio control inventory has an invalid JSON shape",
                ),
            )
        rows: list[_ControlRow] = []
        for raw in raw_rows:
            item = _mapping(raw)
            if item is None:
                return (
                    None,
                    AdapterError(
                        code=AdapterErrorCode.BAD_RESPONSE,
                        message="LM Studio control inventory contains an invalid item",
                    ),
                )
            raw_model = item.get("modelKey")
            raw_identifier = item.get("identifier")
            model_id = raw_model if isinstance(raw_model, str) else raw_identifier
            identifier = raw_identifier if isinstance(raw_identifier, str) else model_id
            if not isinstance(model_id, str) or not isinstance(identifier, str):
                return (
                    None,
                    AdapterError(
                        code=AdapterErrorCode.BAD_RESPONSE,
                        message="LM Studio control inventory omits model identity",
                    ),
                )
            try:
                _validate_model_token(model_id)
                _validate_model_token(identifier, label="identifier")
            except ValueError:
                return (
                    None,
                    AdapterError(
                        code=AdapterErrorCode.BAD_RESPONSE,
                        message="LM Studio control inventory contains an unsafe identity",
                    ),
                )
            context_length = item.get("contextLength")
            parallel = item.get("parallel")
            ttl_ms = item.get("ttlMs")
            rows.append(
                _ControlRow(
                    model_id=model_id,
                    identifier=identifier,
                    context_length=(
                        context_length
                        if isinstance(context_length, int)
                        and not isinstance(context_length, bool)
                        and context_length > 0
                        else None
                    ),
                    parallel=(
                        parallel
                        if isinstance(parallel, int)
                        and not isinstance(parallel, bool)
                        and parallel > 0
                        else None
                    ),
                    ttl_seconds=(
                        int(ttl_ms / 1000)
                        if isinstance(ttl_ms, (int, float))
                        and not isinstance(ttl_ms, bool)
                        and ttl_ms > 0
                        else None
                    ),
                )
            )
        return tuple(rows), None

    async def discover(self) -> CapabilitySnapshot:
        observed_at = self._clock()
        try:
            models, control_error, control_known, _ = await self._list_models_with_control()
        except AdapterFailure as failure:
            return CapabilitySnapshot(
                backend_id=self._backend_id,
                reachable=failure.error.code is not AdapterErrorCode.UNREACHABLE,
                compatible=False,
                model_available=False,
                generation_ready=False,
                observed_at=observed_at,
                errors=(failure.error,),
            )

        model_available = bool(models)
        errors = () if control_error is None else (control_error,)
        probe_id = self._probe_model_id
        if probe_id is None:
            probe_id = next((model.id for model in models if model.loaded is True), None)
        loaded_ids = {model.id for model in models if model.loaded is True}
        generation_ready = False
        if probe_id is not None and probe_id in loaded_ids:
            probe = await self.chat(
                ChatRequest(
                    request_id="lmstudio-readiness-probe",
                    model=probe_id,
                    messages=(ChatMessage(role="user", content="Reply O only"),),
                    max_tokens=1,
                    temperature=0.0,
                )
            )
            generation_ready = probe.success and bool(probe.content)
            if probe.error is not None:
                errors += (probe.error,)
        capabilities = {
            AdapterCapability.CHAT,
            AdapterCapability.STREAMING,
            AdapterCapability.VISION,
        }
        if control_known:
            capabilities.add(AdapterCapability.MODEL_LIFECYCLE)
            capabilities.add(AdapterCapability.TUNING)
        return CapabilitySnapshot(
            backend_id=self._backend_id,
            reachable=True,
            compatible=True,
            model_available=model_available,
            generation_ready=generation_ready,
            observed_at=observed_at,
            protocol_version="openai-compatible-v1",
            capabilities=frozenset(capabilities),
            errors=errors,
        )

    async def list_models(self) -> tuple[ModelRuntime, ...]:
        models, _, _, _ = await self._list_models_with_control()
        return models

    async def _list_models_with_control(
        self,
    ) -> tuple[
        tuple[ModelRuntime, ...],
        AdapterError | None,
        bool,
        Mapping[str, _ControlRow],
    ]:
        endpoint = "/v1/models"
        response = await self._send("GET", endpoint)
        if not response.is_success:
            raise self._http_error(response, endpoint=endpoint)
        document = self._json_object(response, endpoint=endpoint)
        raw_inventory = _list(document.get("data"))
        if raw_inventory is None:
            raise AdapterFailure.from_detail(
                code=AdapterErrorCode.INCOMPATIBLE,
                message="LM Studio model inventory is incompatible",
                detail={},
                endpoint=endpoint,
            )
        http_ids: list[str] = []
        for raw in raw_inventory:
            item = _mapping(raw)
            model_id = item.get("id") if item is not None else None
            if not isinstance(model_id, str):
                continue
            try:
                _validate_model_token(model_id)
            except ValueError:
                continue
            if model_id not in http_ids:
                http_ids.append(model_id)

        control_rows, control_error = await self._probe_control()
        control_by_model: dict[str, _ControlRow] = {}
        control_only_ids: list[str] = []
        if control_rows is not None:
            for row in control_rows:
                matched_id = next(
                    (http_id for http_id in http_ids if http_id in {row.model_id, row.identifier}),
                    None,
                )
                if matched_id is not None:
                    control_by_model[matched_id] = row
                else:
                    control_by_model[row.model_id] = row
                    control_only_ids.append(row.model_id)
        all_ids = list(http_ids)
        all_ids.extend(model_id for model_id in control_only_ids if model_id not in all_ids)
        models = tuple(
            ModelRuntime(
                id=model_id,
                state=(
                    ModelRuntimeState.UNKNOWN
                    if control_rows is None
                    else ModelRuntimeState.LOADED
                    if model_id in control_by_model
                    else ModelRuntimeState.AVAILABLE
                ),
                loaded=(None if control_rows is None else model_id in control_by_model),
                context_limit=(
                    control_by_model[model_id].context_length
                    if model_id in control_by_model
                    else None
                ),
            )
            for model_id in all_ids
        )
        return models, control_error, control_rows is not None, control_by_model

    async def load_model(
        self, model_id: str, *, idempotency_key: str | None = None
    ) -> LifecycleResult:
        return await self._change_model_state(
            model_id,
            load=True,
            idempotency_key=idempotency_key,
            options=self._load_options,
        )

    async def unload_model(
        self, model_id: str, *, idempotency_key: str | None = None
    ) -> LifecycleResult:
        return await self._change_model_state(
            model_id,
            load=False,
            idempotency_key=idempotency_key,
            options=self._load_options,
        )

    @staticmethod
    def _lifecycle_failure(
        model_id: str,
        error: AdapterError,
        *,
        idempotency_key: str | None,
    ) -> LifecycleResult:
        return LifecycleResult(
            model_id=model_id,
            status=(
                OperationStatus.UNSUPPORTED
                if error.code is AdapterErrorCode.UNSUPPORTED
                else OperationStatus.FAILED
            ),
            changed=False,
            idempotency_key=idempotency_key,
            error=error,
        )

    async def _change_model_state(
        self,
        model_id: str,
        *,
        load: bool,
        idempotency_key: str | None,
        options: LmsLoadOptions,
    ) -> LifecycleResult:
        try:
            _validate_model_token(model_id)
        except ValueError:
            return self._lifecycle_failure(
                model_id,
                AdapterError(
                    code=AdapterErrorCode.INVALID_REQUEST,
                    message="model is not a safe lms argument",
                ),
                idempotency_key=idempotency_key,
            )
        try:
            models, control_error, _, control_by_model = await self._list_models_with_control()
        except AdapterFailure as failure:
            return self._lifecycle_failure(model_id, failure.error, idempotency_key=idempotency_key)
        model = next((candidate for candidate in models if candidate.id == model_id), None)
        if model is None:
            return self._lifecycle_failure(
                model_id,
                AdapterError(
                    code=AdapterErrorCode.MODEL_UNAVAILABLE,
                    message="model is not present in the LM Studio inventory",
                ),
                idempotency_key=idempotency_key,
            )
        if model.loaded is None:
            return LifecycleResult(
                model_id=model_id,
                status=OperationStatus.FAILED,
                changed=False,
                idempotency_key=idempotency_key,
                error=control_error
                or AdapterError(
                    code=AdapterErrorCode.BAD_RESPONSE,
                    message="model loaded state is indeterminate",
                    retryable=True,
                ),
            )
        if model.loaded is load:
            return LifecycleResult(
                model_id=model_id,
                status=OperationStatus.UNCHANGED,
                changed=False,
                idempotency_key=idempotency_key,
            )

        arguments = (
            self._load_arguments(model_id, options)
            if load
            else ("unload", control_by_model[model_id].identifier)
        )
        try:
            await self._run_control(arguments, timeout=300.0)
            verified, verify_error, _, _ = await self._list_models_with_control()
        except AdapterFailure as failure:
            return self._lifecycle_failure(model_id, failure.error, idempotency_key=idempotency_key)
        verified_model = next(
            (candidate for candidate in verified if candidate.id == model_id), None
        )
        if (
            verified_model is None
            or verified_model.loaded is None
            or verified_model.loaded is not load
        ):
            return self._lifecycle_failure(
                model_id,
                verify_error
                or AdapterError(
                    code=AdapterErrorCode.BAD_RESPONSE,
                    message="LM Studio lifecycle postcondition did not verify",
                    retryable=True,
                ),
                idempotency_key=idempotency_key,
            )
        return LifecycleResult(
            model_id=model_id,
            status=OperationStatus.SUCCEEDED,
            changed=True,
            idempotency_key=idempotency_key,
        )

    @staticmethod
    def _load_arguments(model_id: str, options: LmsLoadOptions) -> tuple[str, ...]:
        arguments = ["load", model_id]
        if options.context_length is not None:
            arguments.extend(("-c", str(options.context_length)))
        if options.parallel is not None:
            arguments.extend(("--parallel", str(options.parallel)))
        if options.ttl_seconds is not None:
            arguments.extend(("--ttl", str(options.ttl_seconds)))
        if options.identifier is not None:
            arguments.extend(("--identifier", options.identifier))
        if options.yes:
            arguments.append("-y")
        return tuple(arguments)

    async def tune(self, request: TuneRequest) -> TuneResult:
        if request.scope is not TuneScope.MODEL or request.model_id is None:
            return self._tune_failure(
                request,
                AdapterError(
                    code=AdapterErrorCode.UNSUPPORTED,
                    message="LM Studio supports only model-scoped CLI tuning",
                ),
            )
        raw_settings = request.settings.model_dump(exclude_unset=True)
        supported = {"max_context_window", "ttl_seconds"}
        if not raw_settings or set(raw_settings) - supported:
            return self._tune_failure(
                request,
                AdapterError(
                    code=AdapterErrorCode.UNSUPPORTED,
                    message="LM Studio cannot map the requested tuning fields safely",
                ),
            )
        model_id = request.model_id
        try:
            _validate_model_token(model_id)
            rows, row_error = await self._probe_control()
        except ValueError:
            return self._tune_failure(
                request,
                AdapterError(
                    code=AdapterErrorCode.INVALID_REQUEST,
                    message="model is not a safe lms argument",
                ),
            )
        except AdapterFailure as failure:
            return self._tune_failure(request, failure.error)
        if rows is None:
            return self._tune_failure(
                request,
                row_error
                or AdapterError(
                    code=AdapterErrorCode.BAD_RESPONSE,
                    message="LM Studio tuning state is indeterminate",
                ),
            )
        row = next((candidate for candidate in rows if candidate.model_id == model_id), None)
        if row is None:
            return self._tune_failure(
                request,
                AdapterError(
                    code=AdapterErrorCode.UNSUPPORTED,
                    message="LM Studio tuning requires a confirmed loaded model",
                ),
            )
        desired_context = cast(int | None, raw_settings.get("max_context_window"))
        desired_ttl = cast(int | None, raw_settings.get("ttl_seconds"))
        changed_fields = tuple(
            field
            for field, actual, desired in (
                ("max_context_window", row.context_length, desired_context),
                ("ttl_seconds", row.ttl_seconds, desired_ttl),
            )
            if desired is not None and actual != desired
        )
        if not changed_fields:
            return TuneResult(
                scope=request.scope,
                model_id=model_id,
                status=OperationStatus.UNCHANGED,
                idempotency_key=request.idempotency_key,
            )
        if row.parallel is None:
            return self._tune_failure(
                request,
                AdapterError(
                    code=AdapterErrorCode.UNSUPPORTED,
                    message="LM Studio tuning cannot preserve an unknown parallel setting",
                ),
            )
        options = LmsLoadOptions(
            context_length=desired_context or row.context_length,
            parallel=row.parallel,
            ttl_seconds=desired_ttl or row.ttl_seconds,
            identifier=row.identifier,
        )
        try:
            await self._run_control(("unload", row.identifier), timeout=300.0)
            unloaded_rows, unloaded_error = await self._probe_control()
            if unloaded_rows is None or any(
                candidate.model_id == model_id for candidate in unloaded_rows
            ):
                return self._tune_failure(
                    request,
                    unloaded_error
                    or AdapterError(
                        code=AdapterErrorCode.BAD_RESPONSE,
                        message="LM Studio tune unload postcondition did not verify",
                        retryable=True,
                    ),
                )
            await self._run_control(self._load_arguments(model_id, options), timeout=300.0)
            loaded_rows, loaded_error = await self._probe_control()
        except AdapterFailure as failure:
            return self._tune_failure(request, failure.error)
        verified = (
            next(
                (candidate for candidate in loaded_rows if candidate.model_id == model_id),
                None,
            )
            if loaded_rows is not None
            else None
        )
        if (
            verified is None
            or verified.context_length != options.context_length
            or verified.parallel != options.parallel
            or verified.ttl_seconds != options.ttl_seconds
        ):
            return self._tune_failure(
                request,
                loaded_error
                or AdapterError(
                    code=AdapterErrorCode.BAD_RESPONSE,
                    message="LM Studio tune load postcondition did not verify",
                    retryable=True,
                ),
            )
        return TuneResult(
            scope=request.scope,
            model_id=model_id,
            status=OperationStatus.SUCCEEDED,
            changed_fields=changed_fields,
            idempotency_key=request.idempotency_key,
        )

    @staticmethod
    def _tune_failure(request: TuneRequest, error: AdapterError) -> TuneResult:
        return TuneResult(
            scope=request.scope,
            model_id=request.model_id,
            status=(
                OperationStatus.UNSUPPORTED
                if error.code is AdapterErrorCode.UNSUPPORTED
                else OperationStatus.FAILED
            ),
            idempotency_key=request.idempotency_key,
            error=error,
        )

    @staticmethod
    def _message_payload(message: ChatMessage) -> dict[str, object]:
        return cast(dict[str, object], message.model_dump(mode="json"))

    def _chat_payload(self, request: ChatRequest, *, stream: bool) -> dict[str, object]:
        # LM Studio has no stable cross-version wire knob for thinking-off.  Send only
        # OpenAI-compatible fields, then fail closed while filtering response reasoning.
        return {
            "model": request.model,
            "messages": [self._message_payload(message) for message in request.messages],
            "max_tokens": request.max_tokens,
            "temperature": request.temperature,
            "stream": stream,
        }

    async def chat(self, request: ChatRequest) -> ChatResult:
        endpoint = "/v1/chat/completions"
        try:
            response = await self._send(
                "POST", endpoint, payload=self._chat_payload(request, stream=False)
            )
            if not response.is_success:
                raise self._http_error(response, endpoint=endpoint)
            document = self._json_object(response, endpoint=endpoint)
            content, finish_reason = self._parse_chat_choice(document)
            safe_content, unclosed = self._strip_reasoning(content)
            if unclosed:
                raise AdapterFailure.from_detail(
                    code=AdapterErrorCode.BAD_RESPONSE,
                    message="LM Studio chat response contains an unclosed reasoning block",
                    detail={},
                )
            if not safe_content:
                raise AdapterFailure.from_detail(
                    code=AdapterErrorCode.BAD_RESPONSE,
                    message="LM Studio chat response contains no visible content",
                    detail={},
                )
        except AdapterFailure as failure:
            return ChatResult(
                request_id=request.request_id,
                success=False,
                error=failure.error,
            )
        return ChatResult(
            request_id=request.request_id,
            success=True,
            content=safe_content,
            finish_reason=finish_reason,
            usage=self._parse_usage(document.get("usage")),
        )

    @staticmethod
    def _parse_chat_choice(document: Mapping[str, object]) -> tuple[str, str | None]:
        choices = _list(document.get("choices"))
        choice = _mapping(choices[0]) if choices else None
        message = _mapping(choice.get("message")) if choice is not None else None
        if message is None:
            raise AdapterFailure.from_detail(
                code=AdapterErrorCode.BAD_RESPONSE,
                message="LM Studio chat response has no message",
                detail={},
            )
        content = message.get("content")
        finish_reason = choice.get("finish_reason") if choice is not None else None
        return (
            content if isinstance(content, str) else "",
            finish_reason if isinstance(finish_reason, str) else None,
        )

    @staticmethod
    def _strip_reasoning(content: str) -> tuple[str, bool]:
        filtered = ReasoningFilter()
        safe = filtered.feed(content)
        remaining, unclosed = filtered.finish()
        return safe + remaining, unclosed

    @staticmethod
    def _parse_usage(value: object) -> TokenUsage | None:
        mapping = _mapping(value)
        if mapping is None:
            return None

        def count(key: str) -> int:
            raw = mapping.get(key, 0)
            return raw if isinstance(raw, int) and not isinstance(raw, bool) and raw >= 0 else 0

        return TokenUsage(
            prompt_tokens=count("prompt_tokens"),
            completion_tokens=count("completion_tokens"),
            total_tokens=count("total_tokens"),
        )

    async def embed(self, request: EmbeddingRequest) -> EmbeddingResult:
        endpoint = "/v1/embeddings"
        try:
            response = await self._send(
                "POST", endpoint, payload={"model": request.model, "input": request.input}
            )
            if not response.is_success:
                raise self._http_error(response, endpoint=endpoint)
            document = self._json_object(response, endpoint=endpoint)
            embeddings = self._parse_embeddings(document)
        except AdapterFailure as failure:
            return EmbeddingResult(
                request_id=request.request_id,
                status=(
                    OperationStatus.UNSUPPORTED
                    if failure.error.code is AdapterErrorCode.UNSUPPORTED
                    else OperationStatus.FAILED
                ),
                error=failure.error,
            )
        return EmbeddingResult(
            request_id=request.request_id,
            status=OperationStatus.SUCCEEDED,
            embeddings=embeddings,
            usage=self._parse_usage(document.get("usage")),
        )

    @staticmethod
    def _parse_embeddings(document: Mapping[str, object]) -> tuple[tuple[float, ...], ...]:
        data = _list(document.get("data"))
        if not data:
            raise AdapterFailure.from_detail(
                code=AdapterErrorCode.BAD_RESPONSE,
                message="LM Studio embedding response has no vectors",
                detail={},
            )
        vectors: list[tuple[float, ...]] = []
        for raw in data:
            item = _mapping(raw)
            vector = _list(item.get("embedding")) if item is not None else None
            if vector is None or not all(
                isinstance(number, (int, float)) and not isinstance(number, bool)
                for number in vector
            ):
                raise AdapterFailure.from_detail(
                    code=AdapterErrorCode.BAD_RESPONSE,
                    message="LM Studio embedding vector is invalid",
                    detail={},
                )
            vectors.append(tuple(float(cast(int | float, number)) for number in vector))
        return tuple(vectors)

    async def stream_chat(self, request: ChatRequest) -> AsyncIterator[StreamEvent]:
        endpoint = "/v1/chat/completions"
        emitted_content = False
        saw_data = False
        reasoning_filter = ReasoningFilter()
        decoder = SSEDecoder()
        try:
            async with self._client.stream(
                "POST",
                self._url(endpoint),
                json=self._chat_payload(request, stream=True),
                timeout=self._timeout,
            ) as response:
                if not response.is_success:
                    yield self._stream_error(
                        request.request_id,
                        self._http_error(response, endpoint=endpoint).error,
                        emitted_content=False,
                    )
                    return
                try:
                    async for chunk in response.aiter_bytes():
                        for data in decoder.feed(chunk):
                            saw_data = True
                            events, emitted_content, complete = self._stream_frame_events(
                                request_id=request.request_id,
                                data=data,
                                reasoning_filter=reasoning_filter,
                                emitted_content=emitted_content,
                            )
                            for event in events:
                                yield event
                            if complete:
                                return
                    finish = decoder.finish()
                except UnicodeDecodeError:
                    yield self._stream_error(
                        request.request_id,
                        AdapterError(
                            code=AdapterErrorCode.BAD_RESPONSE,
                            message="LM Studio stream emitted invalid UTF-8",
                        ),
                        emitted_content=emitted_content,
                    )
                    return
                for data in finish.events:
                    saw_data = True
                    events, emitted_content, complete = self._stream_frame_events(
                        request_id=request.request_id,
                        data=data,
                        reasoning_filter=reasoning_filter,
                        emitted_content=emitted_content,
                    )
                    for event in events:
                        yield event
                    if complete:
                        return
                if finish.incomplete_event:
                    yield self._stream_error(
                        request.request_id,
                        AdapterError(
                            code=AdapterErrorCode.BAD_RESPONSE,
                            message="LM Studio stream ended with an incomplete SSE event",
                            retryable=not emitted_content,
                        ),
                        emitted_content=emitted_content,
                    )
                    return
        except httpx.TimeoutException:
            yield self._stream_error(
                request.request_id,
                AdapterError(
                    code=AdapterErrorCode.TIMEOUT,
                    message="LM Studio stream timed out",
                    retryable=not emitted_content,
                ),
                emitted_content=emitted_content,
            )
            return
        except httpx.TransportError:
            yield self._stream_error(
                request.request_id,
                AdapterError(
                    code=AdapterErrorCode.STREAM_INTERRUPTED,
                    message="LM Studio stream was interrupted",
                    retryable=not emitted_content,
                    emitted_content=emitted_content,
                    phase=(
                        StreamPhase.AFTER_CONTENT if emitted_content else StreamPhase.BEFORE_CONTENT
                    ),
                ),
                emitted_content=emitted_content,
            )
            return
        yield self._stream_error(
            request.request_id,
            AdapterError(
                code=(
                    AdapterErrorCode.STREAM_INTERRUPTED
                    if saw_data
                    else AdapterErrorCode.BAD_RESPONSE
                ),
                message=(
                    "LM Studio stream ended before completion"
                    if saw_data
                    else "LM Studio stream returned an empty body"
                ),
                retryable=not emitted_content,
                emitted_content=emitted_content,
                phase=(
                    StreamPhase.AFTER_CONTENT if emitted_content else StreamPhase.BEFORE_CONTENT
                ),
            ),
            emitted_content=emitted_content,
        )

    def _stream_frame_events(
        self,
        *,
        request_id: str,
        data: str,
        reasoning_filter: ReasoningFilter,
        emitted_content: bool,
    ) -> tuple[tuple[StreamEvent, ...], bool, bool]:
        if data.strip() == "[DONE]":
            events: list[StreamEvent] = []
            remaining, unclosed = reasoning_filter.finish()
            if unclosed:
                error = AdapterError(
                    code=AdapterErrorCode.BAD_RESPONSE,
                    message="LM Studio stream ended with an unclosed reasoning block",
                    retryable=not emitted_content,
                )
                return (
                    (self._stream_error(request_id, error, emitted_content=emitted_content),),
                    emitted_content,
                    True,
                )
            if remaining:
                emitted_content = True
                events.append(
                    StreamEvent(
                        kind=StreamEventKind.CONTENT,
                        request_id=request_id,
                        content=remaining,
                        emitted_content=True,
                        phase=StreamPhase.AFTER_CONTENT,
                    )
                )
            if not emitted_content:
                error = AdapterError(
                    code=AdapterErrorCode.BAD_RESPONSE,
                    message="LM Studio stream completed without visible content",
                )
                return (
                    (self._stream_error(request_id, error, emitted_content=False),),
                    False,
                    True,
                )
            events.append(
                StreamEvent(
                    kind=StreamEventKind.DONE,
                    request_id=request_id,
                    emitted_content=emitted_content,
                    phase=StreamPhase.COMPLETE,
                )
            )
            return tuple(events), emitted_content, True
        try:
            parsed = cast(object, json.loads(data))
        except json.JSONDecodeError:
            error = AdapterError(
                code=AdapterErrorCode.BAD_RESPONSE,
                message="LM Studio stream emitted non-JSON data",
            )
            return (
                (self._stream_error(request_id, error, emitted_content=emitted_content),),
                emitted_content,
                True,
            )
        if not isinstance(parsed, dict):
            error = AdapterError(
                code=AdapterErrorCode.BAD_RESPONSE,
                message="LM Studio stream emitted an unexpected JSON shape",
            )
            return (
                (self._stream_error(request_id, error, emitted_content=emitted_content),),
                emitted_content,
                True,
            )
        document = cast(dict[str, object], parsed)
        events: list[StreamEvent] = []
        usage = self._parse_usage(document.get("usage"))
        if usage is not None:
            events.append(
                StreamEvent(
                    kind=StreamEventKind.USAGE,
                    request_id=request_id,
                    usage=usage,
                    emitted_content=emitted_content,
                    phase=(
                        StreamPhase.AFTER_CONTENT if emitted_content else StreamPhase.BEFORE_CONTENT
                    ),
                )
            )
        content, finish_reason = self._parse_stream_choice(document)
        content = reasoning_filter.feed(content)
        if content:
            emitted_content = True
            events.append(
                StreamEvent(
                    kind=StreamEventKind.CONTENT,
                    request_id=request_id,
                    content=content,
                    finish_reason=finish_reason,
                    emitted_content=True,
                    phase=StreamPhase.AFTER_CONTENT,
                )
            )
        return tuple(events), emitted_content, False

    @staticmethod
    def _parse_stream_choice(document: Mapping[str, object]) -> tuple[str, str | None]:
        choices = _list(document.get("choices"))
        choice = _mapping(choices[0]) if choices else None
        delta = _mapping(choice.get("delta")) if choice is not None else None
        content = delta.get("content") if delta is not None else ""
        finish_reason = choice.get("finish_reason") if choice is not None else None
        return (
            content if isinstance(content, str) else "",
            finish_reason if isinstance(finish_reason, str) else None,
        )

    @staticmethod
    def _stream_error(
        request_id: str, error: AdapterError, *, emitted_content: bool
    ) -> StreamEvent:
        phase = StreamPhase.AFTER_CONTENT if emitted_content else StreamPhase.BEFORE_CONTENT
        normalized = error.model_copy(update={"emitted_content": emitted_content, "phase": phase})
        return StreamEvent(
            kind=StreamEventKind.ERROR,
            request_id=request_id,
            error=normalized,
            emitted_content=emitted_content,
            phase=phase,
        )
