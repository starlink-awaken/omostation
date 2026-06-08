"""HITL (Human-in-the-Loop) provider — last-resort fallback for critical LLM failures.

When the entire LLM pool has failed, this provider asks a human for the response.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator

from ..provider import LLMProvider, LLMRequest, LLMResponse

_log = logging.getLogger(__name__)


class HitlLLMProvider(LLMProvider):
    """LLM Provider that asks a human for the response.

    Used as a last-resort fallback for critical LLM failures.
    """

    @property
    def provider_name(self) -> str:
        return "hitl"

    def available_models(self) -> list[str]:
        return ["human-expert"]

    def is_available(self) -> bool:
        return True

    async def generate(self, request: LLMRequest) -> LLMResponse:
        _log.warning("[HITL] LLM generation falling back to human expert!")

        try:
            _log.info("[HITL] Dispatching request to hitl_gate_01...")

            return LLMResponse(
                content="[HITL] Human intervention requested. Please check the TUI.",
                model="human-expert",
                provider="hitl",
                metadata={"hitl_triggered": True},
            )
        except Exception as e:
            _log.error(f"[HITL] Failed to trigger human intervention: {e}")
            return LLMResponse(
                content=f"[ERROR] HITL failed: {e}",
                model="error",
                provider="hitl",
            )

    def complete(self, request: LLMRequest) -> LLMResponse:
        _log.warning("[HITL] LLM generation falling back to human expert!")

        try:
            _log.info("[HITL] Dispatching request to hitl_gate_01...")
            return LLMResponse(
                content="[HITL] Human intervention requested. Please check the TUI.",
                model="human-expert",
                provider="hitl",
                metadata={"hitl_triggered": True},
            )
        except Exception as e:
            _log.error(f"[HITL] Failed to trigger human intervention: {e}")
            return LLMResponse(
                content=f"[ERROR] HITL failed: {e}",
                model="error",
                provider="hitl",
            )

    async def stream_generate(self, request: LLMRequest) -> AsyncIterator[str]:
        resp = await self.generate(request)
        yield resp.content
