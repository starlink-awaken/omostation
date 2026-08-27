"""Sophia MCP Server — paradigm compilation and analysis via MCP protocol."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

from fastmcp import FastMCP

if TYPE_CHECKING:
    from openai import AsyncOpenAI

    from .learner import ParadigmLearner  # type: ignore[reportMissingImports]

FORMAT_VERSION = "sophia-v1"

_AUTH_TOKEN = os.environ.get("SOPHIA_AUTH_TOKEN", "")

mcp = FastMCP(
    "Sophia — Research Paradigm Engine",
    mask_error_details=True,
)

_learner_instance = None
_llm_client_instance = None


def _get_learner() -> ParadigmLearner:
    global _learner_instance
    if _learner_instance is None:
        from .learner import ParadigmLearner  # type: ignore[reportMissingImports]

        _learner_instance = ParadigmLearner()
    return _learner_instance


class _LLMClient:
    """LLM client wrapper using AsyncOpenAI, cached at module level."""

    def __init__(self, oai_client: AsyncOpenAI) -> None:
        self._oai = oai_client

    async def generate(
        self,
        system: str,
        prompt: str,
        temperature: float,
        max_tokens: int,
    ) -> str:
        resp = await self._oai.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return resp.choices[0].message.content or ""


def _get_llm_client() -> _LLMClient | None:
    """Lazy-init AsyncOpenAI client via AetherForge proxy."""
    global _llm_client_instance
    if _llm_client_instance is None:
        api_key = os.environ.get("AETHERFORGE_KEY", "local")
        base_url = os.environ.get("AETHERFORGE_URL", "http://127.0.0.1:9290/v1")
        from openai import AsyncOpenAI

        _llm_client_instance = _LLMClient(
            AsyncOpenAI(api_key=api_key, base_url=base_url),
        )
    return _llm_client_instance


# ── 辅助函数 ─────────────────────────────────────────
# _ok() / _error() 集中管理返回格式。


def _error(msg: str) -> dict:
    """返回标准错误响应（内建 format_version）。"""
    return {"status": "error", "error": msg, "format_version": FORMAT_VERSION}


def _ok(data: dict) -> dict:
    """返回标准成功响应。data 中应包含 format_version 字段。"""
    return {"status": "ok", **data}


@mcp.tool()
async def compile_paradigm(query: str, use_llm: bool = False) -> dict:
    """Compile a research paradigm for a given question.

    Returns the paradigm program as JSON with operations, states, and transitions.
    Use when you need to determine the best research framework for a question.

    Args:
        query: The research question to analyze
        use_llm: Whether to use LLM for compilation (default: rule-based)
    """
    from .compiler import compile_paradigm as compile_paradigm_async  # type: ignore[reportMissingImports]
    from .compiler import compile_paradigm_sync  # type: ignore[reportMissingImports]

    if not query.strip():
        return _error("Query must not be empty")

    if use_llm:
        llm_client = _get_llm_client()
        if llm_client is not None:
            try:
                program = await compile_paradigm_async(llm_client, query[:1000])
                result = program.to_dict()
                result["format_version"] = FORMAT_VERSION
                return _ok(result)
            except Exception:
                pass  # fall through to sync fallback

    program = compile_paradigm_sync(query[:1000])
    result = program.to_dict()
    result["format_version"] = FORMAT_VERSION
    return _ok(result)


@mcp.tool()
def list_operations() -> dict:
    """List all available atomic research operations with descriptions.

    Use when you need to understand what operations are available for building paradigms.
    """
    ops = {
        "DECOMPOSE": "Split question into sub-questions",
        "SEARCH": "Gather sources for a claim",
        "EXTRACT": "Extract entities/claims from text",
        "COMPARE": "Compare multiple claims/sources",
        "HYPOTHESIZE": "Generate tentative answer",
        "VERIFY": "Check claim against evidence",
        "SYNTHESIZE": "Combine claims into conclusion",
        "ELIMINATE": "Remove disproven hypothesis",
        "ITERATE": "Re-run with refined parameters",
        "CONCLUDE": "Finalize answer",
    }
    return _ok(
        {
            "format_version": FORMAT_VERSION,
            "operations": ops,
        }
    )


@mcp.tool()
def list_states() -> dict:
    """List all research states in the paradigm state machine."""
    from .symbols import ResearchState  # type: ignore[reportMissingImports]

    states = {s.name: s.value for s in ResearchState}
    return _ok(
        {
            "format_version": FORMAT_VERSION,
            "states": states,
        }
    )


@mcp.tool()
def get_transitions() -> dict:
    """Get the base transition rules between research states.

    Returns {from_state, operation, to_state, gate_function, on_fail} for each rule.
    """
    from .symbols import BASE_TRANSITIONS  # type: ignore[reportMissingImports]

    rules = []
    for t in BASE_TRANSITIONS:
        rules.append(
            {
                "from": t.from_state.value,
                "operation": t.operation.value,
                "to": t.to_state.value,
                "gate": t.gate.__name__,
                "on_fail": t.on_fail.value,
            }
        )
    return _ok(
        {
            "format_version": FORMAT_VERSION,
            "transitions": rules,
        }
    )


@mcp.tool()
def record_trace(query: str, paradigm_name: str, operations: str, quality_score: int = 80) -> dict:
    """Record a research trace for future learning.

    Args:
        query: The research question
        paradigm_name: Name of the paradigm used
        operations: Comma-separated list of operation names used
        quality_score: Quality score (0-100) of the research
    """
    from .learner import ResearchTrace  # type: ignore[reportMissingImports]
    from .symbols import AtomicOp  # type: ignore[reportMissingImports]

    if not query.strip():
        return _error("Query must not be empty")
    if not paradigm_name.strip():
        return _error("Paradigm name must not be empty")
    if not 0 <= quality_score <= 100:
        return _error("Quality score must be 0-100")

    ops = [o.strip() for o in operations.split(",") if o.strip()]
    valid_ops = [op for op in ops if AtomicOp.from_string(op) is not None]
    if not valid_ops:
        allowed = [o.value for o in AtomicOp]
        return _error(f"No valid operations. Allowed: {allowed}")

    trace = ResearchTrace(
        query=query[:500],
        paradigm_name=paradigm_name[:200],
        operations=valid_ops,
        quality_score=quality_score,
        completed=True,
    )
    _get_learner().record(trace)
    return _ok(
        {
            "format_version": FORMAT_VERSION,
            "action": "recorded",
            "query": query[:100],
            "ops": valid_ops,
        }
    )


@mcp.tool()
def get_effective_ops(domain_hint: str = "") -> dict:
    """Get operation effectiveness scores based on past traces.

    Args:
        domain_hint: Optional domain filter for traces (min 4 chars)
    """
    if domain_hint and len(domain_hint) < 4:
        return _error("domain_hint must be at least 4 characters if provided")
    scores = _get_learner().get_effective_ops(domain_hint=domain_hint)
    return _ok(
        {
            "format_version": FORMAT_VERSION,
            "scores": scores,
        }
    )


@mcp.tool()
def suggest_ops(domain_hint: str = "") -> dict:
    """Suggest the most effective operations based on learning history.

    Args:
        domain_hint: Optional domain filter (min 4 chars)
    """
    if domain_hint and len(domain_hint) < 4:
        return _error("domain_hint must be at least 4 characters if provided")
    ops = _get_learner().suggest_ops(domain_hint=domain_hint)
    return _ok(
        {
            "format_version": FORMAT_VERSION,
            "operations": ops,
        }
    )


@mcp.tool()
def suggest_paradigm(query: str) -> dict:
    """Suggest an optimized paradigm based on learning from similar past queries.

    Args:
        query: The research question to optimize for
    """
    if not query.strip():
        return _error("Query must not be empty")
    suggestion = _get_learner().suggest_paradigm(query[:1000])
    return _ok(
        {
            "format_version": FORMAT_VERSION,
            "suggestion": suggestion,
        }
    )


def main() -> int:
    mcp.run()
    return 0


if __name__ == "__main__":
    main()
