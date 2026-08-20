"""B.D.S.K. virtual-board evaluation through the canonical BOS compute route.

The persona endpoint is orchestration, not an inference engine. Every proved
evaluation therefore comes from ``bos://compute/aetherforge/infer``. There is
no rules-based success fallback and this endpoint never writes an ADR.
"""

from __future__ import annotations

import asyncio
import json
import re
from collections.abc import Mapping
from hashlib import sha256
from typing import Any

from agora.mcp.resolver.adapter import get_stdio_adapter as _get_stdio_adapter
from agora.mcp.resolver.api import get_service as _get_service
from agora.server._response import FORMAT_VERSION, _error, _ok

_COMPUTE_URI = "bos://compute/aetherforge/infer"
_COMPUTE_TIMEOUT_SECONDS = 120.0
_COMPUTE_TIMEOUT_MAX_SECONDS = 120.0
_ROLES = ("builder", "devil", "sage", "keeper")
_SAFE_VERDICTS = {
    "REVIEW_REQUIRED",
    "PROCEED_WITH_GUARDRAILS",
    "DO_NOT_PROCEED",
}
_POSIX_ABSOLUTE_PATH = re.compile(r"(?:^|[^A-Za-z0-9_/])/(?!/)")
_WINDOWS_DRIVE_PATH = re.compile(r"(?i)(?:^|[^a-z0-9])[a-z]:[\\/]")
_UNC_PATH = re.compile(r"(?:\\\\|//)[^\\/\s]+[\\/]")
_CREDENTIAL = re.compile(
    r"(?i)(?:\bsk-(?:test-)?[a-z0-9_-]{4,}|"
    r"\b(?:token|credential|password|api[_-]?key|secret)\s*[:=]\s*\S+)"
)


def _persist_bdsk_adr(*_args: Any, **_kwargs: Any) -> str:
    """Retained import shim; automatic ADR persistence is intentionally disabled."""
    raise RuntimeError("automatic_adr_persistence_disabled")


def _not_proven(error_code: str) -> dict[str, Any]:
    result = _error("BDSK evaluation not proven")
    result.update(
        {
            "proof_state": "not_proven",
            "verdict": "NOT_PROVEN",
            "compute_uri": _COMPUTE_URI,
            "error_code": error_code,
        }
    )
    return result


def _privacy_safe(topic: Any, context: Any) -> bool:
    if not isinstance(topic, str) or not isinstance(context, str):
        return False
    if not topic.strip() or len(topic) > 4_000 or len(context) > 8_000:
        return False
    combined = topic + context
    if any(ord(character) < 32 or ord(character) == 127 for character in combined):
        return False
    return not any(_contains_private_syntax(value) for value in (topic, context))


def _contains_private_syntax(value: str) -> bool:
    return bool(
        _POSIX_ABSOLUTE_PATH.search(value)
        or _WINDOWS_DRIVE_PATH.search(value)
        or _UNC_PATH.search(value)
        or _CREDENTIAL.search(value)
    )


def _privacy_safe_output(value: str, topic: str, context: str) -> bool:
    if any(ord(character) < 32 or ord(character) == 127 for character in value):
        return False
    if _contains_private_syntax(value):
        return False
    return topic not in value and (not context or context not in value)


def _extract_openai_content(result: Any) -> str | None:
    """Extract bounded OpenAI-compatible content from resolver envelopes."""
    current = result
    for _depth in range(4):
        if not isinstance(current, Mapping):
            return None
        choices = current.get("choices")
        if isinstance(choices, list) and choices:
            first = choices[0]
            if not isinstance(first, Mapping):
                return None
            message = first.get("message")
            if not isinstance(message, Mapping):
                return None
            content = message.get("content")
            if isinstance(content, str) and len(content) <= 32_000:
                return content
            return None
        nested = current.get("result")
        if nested is current:
            return None
        current = nested
    return None


