"""LLM helper compatibility module — delegates to IntelligentAgent.

Migrated from bin/ssot/_llm_helper.py. The original had its own
_get_gateway() + GLM fallback chain. Now delegates to the unified
IntelligentAgent._llm_ask() which uses the same ModelGateway path.

Existing scripts calling `from _llm_helper import llm_ask` work unchanged.
"""

from __future__ import annotations

from typing import Any


def llm_ask(
    question: str, context: dict[str, Any] | None = None, timeout: float = 60.0
) -> str | None:
    """Ask LLM a question, return plain text response.

    Delegates to IntelligentAgent._llm_ask() which uses the unified
    ModelGateway → omlx direct → GLM cloud path.
    """
    try:
        from .intelligent_agent import IntelligentAgent
        return IntelligentAgent.llm_ask(question, context, timeout)
    except Exception:
        return None
