"""Pipeline verifiers — step-level and global report verification.

Inspired by MiroThinker-H1's Local+Global Verifier architecture:
- StepVerifier: checks consistency after each pipeline stage (local, $0)
- GlobalVerifier: fact-checks final report claims against sources (global, $0)
"""

from __future__ import annotations

from typing import Any

STEP_VERIFY_PROMPT = """You are a research quality auditor. Review the intermediate research state for consistency issues.

Current stage: {stage_name}
Research query: {query}

Intermediate state:
- Sub-questions: {sub_count}
- Search results: {src_count} ({sources})
- Entities extracted: {entity_count}
- Contradictions found: {contradiction_count}

Check for:
1. Entity consistency — do extracted entities match the query domain?
2. Source traceability — can claims be traced back to search results?
3. Contradiction awareness — are conflicting views noted?

Respond with one line: "OK" if everything is consistent, or describe the specific issue found."""

GLOBAL_VERIFY_PROMPT = """You are a fact-checker. Verify the following research report claims against the provided sources.

Report:
{report}

Sources:
{sources}

For each claim in the report that makes a factual assertion:
1. Check if at least one source supports it
2. Mark claims with NO source support as [UNVERIFIED]
3. Note any claims that contradict a source

Output a JSON array of issues found:
[{{"claim": "claim text", "issue": "no_source|contradiction|weak_evidence", "detail": "..."}}]

If all claims are supported, return an empty array []."""


async def verify_step(llm_client: Any, ctx: Any, stage_name: str) -> dict:
    """Run a lightweight consistency check after a pipeline stage.

    Uses local LLM (qwen3.6:35b, $0) to check intermediate research state.
    Returns {"status": "ok"} or {"status": "warning", "issue": "..."}
    """
    if llm_client is None:
        return {"status": "ok"}
    try:
        sources = ", ".join(sorted({r.get("source", "web") for r in ctx.search_results[:10]})) or "none"
        response = await llm_client.generate(
            system="You are a research quality auditor. Be concise.",
            prompt=STEP_VERIFY_PROMPT.format(
                stage_name=stage_name,
                query=ctx.query[:200],
                sub_count=len(ctx.sub_questions),
                src_count=len(ctx.search_results),
                sources=sources,
                entity_count=len(ctx.entities),
                contradiction_count=len(ctx.contradictions or []),
            ),
            temperature=0.1,
            max_tokens=100,
        )
        response = response.strip()
        if response.upper().startswith("OK"):
            return {"status": "ok"}
        return {"status": "warning", "issue": response[:200]}
    except Exception:
        return {"status": "ok"}  # Verification never blocks


async def verify_report(llm_client: Any, report: str, search_results: list[dict]) -> dict:
    """Verify that report claims are supported by search result sources.

    Returns {"verified": True, "issues": [...]} or {"verified": False, "issues": [...]}
    """
    if not llm_client or not search_results:
        return {"verified": True, "issues": []}

    sources_text = "\n".join(
        f"[{i + 1}] {r.get('title', 'Untitled')[:100]} — {r.get('snippet', '')[:200]}"
        for i, r in enumerate(search_results[:15])
    )
    if len(sources_text) < 100:
        return {"verified": True, "issues": []}

    try:
        response = await llm_client.generate(
            system="You verify research reports against sources. Output valid JSON only.",
            prompt=GLOBAL_VERIFY_PROMPT.format(
                report=report[:4000],
                sources=sources_text[:3000],
            ),
            temperature=0.1,
            max_tokens=800,
        )
        import json

        start = response.find("[")
        end = response.rfind("]")
        if start >= 0 and end > start:
            issues = json.loads(response[start : end + 1])
            return {"verified": len(issues) == 0, "issues": issues}
    except Exception:
        pass

    return {"verified": True, "issues": []}
