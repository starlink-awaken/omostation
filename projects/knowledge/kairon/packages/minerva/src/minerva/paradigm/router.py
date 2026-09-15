"""Paradigm Router — classify research questions into the optimal paradigm."""

from __future__ import annotations

from typing import Any

from minerva.paradigm.types import ParadigmResult, ResearchParadigm

CLASSIFY_PROMPT = """Classify this research question into exactly ONE of these paradigms:

1. SCIENTIFIC_INQUIRY — Investigating "what is", "how does X work", "what caused Y".
   Hypothesis-driven exploration of factual questions.
2. COMPARATIVE_ANALYSIS — "Compare X vs Y", "which is better for Z".
   Multi-dimensional comparison with explicit criteria.
3. PROBLEM_SOLVING — "Why does X fail", "how to fix Y", "how to optimize Z".
   Debugging or performance questions with testable hypotheses.
4. LITERATURE_REVIEW — "Survey of X", "trends in Y", "state of the art in Z".
   Broad information collection and categorization.
5. POLICY_ANALYSIS — "Impact of regulation X", "effects of policy Y".
   Multi-stakeholder impact assessment.

Research question: {query}

Respond with a JSON object:
{{"paradigm": "<paradigm_name>", "confidence": 0.0-1.0, "reasoning": "<why>",
"alternative": "<second_best>"}}"""


async def classify_paradigm(llm_client: Any, query: str) -> ParadigmResult:
    """Use LLM to classify a research question into the best paradigm."""
    if llm_client is None:
        return _rule_based_classify(query)

    try:
        import json

        from minerva.shared.cards_context import get_cards_context

        l4_context = get_cards_context()
        system_prompt = "You classify research questions into paradigms. Output valid JSON only." + l4_context

        response = await llm_client.generate(
            system=system_prompt,
            prompt=CLASSIFY_PROMPT.format(query=query[:500]),
            temperature=0.1,
            max_tokens=300,
        )
        start = response.find("{")
        end = response.rfind("}")
        if start >= 0 and end > start:
            data = json.loads(response[start : end + 1])
            paradigm_name = data.get("paradigm", "").upper()
            for p in ResearchParadigm:
                if p.value.upper() == paradigm_name or p.name == paradigm_name:
                    alt_name = data.get("alternative", "").upper()
                    alt = None
                    for ap in ResearchParadigm:
                        if ap.value.upper() == alt_name or ap.name == alt_name:
                            alt = ap
                            break
                    return ParadigmResult(
                        paradigm=p,
                        confidence=float(data.get("confidence", 0.7)),
                        reasoning=data.get("reasoning", ""),
                        alternative=alt,
                    )
    except Exception:
        pass

    return _rule_based_classify(query)


def _rule_based_classify(query: str) -> ParadigmResult:
    """Fast rule-based classification when LLM is unavailable."""
    q = query.lower()

    # Comparative patterns
    if any(w in q for w in ("compare", " vs ", "versus", "which is better", "difference between")):
        return ParadigmResult(
            paradigm=ResearchParadigm.COMPARATIVE_ANALYSIS,
            confidence=0.85,
            reasoning="Detected comparison patterns in query",
        )

    # Problem-solving patterns
    if any(
        w in q
        for w in (
            "why does",
            "how to fix",
            "how to solve",
            "debug",
            "error",
            "bug",
            "optimize",
            "reduce latency",
            "improve performance",
        )
    ):
        return ParadigmResult(
            paradigm=ResearchParadigm.PROBLEM_SOLVING,
            confidence=0.80,
            reasoning="Detected problem-solving patterns in query",
        )

    # Policy patterns
    if any(
        w in q
        for w in (
            "policy",
            "regulation",
            "impact of",
            "law",
            "compliance",
            "tax",
            "subsidy",
            "government",
            "legislation",
        )
    ):
        return ParadigmResult(
            paradigm=ResearchParadigm.POLICY_ANALYSIS,
            confidence=0.80,
            reasoning="Detected policy/regulation patterns in query",
        )

    # Literature review patterns
    if any(
        w in q
        for w in (
            "survey",
            "trends",
            "state of",
            "literature",
            "review of",
            "overview of",
            "what are the",
            "latest in",
            "recent advances",
        )
    ):
        return ParadigmResult(
            paradigm=ResearchParadigm.LITERATURE_REVIEW,
            confidence=0.78,
            reasoning="Detected survey/overview patterns in query",
        )

    # Default: scientific inquiry
    return ParadigmResult(
        paradigm=ResearchParadigm.SCIENTIFIC_INQUIRY,
        confidence=0.70,
        reasoning="Default: hypothesis-driven investigation",
    )
