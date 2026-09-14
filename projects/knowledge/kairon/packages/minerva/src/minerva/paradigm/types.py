# DEPRECATED — This module has concept overlap with the sophia package.
# Retained for backward compatibility. New code should use sophia directly.
# This module will be removed in a future release.

"""Research paradigm types — problem classification and structured frameworks."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class ResearchParadigm(Enum):
    """The research paradigm determines the structured framework to apply."""

    SCIENTIFIC_INQUIRY = "scientific_inquiry"  # Hypothesis → Evidence → Verify
    COMPARATIVE_ANALYSIS = "comparative_analysis"  # Criteria → Compare → Synthesize
    PROBLEM_SOLVING = "problem_solving"  # Define → Hypothesize → Test → Verify
    LITERATURE_REVIEW = "literature_review"  # Scope → Collect → Categorize → Gaps
    POLICY_ANALYSIS = "policy_analysis"  # Context → Stakeholders → Impact


class VerificationMode(Enum):
    """How strictly the paradigm requires verification before completion."""

    STRICT = "strict"  # Must pass all verification gates (math-like)
    STANDARD = "standard"  # Should pass most gates, warn on failure
    RELAXED = "relaxed"  # Verification is advisory only


@dataclass
class ParadigmDefinition:
    """Defines a research paradigm: its stages, verification rules, and output format."""

    paradigm: ResearchParadigm
    name: str
    description: str
    verification_mode: VerificationMode
    stages: list[str] = field(default_factory=list)  # Ordered stage names
    completion_criteria: list[str] = field(default_factory=list)  # Must-satisfy conditions
    example_questions: list[str] = field(default_factory=list)


@dataclass
class ParadigmResult:
    """Result of paradigm classification and execution."""

    paradigm: ResearchParadigm
    confidence: float  # 0.0-1.0
    reasoning: str  # Why this paradigm was chosen
    alternative: ResearchParadigm | None = None  # Second-best paradigm
    verification_passed: bool = False
    completion_met: bool = False
    iteration_count: int = 0


# ── Paradigm Definitions ────────────────────────────────────────────

PARADIGMS: dict[ResearchParadigm, ParadigmDefinition] = {
    ResearchParadigm.SCIENTIFIC_INQUIRY: ParadigmDefinition(
        paradigm=ResearchParadigm.SCIENTIFIC_INQUIRY,
        name="Scientific Inquiry",
        description=(
            "Hypothesis-driven investigation: formulate hypothesis, gather evidence from multiple sources, cross-validate claims, verify against counter-evidence, draw conclusion."
        ),
        verification_mode=VerificationMode.STRICT,
        stages=[
            "decompose",
            "search",
            "entity_extract",
            "deep_read",
            "cross_analyze",
            "counter_argument",
            "quality_gate",
            "verify",
            "output",
        ],
        completion_criteria=[
            "Every major claim has ≥1 traceable source",
            "Counter-arguments explicitly addressed",
            "Confidence levels assigned to all conclusions",
            "Verification gate passed (no HIGH-severity issues)",
        ],
        example_questions=[
            "What is the latest in MoE architecture?",
            "How does quantum computing affect cryptography?",
            "What caused the decline of honeybee populations?",
        ],
    ),
    ResearchParadigm.COMPARATIVE_ANALYSIS: ParadigmDefinition(
        paradigm=ResearchParadigm.COMPARATIVE_ANALYSIS,
        name="Comparative Analysis",
        description=(
            "Multi-dimensional comparison: define criteria, collect data for each option, build comparison matrix, synthesize trade-offs, provide recommendation with rationale."
        ),
        verification_mode=VerificationMode.STANDARD,
        stages=[
            "decompose_criteria",
            "search_per_option",
            "cross_compare",
            "synthesize",
            "counter_argument",
            "quality_gate",
            "output",
        ],
        completion_criteria=[
            "Comparison criteria explicitly defined",
            "Each option evaluated on all criteria",
            "Trade-offs clearly articulated",
            "Recommendation supported by evidence",
        ],
        example_questions=[
            "Compare Rust vs Zig for systems programming",
            "ChatGPT vs Gemini vs Claude — which to use?",
            "Kubernetes vs Nomad for container orchestration",
        ],
    ),
    ResearchParadigm.PROBLEM_SOLVING: ParadigmDefinition(
        paradigm=ResearchParadigm.PROBLEM_SOLVING,
        name="Problem Solving",
        description=(
            "Structured debugging: define the problem precisely, generate hypotheses, test each against evidence, eliminate failed hypotheses, verify the solution, document the root cause."
        ),
        verification_mode=VerificationMode.STRICT,
        stages=[
            "define_problem",
            "generate_hypotheses",
            "search_per_hypothesis",
            "test_hypotheses",
            "eliminate_failed",
            "verify_solution",
            "output",
        ],
        completion_criteria=[
            "Problem clearly defined with scope and constraints",
            "All plausible hypotheses enumerated",
            "Each hypothesis tested against evidence",
            "Failed hypotheses explicitly eliminated with reasons",
            "Solution verified (reproducible or logically sound)",
        ],
        example_questions=[
            "Why does my database connection pool keep exhausting?",
            "How to reduce p99 latency in my API?",
            "Why is Python asyncio slower than expected?",
        ],
    ),
    ResearchParadigm.LITERATURE_REVIEW: ParadigmDefinition(
        paradigm=ResearchParadigm.LITERATURE_REVIEW,
        name="Literature Review",
        description=(
            "Systematic survey: define scope, multi-source collection, taxonomy categorization, cross-source synthesis, gap identification, future directions."
        ),
        verification_mode=VerificationMode.STANDARD,
        stages=[
            "define_scope",
            "search",
            "categorize",
            "synthesize",
            "identify_gaps",
            "quality_gate",
            "output",
        ],
        completion_criteria=[
            "Scope clearly defined with inclusion/exclusion criteria",
            "Sources categorized into taxonomic framework",
            "Consensus and disputes across sources documented",
            "Research gaps explicitly identified",
            "Future research directions proposed",
        ],
        example_questions=[
            "Survey the state of AI agent research in 2026",
            "What are the key trends in edge computing?",
            "Literature review of RAG optimization techniques",
        ],
    ),
    ResearchParadigm.POLICY_ANALYSIS: ParadigmDefinition(
        paradigm=ResearchParadigm.POLICY_ANALYSIS,
        name="Policy Analysis",
        description="Impact assessment: establish context, map stakeholders, analyze multi-dimensional impact, evaluate alternatives, provide evidence-based recommendation.",
        verification_mode=VerificationMode.STANDARD,
        stages=[
            "establish_context",
            "map_stakeholders",
            "search",
            "analyze_impact",
            "evaluate_alternatives",
            "counter_argument",
            "quality_gate",
            "output",
        ],
        completion_criteria=[
            "Policy context and jurisdiction clearly stated",
            "Stakeholder map with interests and influence",
            "Impact assessed across economic/social/technical dimensions",
            "Alternatives evaluated with pros/cons",
            "Recommendation with implementation considerations",
        ],
        example_questions=[
            "Analyze the impact of EU AI Act on open-source models",
            "What are the effects of remote work policies on productivity?",
            "Evaluate carbon tax vs cap-and-trade for emissions reduction",
        ],
    ),
}
