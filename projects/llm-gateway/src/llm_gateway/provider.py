# ruff: noqa: RUF002
"""LLM provider abstraction — unified ABC and dataclasses.

Provides:
- :class:`LLMRequest` / :class:`LLMResponse` dataclasses
- :class:`LLMProvider` abstract base class with async/sync/stream interfaces
- :class:`MockLLMProvider` for testing
- :class:`NoneProvider` for silent degradation
- :func:`record_llm_cost` for X3 cost tracking
"""

from __future__ import annotations

import json
import logging
import os
import time as _time
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, TypeVar

_T = TypeVar("_T")

_log = logging.getLogger(__name__)

# ── X3 Cost tracking ─────────────────────────────────────────────────────────
_COST_LOG = Path(os.environ.get("RUNTIME_HOME", str(Path.home() / "runtime"))) / "data" / "llm_cost.jsonl"


def record_llm_cost(model: str, input_tokens: int, output_tokens: int) -> None:
    """Record an LLM call's token usage to the cost log (non-blocking).

    Called from provider implementations after each successful ``complete()``.
    Failure to write the log never breaks the LLM call.
    """
    try:
        record = {
            "ts": datetime.now(UTC).isoformat(),
            "model": model,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
        }
        _COST_LOG.parent.mkdir(parents=True, exist_ok=True)
        line = (json.dumps(record, ensure_ascii=False) + "\n").encode("utf-8")
        fd = os.open(str(_COST_LOG), os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o644)
        try:
            os.write(fd, line)
        finally:
            os.close(fd)
    except Exception:  # noqa: S110
        pass  # non-blocking


# ---------------------------------------------------------------------------
# Custom exceptions
# ---------------------------------------------------------------------------


class LLMError(Exception):
    """Base exception for LLM gateway errors."""


class LLMAvailabilityError(LLMError):
    """Raised when a provider is not available."""


class LLMRetryExhaustedError(LLMError):
    """Raised after all retry attempts fail."""


# ---------------------------------------------------------------------------
# Retry helper
# ---------------------------------------------------------------------------


def _with_llm_retry(  # noqa: UP047
    fn: Callable[[], _T],
    max_retries: int = 3,
    base_delay: float = 1.0,
) -> _T:
    """Execute *fn* with exponential-backoff retry for transient errors.

    Transient errors caught: ``OSError``, ``ValueError``, ``RuntimeError``.
    Permanent errors (e.g. auth failures) **must** raise a different type
    to avoid being retried.
    """
    last_exc: Exception | None = None
    for attempt in range(max_retries + 1):
        try:
            return fn()
        except (OSError, ValueError, RuntimeError) as exc:
            last_exc = exc
            if attempt < max_retries:
                delay = base_delay * (2**attempt)
                _log.warning(
                    "LLM call failed (attempt %d/%d): %s — retrying in %.1fs",
                    attempt + 1,
                    max_retries,
                    exc,
                    delay,
                )
                _time.sleep(delay)
    if last_exc is not None:
        raise LLMRetryExhaustedError(str(last_exc)) from last_exc
    raise LLMRetryExhaustedError("LLM retry exhausted without a captured exception")


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class LLMRequest:
    """A request to an LLM provider.

    Parameters
    ----------
    prompt:
        The primary user prompt / instruction text.
    system_prompt:
        Optional system-level instruction (e.g. "You are a helpful
        assistant").
    model:
        Specific model override.  When ``None`` the provider uses its
        own *default_model*.
    max_tokens:
        Maximum number of tokens to generate.
    temperature:
        Sampling temperature (0.0 – 2.0).
    stop_sequences:
        Optional list of stop sequences.
    context:
        Optional conversation history as a list of message dicts
        (``{"role": …, "content": …}``).
    metadata:
        Arbitrary key/value pairs passed through to the provider.
    """

    prompt: str
    system_prompt: str = ""
    model: str | None = None
    max_tokens: int = 1024
    temperature: float = 0.7
    stop_sequences: list[str] = field(default_factory=list)
    context: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class LLMResponse:
    """A response from an LLM provider.

    Parameters
    ----------
    content:
        The actual response text.
    provider:
        Provider name (e.g. ``"openai"``, ``"ollama"``).
    model:
        Model name that produced the response.
    input_tokens:
        Number of input (prompt) tokens consumed.
    output_tokens:
        Number of output (completion) tokens generated.
    finish_reason:
        Reason the generation stopped
        (``"stop"``, ``"length"``, ``"error"``, …).
    metadata:
        Arbitrary key/value pairs from the provider.
    """

    content: str
    provider: str = ""
    model: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    finish_reason: str = "stop"
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ToolSchema:
    """Schema for a tool/function that an LLM can call."""

    name: str
    description: str
    parameters: dict[str, Any]