def _validated_board_result(
    content: str, topic: str, context: str
) -> tuple[dict[str, Any] | None, str | None]:
    """Accept only the small decision schema; discard all untrusted extra output."""
    try:
        raw = json.loads(content)
    except (json.JSONDecodeError, RecursionError):
        return None, "invalid_compute_response"
    if not isinstance(raw, Mapping):
        return None, "invalid_compute_response"

    verdict = raw.get("verdict")
    risk_score = raw.get("risk_score")
    recommendation = raw.get("recommendation")
    reviews = raw.get("board_reviews")
    if verdict not in _SAFE_VERDICTS:
        return None, "invalid_compute_response"
    if (
        isinstance(risk_score, bool)
        or not isinstance(risk_score, int)
        or not 0 <= risk_score <= 100
    ):
        return None, "invalid_compute_response"
    if not isinstance(recommendation, str) or not recommendation.strip():
        return None, "invalid_compute_response"
    if not isinstance(reviews, Mapping):
        return None, "invalid_compute_response"

    bounded_recommendation = recommendation[:4_000]
    if not _privacy_safe_output(bounded_recommendation, topic, context):
        return None, "unsafe_compute_response"

    safe_reviews: dict[str, dict[str, str]] = {}
    for role in _ROLES:
        review = reviews.get(role)
        if not isinstance(review, Mapping):
            return None, "invalid_compute_response"
        opinion = review.get("opinion")
        if not isinstance(opinion, str) or not opinion.strip():
            return None, "invalid_compute_response"
        bounded_opinion = opinion[:4_000]
        if not _privacy_safe_output(bounded_opinion, topic, context):
            return None, "unsafe_compute_response"
        safe_review = {"opinion": bounded_opinion}
        for optional in ("role", "focus"):
            value = review.get(optional)
            if isinstance(value, str) and value.strip():
                bounded_value = value[:500]
                if not _privacy_safe_output(bounded_value, topic, context):
                    return None, "unsafe_compute_response"
                safe_review[optional] = bounded_value
        safe_reviews[role] = safe_review

    return {
        "verdict": verdict,
        "risk_score": risk_score,
        "recommendation": bounded_recommendation,
        "board_reviews": safe_reviews,
    }, None


async def _invoke_compute(uri: str, **payload: Any) -> dict[str, Any]:
    """Resolve the canonical service and enforce the timeout in its real adapter."""
    service = _get_service(uri)
    if service is None or service.transport != "stdio":
        return {"status": "error"}
    timeout_seconds = min(
        max(float(_COMPUTE_TIMEOUT_SECONDS), 0.01), _COMPUTE_TIMEOUT_MAX_SECONDS
    )
    adapter = _get_stdio_adapter(timeout=timeout_seconds)
    payload["timeout"] = timeout_seconds
    return await asyncio.to_thread(adapter.call, service, **payload)


def _prompt(topic: str, mode: str, context: str) -> str:
    return f"""Evaluate this proposal as the B.D.S.K. four-corner board.
Mode: {mode}
Topic: {topic}
Context: {context or '[not provided]'}

Return JSON only with exactly these decision fields:
{{
  "verdict": "REVIEW_REQUIRED|PROCEED_WITH_GUARDRAILS|DO_NOT_PROCEED",
  "risk_score": 0,
  "recommendation": "bounded human-review recommendation",
  "board_reviews": {{
    "builder": {{"opinion": "..."}},
    "devil": {{"opinion": "..."}},
    "sage": {{"opinion": "..."}},
    "keeper": {{"opinion": "..."}}
  }}
}}
Never claim APPROVED or ACCEPTED. This output is advisory and cannot authorize
a commit, merge, deployment, ADR, or external side effect.
"""


async def persona_bdsk_evaluate(
    topic: str,
    mode: str = "deep",
    context: str = "",
    persist_adr: bool = False,
    adr_dir: str = "docs/decisions",
) -> dict[str, Any]:
    """Evaluate via AetherForge; unavailable or malformed compute is not proven."""
    del adr_dir  # legacy input retained only to fail closed without touching disk
    if persist_adr:
        return _not_proven("automatic_adr_persistence_disabled")
    if mode not in {"deep", "fast"}:
        return _not_proven("unsupported_mode")
    if not _privacy_safe(topic, context):
        return _not_proven("privacy_rejected")

    try:
        compute_result = await _invoke_compute(
            _COMPUTE_URI,
            prompt=_prompt(topic, mode, context),
            model="coding-fast",
            routing_mode="local",
            stream=False,
        )
    except Exception:
        return _not_proven("compute_unavailable")
    if not isinstance(compute_result, Mapping) or compute_result.get("status") != "ok":
        return _not_proven("compute_unavailable")

    content = _extract_openai_content(compute_result)
    board_result, validation_error = (
        _validated_board_result(content, topic, context)
        if content is not None
        else (None, "invalid_compute_response")
    )
    if board_result is None:
        return _not_proven(validation_error or "invalid_compute_response")

    return _ok(
        {
            "format_version": FORMAT_VERSION,
            "topic_digest": f"sha256:{sha256(topic.encode()).hexdigest()}",
            "context_digest": f"sha256:{sha256(context.encode()).hexdigest()}",
            "mode": mode,
            "proof_state": "proven",
            "compute_uri": _COMPUTE_URI,
            **board_result,
        }
    )


# ── route helper ──────────────────────────────────────────────