@dataclass
class ToolCall:
    """A tool call request from the LLM."""

    id: str
    name: str
    arguments: dict[str, Any]


@dataclass
class ToolResult:
    """Result of executing a tool call."""

    call_id: str
    output: Any
    error: str | None = None


# ---------------------------------------------------------------------------
# Abstract base
# ---------------------------------------------------------------------------


class LLMProvider(ABC):
    """Unified LLM Provider Abstraction.

    Subclasses **must** implement:

    - :meth:`generate`  — async generation
    - :meth:`complete`  — sync generation (may delegate to ``generate``)
    - :meth:`is_available` — availability check
    - :attr:`provider_name` — identity string

    Subclasses **may** override:

    - :meth:`stream_generate` — streaming (default yields full output)
    - :meth:`health_check` — detailed health probe
    - :meth:`available_models` — model listing
    """

    # ------------------------------------------------------------------
    # Abstract
    # ------------------------------------------------------------------

    @abstractmethod
    async def generate(self, request: LLMRequest) -> LLMResponse:
        """Core async generation method."""

    @abstractmethod
    def complete(self, request: LLMRequest) -> LLMResponse:
        """Synchronous generation (backward-compatible entry point)."""

    @abstractmethod
    def is_available(self) -> bool:
        """Check whether this provider is ready for use.

        Returns ``False`` when the API key is missing, the SDK is not
        installed, or the service is unreachable.
        """

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Provider identity string (e.g. ``"openai"``)."""

    # ------------------------------------------------------------------
    # Optional overrides
    # ------------------------------------------------------------------

    async def stream_generate(self, request: LLMRequest) -> AsyncIterator[str]:
        """Stream response tokens as they arrive.

        Default implementation calls :meth:`generate` and yields the
        full content in one chunk.  Subclasses should override this to
        provide real streaming.
        """
        resp = await self.generate(request)
        yield resp.content

    def health_check(self) -> str:
        """Run a health probe.

        Returns an empty string when healthy, or an error message when
        the provider is unavailable or misconfigured.
        """
        if not self.is_available():
            return f"{self.__class__.__name__} not available"
        return ""

    def available_models(self) -> list[str]:
        """Return the list of models this provider can use.

        Subclasses may override to query the API for the actual list.
        """
        return []


# ---------------------------------------------------------------------------
# Concrete providers
# ---------------------------------------------------------------------------


class MockLLMProvider(LLMProvider):
    """Mock provider for testing.

    Always available.  ``generate`` / ``complete`` return a canned
    response that echoes the first 50 characters of the prompt.
    """

    @property
    def provider_name(self) -> str:
        return "mock"

    def available_models(self) -> list[str]:
        return ["mock-model"]

    def is_available(self) -> bool:
        return True

    async def generate(self, request: LLMRequest) -> LLMResponse:
        return LLMResponse(
            content=f"Mock response to: {request.prompt[:50]}",
            provider="mock",
            model="mock-model",
            input_tokens=len(request.prompt.split()),
            output_tokens=10,
        )

    def complete(self, request: LLMRequest) -> LLMResponse:
        response = LLMResponse(
            content=f"Mock response to: {request.prompt[:50]}",
            provider="mock",
            model="mock-model",
            input_tokens=len(request.prompt.split()),
            output_tokens=10,
        )
        # X3 cost tracking — silent fail per record_llm_cost contract
        record_llm_cost(response.model, response.input_tokens, response.output_tokens)
        return response


class NoneProvider(LLMProvider):
    """Silent degradation provider.

    Always reports available but returns a fallback response.
    Useful as a no-op placeholder when all real providers are down.
    """

    @property
    def provider_name(self) -> str:
        return "none"

    def is_available(self) -> bool:
        return True

    async def generate(self, request: LLMRequest) -> LLMResponse:
        return LLMResponse(
            content="",
            provider="none",
            model="none",
        )

    def complete(self, request: LLMRequest) -> LLMResponse:
        response = LLMResponse(
            content="",
            provider="none",
            model="none",
        )
        # X3 cost tracking — NoneProvider 默认 0 tokens
        record_llm_cost(response.model, 0, 0)
        return response
